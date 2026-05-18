#!/usr/bin/env python3
"""Relabel affordance_hint fields in plan.json using GPT-4o vision.

The original training labels (e.g. "block", "the knife", "an empty area on the
designated location") are templated and occasionally hallucinated (e.g. "the
handle of the napkin"). This script uses GPT-4o with vision to rewrite each
hint as a richer, visually grounded noun phrase that mirrors the rules
embedded in PLANNING_SYSTEM_PROMPT (utils/prompt_utils.py).

For each episode under data/processed/<dataset>/episode_*/:
  - reads plan.json + rgb_0.png
  - for each step, calls GPT-4o with the image + step context (action, target,
    destination, old hint, scene_objects, task)
  - writes plan_v2.json next to plan.json (does NOT modify the original)

Setup:
    pip install "openai>=1.40"
    export OPENAI_API_KEY=sk-...
    # Optional: point at an OpenAI-compatible relay (yunwu.ai, one-api, etc.)
    export OPENAI_BASE_URL=https://yunwu.ai/v1

Usage:
    # rlbench pilot, 20 concurrent requests
    python scripts/refine_hints_gpt4.py \\
        --data-root data/processed/rlbench \\
        --concurrency 20

    # dry-run on first 5 episodes to sanity-check the prompt
    python scripts/refine_hints_gpt4.py \\
        --data-root data/processed/rlbench \\
        --limit 5 --dry-run

    # resume (skips episodes that already have plan_v2.json)
    python scripts/refine_hints_gpt4.py --data-root data/processed/rlbench
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import copy
import json
import os
import sys
from pathlib import Path

try:
    from openai import AsyncOpenAI
    from openai import APIError, APITimeoutError, RateLimitError
except ImportError:
    print("ERROR: openai package not installed. Run: pip install 'openai>=1.40'",
          file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Prompt — mirrors PLANNING_SYSTEM_PROMPT rules so train/inference distributions match
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a labeling assistant for a robotic manipulation dataset. Your job is to rewrite the `affordance_hint` field of one manipulation step into a richer, visually grounded noun phrase.

The hint you produce will be used to train a vision-language model and will be passed to GroundingDINO at inference time, so it must be a SPECIFIC, VISUALLY DISTINCTIVE noun phrase — never a template.

Rules (follow ALL of them):

1. LOOK AT THE IMAGE FIRST. Name a part that actually exists on the visible object. NEVER invent a part that isn't there.
   - A bowl has no handle. Write "the rim of the red bowl", NOT "the handle of the red bowl".
   - A ball has no grip. Write "the body of the yellow ball".
   - A bottle without a handle has a neck. Write "the neck of the green bottle".
   - A napkin / cloth / sponge has no handle. Use "the body of the X" or "the corner of the X".

2. ADD A DISCRIMINATIVE MODIFIER. Include at least one of: color, material, position (left/right/front/back/top), size, or relation to another visible object. Especially required when more than one similar object is visible.

3. MATCH THE PART TO THE ACTION (guideline — pick whichever grip-able feature is actually visible):
   - reach / release: the object itself or its main body
   - grasp / pick / lift / pull / open / close: prefer handle / knob / lid-grip / neck / stem / spout if visible, otherwise rim / edge / body. Do NOT default to "the handle of X" when X has no visible handle.
   - place / transport: an empty area on the destination surface
   - insert: the top opening or slot of the destination
   - pour: the inside / mouth of the destination container
   - push / press: the center of the contact face
   - rotate / flip: the body of the object
   - wipe: the surface being wiped

4. FOR DESTINATION-BEARING ACTIONS (transport / place / insert / pour) describe the DESTINATION, not the held object.

5. KEEP IT SHORT. 4-15 words. No sentences, no punctuation except hyphens. Output a single noun phrase starting with "the".

6. IF THE IMAGE DOESN'T CLEARLY SHOW THE TARGET, fall back to a minimally enriched version of the old hint (e.g. add the color from the task description if known, otherwise return the old hint unchanged).

Output strictly as JSON: {"hint": "...", "confidence": "high" | "medium" | "low"}
"""


