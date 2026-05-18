#!/usr/bin/env python3
"""Reasoning-first plan generation (V2).

Generates a complete, causally-coherent plan from scratch given (image, task):
  reasoning -> scene_objects -> steps[*] -> goal

Differences from generate_plans.py (V1):
  - Reasoning leads, plan follows. The reasoning is causal, not post-hoc.
  - No [u,v] pixel coordinates. Steps emit semantic affordance_region only.
  - Goal uses LIFTED predicates (set/quantified) for interchangeable objects,
    so VLA can satisfy the task with any valid permutation.
  - Stronger predicate vocabulary discipline.

Output is written to plan_v2.json (NOT plan.json) so we don't overwrite the
existing V1 annotation. The loader can be switched via prefer_v2=True.

Usage:
    export OPENAI_API_KEY=sk-...
    export OPENAI_BASE_URL=https://yunwu.ai/v1
    export PLAN_V2_MODEL=gpt-5-mini

    # Dry-run on 5 representative episodes (prints, no save)
    python scripts/generate_plans_v2.py --samples scripts/samples_v2_dryrun.txt --dry_run

    # Resume across all datasets
    python scripts/generate_plans_v2.py --all --resume --workers 4
"""

import argparse
import base64
import json
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from openai import OpenAI, RateLimitError

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("OPENAI_API_KEY")
if not API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY environment variable is not set. "
        "Export it before running: export OPENAI_API_KEY=sk-..."
    )
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://yunwu.ai/v1")
MODEL = os.environ.get("PLAN_V2_MODEL", "gpt-5-mini")
DATA_ROOT = Path(__file__).parent.parent / "data" / "processed"
OUTPUT_FILENAME = "plan_v2.json"

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert robotics task planner. Given an image of a tabletop scene \
and a natural-language task, produce a complete manipulation plan as a single \
JSON object.

Think causally: first analyze the scene, then derive the plan from that \
analysis. Do NOT write a plan and then rationalize it afterwards.

OUTPUT SCHEMA — a single JSON object with these fields:

{
  "reasoning": "<200-word causal analysis in English with 3 labeled sections>",
  "scene_objects": ["obj_1", "obj_2", ...],
  "steps": [
    {
      "step": 1,
      "action": "<verb>",
      "target": "<object_name>",
      "destination": "<object_name or empty string>",
      "affordance_region": "<semantic region phrase, NO coordinates>",
      "constraints": {
        "contact":   [{"pred": "...", "args": [...], "role": "..."}, ...],
        "spatial":   [...],
        "pose":      [...],
        "direction": [...],
        "safety":    [...]
      },
      "done_when": "<boolean expression over predicates>"
    },
    ...
  ],
  "goal": [{"pred": "...", "args": [...]}, ...]
}

REASONING (field "reasoning"): three labeled sections, in this order:
  (1) SCENE ANALYSIS — name task-relevant objects, spatial relations, and \
physical properties (deformable, fragile, articulated, liquid-containing, \
slippery, transparent).
  (2) STRATEGY — what to manipulate, in what order, and WHY this order (or \
why order is interchangeable); note failure modes.
  (3) AFFORDANCE REASONING — for each step, justify the chosen region by \
function (grip stability, force application, clearance, contact area).

ACTION VOCABULARY (use ONLY these verbs):
  reach, grasp, release, transport, place, push, pull, press, rotate, \
insert, pour, open, close, lift, lower

PREDICATE VOCABULARY (use ONLY these in constraints, done_when, goal):
  contact:   holding(obj), released(obj), surface_contact(obj1, obj2), \
gripper_contact(obj), gripper_state(open|closed), inserted(obj, container)
  spatial:   on(obj, surface), above(obj1, obj2, gap), inside(obj1, container), \
aligned_xy(obj1, obj2, tol), distance(obj1, obj2, op, val), \
stacked_height(obj_set, op, val)
  pose:      stable(obj), upright(obj), level(obj), closed(obj), open(obj)
  direction: grasp_axis(x, y, z), approach_axis(x, y, z)
  safety:    support_stable(obj), no_collision(obj1, obj2), no_drop(obj)

