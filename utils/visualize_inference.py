"""Render affordance/planning inference output on top of the input image.

Used by run_inference.py / scripts/e2e_inference.py when --visualize is set.

Three rendering modes:
  - "planning" + masks supplied: paint each step's Lang-SAM region as a
    translucent color fill + outline, labeled with the step numbers that
    share the region and the model-emitted affordance_region text.
  - "affordance": single point from {"u", "v"} (legacy V1 path).
  - "pointing" / "grounding" / "trajectory" / generic: scan for any
    [u, v] in [0, 1] and draw a crosshair fallback.

PIL-only; numpy used for the per-pixel region blend.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Distinct colors for up to 12 steps; cycles after.
_STEP_COLORS = [
    "#e74c3c", "#e67e22", "#f1c40f", "#2ecc71", "#3498db", "#9b59b6",
    "#1abc9c", "#d35400", "#c0392b", "#16a085", "#8e44ad", "#2c3e50",
]


def _load_font(size: int = 14) -> ImageFont.ImageFont:
    """Try DejaVuSans (common on Linux), fall back to PIL default."""
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_point(draw: ImageDraw.ImageDraw, x: int, y: int, color: str,
                radius: int = 7, label: str | None = None,
                font: ImageFont.ImageFont | None = None) -> None:
    """Draw a hollow circle marker with optional label to the right."""
    draw.ellipse(
        [x - radius, y - radius, x + radius, y + radius],
        outline=color, width=3,
    )
    # Crosshair for sub-pixel precision when point is small
    draw.line([x - radius - 2, y, x - 2, y], fill=color, width=1)
    draw.line([x + 2, y, x + radius + 2, y], fill=color, width=1)
    draw.line([x, y - radius - 2, x, y - 2], fill=color, width=1)
    draw.line([x, y + 2, x, y + radius + 2], fill=color, width=1)
    if label:
        # Background pill behind text for readability on white/cluttered scenes
        tx, ty = x + radius + 4, y - radius - 2
        if font is not None:
            bbox = draw.textbbox((tx, ty), label, font=font)
            draw.rectangle(bbox, fill="#000000aa")
            draw.text((tx, ty), label, fill=color, font=font)
        else:
            draw.text((tx, ty), label, fill=color)


def _norm_to_pixel(u: float, v: float, w: int, h: int) -> tuple[int, int]:
    """Convert normalized [0,1] coords to pixel ints, clamped to image bounds."""
    return (
        max(0, min(int(round(u * w)), w - 1)),
        max(0, min(int(round(v * h)), h - 1)),
    )


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    h = color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _mask_boundary(mask: np.ndarray, width: int = 2) -> np.ndarray:
    """Extract a `width`-pixel-thick boundary band of a boolean mask.

    Uses iterated XOR-with-shift to avoid pulling in scipy.ndimage just for
    binary dilation — keeps this module's import footprint at numpy + PIL.
    """
    band = np.zeros_like(mask, dtype=bool)
    for shift in range(1, width + 1):
        for axis in (0, 1):
            band |= mask ^ np.roll(mask, shift, axis=axis)
            band |= mask ^ np.roll(mask, -shift, axis=axis)
    return band & ~mask  # keep only pixels just OUTSIDE the mask -> crisp ring


def _blend_region(canvas: np.ndarray, mask: np.ndarray,
                  color_rgb: tuple[int, int, int], alpha: float = 0.45,
                  outline_width: int = 2) -> np.ndarray:
    """Alpha-blend a translucent color fill on `mask` pixels of `canvas`
    and draw a solid outline `outline_width` pixels thick. Operates in
    float32 then casts back to uint8."""
    arr = canvas.astype(np.float32)
    color = np.array(color_rgb, dtype=np.float32)
    m3 = mask[..., None].astype(np.float32)
    arr = arr * (1.0 - alpha * m3) + color * (alpha * m3)
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    if outline_width > 0:
        ring = _mask_boundary(mask, width=outline_width)
        arr[ring] = color_rgb
    return arr


def _iter_planning_points(structured: dict) -> Iterable[tuple[int, str, str, str, list[float]]]:
    """Yield (step_num, action, target, hint, [u, v]) for each step with affordance.

    `hint` is the affordance_region string (V2) or affordance_hint (V1
    back-compat), empty if neither is present — caller decides whether to
    include it in the rendered label.
    """
    for s in structured.get("steps", []):
        # Canonical V2 location after Lang-SAM refinement; fall back to the
        # legacy root-level field for plans produced by older inference runs.
        aff = (s.get("grounding") or {}).get("affordance_2d") or s.get("affordance")
        if not aff or len(aff) < 2:
            continue
        yield (
            s.get("step", 0),
            s.get("action", "?"),
            s.get("target", "?"),
            s.get("affordance_region") or s.get("affordance_hint") or "",
            aff,
        )


def render(image_path: str | Path, structured: dict, task: str,
           output_path: str | Path,
           masks: list | None = None) -> Path:
    """Render structured inference output as an overlay PNG.

    Args:
        image_path: Source RGB image (PNG/JPG).
        structured: Parsed inference dict from run_single().
        task: "planning" | "affordance" | "pointing" | other.
        output_path: Where to save the annotated PNG.
        masks: Optional Lang-SAM masks aligned 1:1 with structured["steps"].
            Each entry is either None (no mask for that step) or
            {"mask": np.ndarray bool, "uv": (u, v) float, "prompt": str, ...}.
            When provided in planning mode, the renderer paints each unique
            mask as a translucent region with combined step labels instead
            of point markers.

    Returns:
        Path to the saved image.
    """
    image_path = Path(image_path)
    output_path = Path(output_path)
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    font = _load_font(max(12, w // 28))
    # Default canvas — region branch replaces it after the numpy blend, all
    # other branches draw on it directly.
    canvas = img.copy()
    draw = ImageDraw.Draw(canvas)

    drawn = 0

    if task == "planning" and masks and any(m for m in masks):
        # ---- Region overlay (V2 path) ----
        # Multiple steps often share a single SAM mask (same target). Dedupe
        # by id(mask) so a region is filled exactly once with the union of
        # step numbers labeling it. Mask resolution may differ from the
        # display image (e.g. SAM at 256, image at higher res) — resize to
        # canvas with nearest-neighbor.
        arr = np.array(img)
        groups: dict[int, dict] = {}
        steps = structured.get("steps", [])
        for idx, step in enumerate(steps):
            if idx >= len(masks) or masks[idx] is None:
                continue
            entry = masks[idx]
            mask_arr = entry["mask"]
            mid = id(mask_arr)
            g = groups.setdefault(mid, {
                "mask": mask_arr,
                "uv": entry.get("uv"),
                "region_text": step.get("affordance_region", ""),
                "step_nums": [],
                "first_step": step.get("step", idx + 1),
            })
            g["step_nums"].append(step.get("step", idx + 1))

        for g in groups.values():
            mask_arr = g["mask"]
            if mask_arr.shape[:2] != (h, w):
                mask_img = Image.fromarray(mask_arr.astype(np.uint8) * 255)
                mask_img = mask_img.resize((w, h), Image.NEAREST)
                mask_arr = np.array(mask_img) > 127
            color_hex = _STEP_COLORS[(g["first_step"] - 1) % len(_STEP_COLORS)]
            color_rgb = _hex_to_rgb(color_hex)
            arr = _blend_region(arr, mask_arr, color_rgb,
                                alpha=0.45, outline_width=2)
            drawn += 1

        canvas = Image.fromarray(arr)
        draw = ImageDraw.Draw(canvas)
        # Labels go on second pass so they sit on top of every region fill.
        for g in groups.values():
            mask_arr = g["mask"]
            if mask_arr.shape[:2] != (h, w):
                mask_img = Image.fromarray(mask_arr.astype(np.uint8) * 255)
                mask_img = mask_img.resize((w, h), Image.NEAREST)
                mask_arr = np.array(mask_img) > 127
            # Anchor: the strategy-selected uv if available; otherwise the
            # mask centroid. uv is normalized [0, 1] from refine_plan.
            uv = g.get("uv")
            if uv is not None:
                lx, ly = _norm_to_pixel(float(uv[0]), float(uv[1]), w, h)
            else:
                ys, xs = np.where(mask_arr)
                if len(xs) == 0:
                    continue
                lx, ly = int(xs.mean()), int(ys.mean())
            steps_str = ",".join(str(n) for n in sorted(g["step_nums"]))
            region_text = g["region_text"] or "<region>"
            label = f"{steps_str}. {region_text}"
            color_hex = _STEP_COLORS[(g["first_step"] - 1) % len(_STEP_COLORS)]
            bbox = draw.textbbox((lx + 4, ly - 4), label, font=font)
            pad = 2
            draw.rectangle(
                (bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad),
                fill="#000000cc",
            )
            draw.text((lx + 4, ly - 4), label, fill=color_hex, font=font)

    elif task == "planning":
        # ---- Legacy point fallback (no masks supplied) ----
        groups: dict[tuple[int, int], list[tuple[int, str, str, str]]] = {}
        for step_num, action, target, hint, (u, v) in _iter_planning_points(structured):
            x, y = _norm_to_pixel(u, v, w, h)
            groups.setdefault((x, y), []).append((step_num, action, target, hint))
        for (x, y), entries in groups.items():
            entries.sort(key=lambda e: e[0])
            steps_str = ",".join(str(e[0]) for e in entries)
            first = entries[0]
            hint = first[3]
            if hint:
                label = f"{steps_str}. {hint}"
            else:
                label = f"{steps_str}.{first[1]}({first[2]})"
            color = _STEP_COLORS[(first[0] - 1) % len(_STEP_COLORS)]
            _draw_point(draw, x, y, color, label=label, font=font)
            drawn += 1

    elif task == "affordance":
        u, v = structured.get("u"), structured.get("v")
        if u is not None and v is not None:
            x, y = _norm_to_pixel(float(u), float(v), w, h)
            hint = structured.get("affordance_hint")
            label = hint if hint else "affordance"
            ga = structured.get("gripper_width")
            if ga is not None:
                label += f" w={ga:.2f}"
            _draw_point(draw, x, y, _STEP_COLORS[0], label=label, font=font)
            drawn += 1

    else:
        # Generic fallback: any (u, v) with values in [0, 1].
        u, v = structured.get("u"), structured.get("v")
        if isinstance(u, (int, float)) and isinstance(v, (int, float)) \
                and 0 <= u <= 1 and 0 <= v <= 1:
            x, y = _norm_to_pixel(float(u), float(v), w, h)
            _draw_point(draw, x, y, _STEP_COLORS[0], label=task, font=font)
            drawn += 1

    label_kind = "regions" if (task == "planning" and masks and any(masks)) else "points"
    banner = f"task={task}  {label_kind}={drawn}"
    bbox = draw.textbbox((4, 4), banner, font=font)
    draw.rectangle(bbox, fill="#000000bb")
    draw.text((4, 4), banner, fill="#ffffff", font=font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return output_path