def build_user_prompt(task: str, action: str, target: str,
                      destination: str | None, old_hint: str,
                      scene_objects: list[str]) -> str:
    """Build the per-step user message text."""
    lines = [
        f"Task: {task}",
        f"Action: {action}",
        f"Target object: {target}",
    ]
    if destination:
        lines.append(f"Destination: {destination}")
    if scene_objects:
        lines.append(f"Scene objects: {', '.join(scene_objects)}")
    lines.append(f"Original (templated) hint: \"{old_hint}\"")
    lines.append("")
    lines.append("Rewrite the hint following the rules. Output JSON only.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_hint(new_hint: str, old_hint: str, target: str,
                  destination: str | None) -> tuple[bool, str]:
    """Light validation. Returns (is_valid, reason).

    The goal is to reject obvious junk, not to second-guess GPT-4o on visual
    grounding. If the model says "low" confidence we keep the result but mark it.
    """
    if not new_hint or not isinstance(new_hint, str):
        return False, "empty or non-string"
    h = new_hint.strip().lower()
    if len(h) < 3:
        return False, "too short"
    if len(h.split()) > 25:
        return False, "too long (>25 words)"
    if "\n" in new_hint or '"' in new_hint:
        return False, "contains newline or quote"
    # Sanity: hint should mention the relevant object (target or destination
    # depending on action). Use word stems to allow plurals/variants.
    relevant = (destination or target).lower().replace("_", " ")
    relevant_tokens = [t for t in relevant.split() if len(t) > 2]
    if relevant_tokens and not any(tok in h for tok in relevant_tokens):
        return False, f"missing relevant token from '{relevant}'"
    return True, "ok"


# ---------------------------------------------------------------------------
# OpenAI call (with retry)
# ---------------------------------------------------------------------------

DESTINATION_ACTIONS = {"transport", "place", "insert", "pour"}


async def refine_one_step(
    client: AsyncOpenAI,
    image_b64: str,
    task: str,
    step: dict,
    scene_objects: list[str],
    model: str,
    max_retries: int = 3,
) -> tuple[str, str]:
    """Refine a single step's affordance_hint. Returns (new_hint, confidence)."""
    action = step.get("action", "")
    target = step.get("target", "")
    destination = step.get("destination")
    old_hint = step.get("affordance_hint", "")

    user_text = build_user_prompt(
        task=task, action=action, target=target,
        destination=destination, old_hint=old_hint,
        scene_objects=scene_objects,
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_b64}",
                        "detail": "low",
                    },
                },
            ],
        },
    ]

    backoff = 2.0
    for attempt in range(max_retries):
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                max_tokens=120,
                temperature=0.2,
            )
            raw = resp.choices[0].message.content or "{}"
            parsed = json.loads(raw)
            new_hint = parsed.get("hint", "").strip()
            confidence = parsed.get("confidence", "medium").strip().lower()

            # Decide which object is "relevant" for validation
            check_dest = destination if action in DESTINATION_ACTIONS else None
            ok, reason = validate_hint(new_hint, old_hint, target, check_dest)
            if ok:
                return new_hint, confidence
            # Validation failed — keep old hint and mark
            return old_hint, f"rejected:{reason}"

        except (APIError, APITimeoutError, RateLimitError) as e:
            if attempt == max_retries - 1:
                return old_hint, f"api_error:{type(e).__name__}"
            await asyncio.sleep(backoff)
            backoff *= 2
        except (json.JSONDecodeError, KeyError) as e:
            return old_hint, f"parse_error:{type(e).__name__}"

    return old_hint, "max_retries"


# ---------------------------------------------------------------------------
# Episode processing
# ---------------------------------------------------------------------------

def encode_image_b64(image_path: Path, max_dim: int = 768) -> str:
    """Encode image to base64, downscaling to keep token cost low."""
    from PIL import Image
    import io
    img = Image.open(image_path).convert("RGB")
    # Downscale (preserve aspect ratio) so GPT-4o uses cheaper image tokens
    img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