LIFTED predicates (goal only — for interchangeable / set tasks):
  stacked(obj_set)              — any total order of obj_set forming a stack
  stacked_with_base(obj_set, base) — base is at bottom, rest in any order
  all_inside(obj_set, container)
  all_on(obj_set, surface)
  any_in(obj_set, container_set)
  paired(obj_set1, obj_set2, rel)
Bound runtime variables you may use as args: __top_of_stack__, __any__, \
__chosen__.

CONSTRAINT ROLES (role field): "completion" (must be true to call step done), \
"progress" (preferred during step but not strict), "safety" (must hold the \
entire step).

GOAL DESIGN RULES — extremely important:
  1. If multiple objects of the same type/role are interchangeable, write \
goal with SET arguments using lifted predicates, NEVER chain grounded on(...).
  2. Use __top_of_stack__ etc. when the task says "any X" rather than "specific X".
  3. Reserve grounded predicates ONLY when the task language demands order \
("stack red on blue, then green on red").
  4. Be MINIMAL: only predicates that MUST hold at completion.
  5. MUTUALLY-EXCLUSIVE PREDICATES — do NOT combine these in one goal:
     - stacked(S) and all_on(S, surface): a stack puts only the base on \
the surface; the rest are on the base, NOT on the surface.
     - on(A, B) and on(A, C) for the same A: an object can be on only one \
direct support at a time.
     - inserted(A, B) and on(A, C): once inserted, not on a separate surface.
  6. Goal length: prefer 1-3 predicates. If you need more, you are probably \
listing transient or per-step conditions — keep only true terminal ones.
  7. LIFTED PREDICATE CARDINALITY — lifted predicates (stacked, all_on, \
all_inside, any_in, paired) require a SET argument of size >= 2. If only \
ONE object would go in the set, COLLAPSE to the grounded form:
     - all_inside([duck], pot)         -> inside(duck, pot)
     - all_on([book], shelf)           -> on(book, shelf)
     - stacked([bowl])                  -> on(bowl, surface) instead
     - any_in([cup], [shelf])           -> inside(cup, shelf)
  8. BOUND-VARIABLE GROUNDING — bound variables are placeholders the MPC \
resolves at runtime; they MUST have a clear grounding source:
     - __top_of_stack__: allowed ONLY in goals that also contain stacked(S); \
MPC binds it to the last element of S in the chosen permutation.
     - __any__ / __chosen__: only for ENUMERABLE sets that are themselves \
listed in scene_objects (e.g., __any__ of [bowl_red, bowl_blue, bowl_green]).
     - For SUBSTANCES (liquids, granules, food contents) that are not \
discretely enumerable, treat the substance as a single mass-noun object: \
add a name like "almonds", "water", "rice" to scene_objects and write \
inside(almonds, pot) — NEVER inside(__any__, pot).

DONE_WHEN: a boolean expression using the same predicates, joined by AND/OR. \
Each step's done_when should reference its own completion-role constraints.

OUTPUT FORMAT: a SINGLE JSON object. No markdown. No code fences. No preamble.

FEW-SHOT EXAMPLES:

# Example 1: single-object pick-place (grounded goal)
Task: "Move the silver pot to the front-left corner"
Output:
{
  "reasoning": "SCENE ANALYSIS - Silver_pot sits center-right, behind red_can; \
table is wooden, front-left corner is empty. STRATEGY - reach pot handle, \
grasp at handle for stability, transport leftward avoiding red_can, place at \
front-left corner. Failure modes: collision with red_can, tipping. AFFORDANCE \
REASONING - handle gives moment arm; flat base for stable placement.",
  "scene_objects": ["silver_pot", "red_can", "table"],
  "steps": [
    {"step": 1, "action": "reach", "target": "silver_pot", "destination": "",
     "affordance_region": "the handle of the silver pot",
     "constraints": {
       "contact": [{"pred": "gripper_state", "args": ["open"], "role": "progress"}],
       "spatial": [{"pred": "distance", "args": ["gripper", "silver_pot", "<", 0.03], "role": "completion"}],
       "safety":  [{"pred": "no_collision", "args": ["gripper", "red_can"], "role": "safety"}]
     },
     "done_when": "distance(gripper, silver_pot) < 0.03 AND gripper_state(open)"},
    {"step": 2, "action": "grasp", "target": "silver_pot", "destination": "",
     "affordance_region": "the handle of the silver pot",
     "constraints": {
       "contact": [{"pred": "holding", "args": ["silver_pot"], "role": "completion"}]
     },
     "done_when": "holding(silver_pot)"},
    {"step": 3, "action": "place", "target": "silver_pot", "destination": "table",
     "affordance_region": "the front-left corner of the table",
     "constraints": {
       "contact": [{"pred": "surface_contact", "args": ["silver_pot", "table"], "role": "completion"},
                   {"pred": "released", "args": ["silver_pot"], "role": "completion"}],
       "pose":    [{"pred": "stable", "args": ["silver_pot"], "role": "completion"}]
     },
     "done_when": "surface_contact(silver_pot, table) AND released(silver_pot) AND stable(silver_pot)"}
  ],
  "goal": [
    {"pred": "on", "args": ["silver_pot", "table"]},
    {"pred": "stable", "args": ["silver_pot"]}
  ]
}

# Example 2: stack three distinguishable bowls (LIFTED goal — any permutation valid)
Task: "Stack the three bowls"
Output goal section:
  "goal": [
    {"pred": "stacked", "args": [["blue_bowl", "red_bowl", "green_bowl"]]},
    {"pred": "stable", "args": ["__top_of_stack__"]}
  ]
NOTE: steps may pick a concrete order (e.g., blue base, red middle, green top) \
as warm-start for VLA, but goal stays lifted so any execution order succeeds.

# Example 3: ordered (grounded goal)
Task: "Stack the red bowl on the blue, then the green on the red"
Output goal section:
  "goal": [
    {"pred": "on", "args": ["red_bowl", "blue_bowl"]},
    {"pred": "on", "args": ["green_bowl", "red_bowl"]},
    {"pred": "stable", "args": ["green_bowl"]}
  ]

# Example 4: collection task (lifted, container)
Task: "Put all the toys in the box"
Output goal section:
  "goal": [
    {"pred": "all_inside", "args": [["toy_car", "toy_block", "toy_duck"], "box"]}
  ]

# Example 5: open-then-insert (mixed)
Task: "Put the lid on the jar"
Output goal section:
  "goal": [
    {"pred": "inserted", "args": ["lid", "jar"]},
    {"pred": "closed", "args": ["jar"]}
  ]
"""

USER_TEMPLATE = """\
Task: "{task}"