async def process_episode(
    client: AsyncOpenAI,
    episode_dir: Path,
    model: str,
    dry_run: bool,
    sem: asyncio.Semaphore,
) -> dict:
    """Refine all hints in one episode's plan.json. Returns stats dict."""
    plan_path = episode_dir / "plan.json"
    out_path = episode_dir / "plan_v2.json"
    image_path = episode_dir / "rgb_0.png"

    if out_path.exists():
        return {"episode": episode_dir.name, "status": "skipped_exists"}
    if not plan_path.exists() or not image_path.exists():
        return {"episode": episode_dir.name, "status": "skipped_missing_files"}

    with open(plan_path) as f:
        plan = json.load(f)
    task = plan.get("task", "")
    scene_objects = plan.get("scene_objects", [])

    image_b64 = encode_image_b64(image_path)

    new_plan = copy.deepcopy(plan)
    stats = {
        "episode": episode_dir.name, "status": "ok",
        "refined": 0, "rejected": 0, "errored": 0, "steps": [],
    }

    # Refine all steps in this episode in parallel (still under the global semaphore)
    async def run_step(step):
        async with sem:
            return await refine_one_step(
                client, image_b64, task, step, scene_objects, model,
            )

    tasks = [run_step(step) for step in new_plan.get("steps", [])]
    results = await asyncio.gather(*tasks)

    for step, (new_hint, confidence) in zip(new_plan["steps"], results):
        old_hint = step.get("affordance_hint", "")
        step["affordance_hint_original"] = old_hint
        step["affordance_hint"] = new_hint
        step["affordance_hint_confidence"] = confidence
        stats["steps"].append({
            "action": step.get("action"), "old": old_hint, "new": new_hint,
            "confidence": confidence,
        })
        if confidence.startswith("rejected") or confidence.startswith("api_error"):
            if "rejected" in confidence:
                stats["rejected"] += 1
            else:
                stats["errored"] += 1
        else:
            stats["refined"] += 1

    if not dry_run:
        with open(out_path, "w") as f:
            json.dump(new_plan, f, indent=2, ensure_ascii=False)

    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main_async(args):
    if "OPENAI_API_KEY" not in os.environ:
        print("ERROR: OPENAI_API_KEY not set in env.", file=sys.stderr)
        sys.exit(1)

    # AsyncOpenAI() reads OPENAI_API_KEY and OPENAI_BASE_URL from env automatically;
    # --base-url overrides if explicitly passed.
    client_kwargs = {}
    if args.base_url:
        client_kwargs["base_url"] = args.base_url
    client = AsyncOpenAI(**client_kwargs)
    if args.base_url or os.environ.get("OPENAI_BASE_URL"):
        print(f"Using base_url: {args.base_url or os.environ.get('OPENAI_BASE_URL')}")

    data_root = Path(args.data_root)
    episodes = sorted(
        d for d in data_root.iterdir()
        if d.is_dir() and d.name.startswith("episode_")
    )
    if args.limit:
        episodes = episodes[: args.limit]

    print(f"Found {len(episodes)} episodes under {data_root}")
    print(f"Model: {args.model} | Concurrency: {args.concurrency} | "
          f"Dry-run: {args.dry_run}")

    sem = asyncio.Semaphore(args.concurrency)

    # Process all episodes; per-episode parallelism is bounded by the semaphore
    totals = {"refined": 0, "rejected": 0, "errored": 0,
              "skipped": 0, "episodes": 0}
    print_every = max(1, len(episodes) // 50)

    for i, ep in enumerate(episodes):
        stats = await process_episode(
            client, ep, args.model, args.dry_run, sem,
        )
        totals["episodes"] += 1
        if stats["status"].startswith("skipped"):
            totals["skipped"] += 1
        else:
            totals["refined"] += stats.get("refined", 0)
            totals["rejected"] += stats.get("rejected", 0)
            totals["errored"] += stats.get("errored", 0)

        if args.verbose or (i % print_every == 0):
            print(f"[{i+1}/{len(episodes)}] {ep.name}: {stats['status']} "
                  f"refined={stats.get('refined', 0)} "
                  f"rejected={stats.get('rejected', 0)} "
                  f"errored={stats.get('errored', 0)}")
            if args.verbose and stats.get("steps"):
                for s in stats["steps"]:
                    print(f"   [{s['action']:10s}] {s['old']!r:40s} -> "
                          f"{s['new']!r} ({s['confidence']})")

    print("\n=== Totals ===")
    print(json.dumps(totals, indent=2))


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-root", required=True,
                   help="e.g. data/processed/rlbench")
    p.add_argument("--model", default="gpt-4o",
                   help="OpenAI vision model (default: gpt-4o)")
    p.add_argument("--base-url", default=None,
                   help="Override base URL (else uses OPENAI_BASE_URL env var, "
                        "else OpenAI default). e.g. https://yunwu.ai/v1")
    p.add_argument("--concurrency", type=int, default=20,
                   help="Max concurrent API calls (default: 20)")
    p.add_argument("--limit", type=int, default=None,
                   help="Limit number of episodes (for testing)")
    p.add_argument("--dry-run", action="store_true",
                   help="Run refinement but do not write plan_v2.json")
    p.add_argument("--verbose", action="store_true",
                   help="Print per-step before/after")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main_async(parse_args()))