Analyze the scene image and produce the complete plan JSON object."""


def encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _extract_json(text: str) -> dict | None:
    """Best-effort: strip markdown fences, locate the first JSON object."""
    import re as _re
    m = _re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, _re.DOTALL)
    if m:
        text = m.group(1)
    m = _re.search(r"\{.*\}", text, _re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _validate_plan(plan: dict) -> tuple[bool, str]:
    """Light structural validation; returns (ok, reason)."""
    for key in ("reasoning", "scene_objects", "steps", "goal"):
        if key not in plan:
            return False, f"missing field '{key}'"
    if not isinstance(plan["reasoning"], str) or len(plan["reasoning"]) < 50:
        return False, "reasoning too short"
    if not isinstance(plan["steps"], list) or not plan["steps"]:
        return False, "steps empty/invalid"
    if not isinstance(plan["goal"], list) or not plan["goal"]:
        return False, "goal empty/invalid"
    for i, s in enumerate(plan["steps"]):
        if not isinstance(s, dict):
            return False, f"step {i} not a dict"
        for k in ("action", "target", "affordance_region", "done_when"):
            if k not in s:
                return False, f"step {i} missing '{k}'"
    return True, ""


def generate_plan_v2(
    client: OpenAI, image_path: str, task: str,
    retries: int = 2, rl_retries: int = 8,
) -> dict | None:
    """Call the chat model, return the parsed plan dict or None on failure."""
    img_b64 = encode_image(image_path)
    user_text = USER_TEMPLATE.format(task=task)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                {"type": "text", "text": user_text},
            ],
        },
    ]

    attempt = 0
    rl_attempts = 0
    while True:
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                # gpt-5-mini can spend the entire max_tokens budget on
                # internal reasoning (reasoning_tokens) and produce empty
                # visible output. reasoning_effort="minimal" caps the
                # hidden reasoning so the budget is spent on the JSON.
                # 8192 covers tasks with 8+ steps and long reasoning;
                # initial 4096 ran out for ~0.8% of episodes.
                max_tokens=8192,
                temperature=0.4,
                reasoning_effort="minimal",
            )
            text = (resp.choices[0].message.content or "").strip()
            if len(text) < 100:
                if attempt < retries:
                    attempt += 1
                    time.sleep(1)
                    continue
                print(
                    f"    EMPTY ({image_path}): finish={resp.choices[0].finish_reason}, "
                    f"usage={resp.usage}",
                    flush=True,
                )
                return None

            obj = _extract_json(text)
            if obj is None or not isinstance(obj, dict):
                if attempt < retries:
                    attempt += 1
                    time.sleep(1)
                    continue
                print(f"    JSON_PARSE_FAIL ({image_path})", flush=True)
                return None

            ok, reason = _validate_plan(obj)
            if not ok:
                if attempt < retries:
                    attempt += 1
                    time.sleep(1)
                    continue
                print(f"    VALIDATION_FAIL ({image_path}): {reason}", flush=True)
                return None

            return obj

        except RateLimitError:
            if rl_attempts < rl_retries:
                wait = min(120, 5 * (2 ** rl_attempts)) + random.uniform(0, 3)
                rl_attempts += 1
                time.sleep(wait)
                continue
            print(f"    RATE_LIMIT_EXHAUSTED ({image_path})", flush=True)
            return None
        except Exception as e:
            if attempt < retries:
                attempt += 1
                time.sleep(2 ** attempt)
                continue
            print(f"    ERROR ({image_path}): {e}", flush=True)
            return None


def process_episode(
    client: OpenAI, ep_dir: Path, dry_run: bool = False
) -> tuple[str, bool]:
    """Generate a V2 plan for one episode and write plan_v2.json."""
    plan_path = ep_dir / "plan.json"
    image_path = ep_dir / "rgb_0.png"
    if not plan_path.exists() or not image_path.exists():
        return (ep_dir.name, False)

    # Need the task description from the existing plan.json (or meta.json).
    try:
        existing = json.loads(plan_path.read_text())
    except Exception:
        existing = {}
    task = existing.get("task", "")
    if not task:
        meta_path = ep_dir / "meta.json"
        if meta_path.exists():
            try:
                task = json.loads(meta_path.read_text()).get("task", "")
            except Exception:
                pass
    if not task:
        return (ep_dir.name, False)

    plan = generate_plan_v2(client, str(image_path), task)
    if plan is None:
        return (ep_dir.name, False)

    if dry_run:
        print(f"\n{'='*70}")
        print(f"Episode: {ep_dir}")
        print(f"Task: {task}")
        print(f"\nReasoning ({len(plan['reasoning'].split())} words):")
        print(plan["reasoning"])
        print(f"\nScene objects: {plan['scene_objects']}")
        print(f"\nSteps ({len(plan['steps'])}):")
        for s in plan["steps"]:
            dest = f" -> {s['destination']}" if s.get("destination") else ""
            print(f"  {s['step']}. {s['action']}({s['target']}{dest})")
            print(f"     region: {s['affordance_region']}")
            print(f"     done_when: {s['done_when']}")
        print(f"\nGoal ({len(plan['goal'])} predicates):")
        for g in plan["goal"]:
            print(f"  - {g['pred']}({', '.join(str(a) for a in g['args'])})")
        print(f"{'='*70}")
        return (ep_dir.name, True)

    # Carry forward task (for self-containment) and write to plan_v2.json.
    plan["task"] = task
    out_path = ep_dir / OUTPUT_FILENAME
    out_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
    return (ep_dir.name, True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def collect_episodes(args) -> list[Path]:
    """Gather episode directories based on CLI args."""
    if args.samples:
        # Sample-list file: one absolute or relative-to-DATA_ROOT path per line.
        out = []
        for line in Path(args.samples).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            p = Path(line)
            if not p.is_absolute():
                p = DATA_ROOT / line
            if p.exists() and (p / "plan.json").exists():
                out.append(p)
        return out

    if args.all:
        datasets = sorted(d for d in DATA_ROOT.iterdir() if d.is_dir())
    else:
        ds_dir = DATA_ROOT / args.dataset
        if not ds_dir.exists():
            print(f"ERROR: {ds_dir} not found")
            sys.exit(1)
        datasets = [ds_dir]

    episodes = []
    for ds_dir in datasets:
        eps = sorted(
            e for e in ds_dir.iterdir()
            if e.is_dir() and e.name.startswith("episode_") and (e / "plan.json").exists()
        )
        episodes.extend(eps)

    if args.end > 0:
        episodes = episodes[args.start:args.end]
    elif args.start > 0:
        episodes = episodes[args.start:]

    if args.resume:
        def _needs(ep: Path) -> bool:
            out = ep / OUTPUT_FILENAME
            if not out.exists():
                return True
            try:
                p = json.loads(out.read_text())
                ok, _ = _validate_plan(p)
                return not ok
            except Exception:
                return True
        episodes = [ep for ep in episodes if _needs(ep)]

    return episodes


def main():
    global MODEL
    parser = argparse.ArgumentParser(description="V2 reasoning-first plan generation")
    parser.add_argument("--dataset", default="rlbench")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--samples", type=str, default=None,
                        help="File with episode paths, one per line (for dry-run subset)")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=-1)
    parser.add_argument("--resume", action="store_true",
                        help="Skip episodes that already have a valid plan_v2.json")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--dry_run", action="store_true",
                        help="Print plans, do not save")
    args = parser.parse_args()

    if args.model:
        MODEL = args.model

    episodes = collect_episodes(args)
    print(f"Episodes to process: {len(episodes)}")
    print(f"Model: {MODEL}")
    print(f"Base URL: {BASE_URL}")
    print(f"Workers: {args.workers}")
    print(f"Output: {OUTPUT_FILENAME}")
    print()

    if not episodes:
        print("Nothing to do.")
        return

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    if args.dry_run:
        for ep in episodes:
            process_episode(client, ep, dry_run=True)
        return

    success = 0
    failed = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_episode, client, ep): ep for ep in episodes}
        for i, future in enumerate(as_completed(futures), 1):
            ep_id, ok = future.result()
            if ok:
                success += 1
            else:
                failed += 1
                print(f"  FAILED: {ep_id}", flush=True)
            if i % 50 == 0 or i == len(episodes):
                elapsed = time.time() - t0
                rate = i / elapsed if elapsed > 0 else 0
                eta = (len(episodes) - i) / rate if rate > 0 else 0
                print(
                    f"  [{i}/{len(episodes)}] ok={success} fail={failed} "
                    f"rate={rate:.2f}/s ETA={eta/60:.0f}min",
                    flush=True,
                )

    elapsed = time.time() - t0
    print(f"\nDone: {success} success, {failed} failed, {elapsed:.0f}s total")


if __name__ == "__main__":
    main()
