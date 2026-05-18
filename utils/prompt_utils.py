"""Prompt utilities for RoboBrain-3DGS training and inference.

Aligns with RoboBrain2.5's Qwen3-VL chat template protocol:
  - <|im_start|>system\n{system_prompt}<|im_end|>
  - <|im_start|>user\n{task_prompt}<|im_end|>
  - <|im_start|>assistant\n{target}<|im_end|>

Key design decisions:
  1. Use apply_chat_template() to match the pretrained model's distribution
  2. Task-specific prompt augmentation matching RoboBrain2.5's inference.py
  3. Label masking: only assistant response tokens contribute to loss
  4. System prompt is optional (the pretrained model supports it)

Reference: /home/w50037733/RoboBrain2.5/inference.py (official inference patterns)
"""

import re

import torch


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_SYSTEM_PROMPT = (
    "You are RoboBrain, an embodied AI assistant specialized in robotic "
    "manipulation. Given an image of a scene with 3D spatial understanding, "
    "provide precise affordance predictions and manipulation constraints."
)

PLANNING_SYSTEM_PROMPT = (
    "You are RoboBrain, an embodied AI assistant with 3D spatial understanding "
    "specialized in robotic manipulation planning. "
    "Given a scene image and a task instruction, output a structured task "
    "decomposition.\n\n"
    "OUTPUT PROTOCOL — follow this order exactly:\n"
    "  1) Reason inside a single <think>...</think> block. Cover scene "
    "analysis (visible objects, spatial relations, material properties), "
    "strategy (ordering, failure modes), and affordance reasoning (which "
    "part to interact with at each step). The reasoning must causally "
    "drive the plan that follows — do NOT rationalize after the fact.\n"
    "  2) Emit a single 'Goal:' line listing lifted goal predicates (e.g. "
    "stacked([cup_a, cup_b])), separated by ';'. The goal is the sole "
    "termination criterion — it is evaluated continuously by the controller "
    "and is order-invariant. Use lifted set-level predicates (stacked, "
    "all_inside, all_on, any_in) when multiple permutations satisfy the "
    "task; use grounded predicates (on(A, B), inside(A, B)) only for "
    "singleton goals.\n"
    "  3) Emit 'Scene: obj1, obj2, ...' listing scene-relevant objects.\n"
    "  4) For each step (2–5 primitives): 'Step N: action(target [-> dest])' "
    "header, then indented lines for affordance_region, constraint categories "
    "(contact / spatial / pose / direction / safety) with role labels "
    "(completion / safety / progress), and done_when.\n\n"
    "AFFORDANCE GROUNDING: instead of numeric [u, v] coordinates, write a "
    "natural-language 'affordance_region:' description of the functional "
    "part to interact with. A downstream open-vocabulary grounding model "
    "(Lang-SAM) resolves the region to pixel coordinates at execution time, "
    "so the description must be SPECIFIC and VISUALLY DISTINCTIVE:\n"
    "  - Name a part that actually exists in the image. NEVER invent a part "
    "(a bowl has no handle — write 'the rim of the red bowl', not 'the "
    "handle of the red bowl'). A ball has no grip — write 'the body of "
    "the yellow ball'.\n"
    "  - Add a discriminative modifier (color, material, position, size, "
    "or relation to another object) whenever the scene contains more than "
    "one similar object.\n"
    "  - Match the part to the action: reach/release → the object body; "
    "grasp/pick/lift/pull → a grip-able feature (handle / knob / rim / "
    "neck / stem); place/transport → an empty area on the destination; "
    "insert → top opening of destination; pour → mouth of container; "
    "push/press → center of contact face; rotate/flip → object body.\n"
    "  - For destination-bearing actions (transport / place / insert / "
    "pour) the region describes the DESTINATION, not the held object.\n\n"
    "Approach direction goes inside the 'direction:' constraint category "
    "(e.g. 'direction: approach_axis(0, 0, -1)'), not as a separate line."
)

DEFAULT_TASK_TYPE = "affordance"

# Marker that separates prompt from assistant response in the chat template
_ASSISTANT_MARKER = "<|im_start|>assistant\n"


# ---------------------------------------------------------------------------
# Task-specific prompt templates (matching RoboBrain2.5's inference.py)
# ---------------------------------------------------------------------------

TASK_TEMPLATES = {
    # Affordance prediction: our primary training task.
    # Idea-B-aware: ask for the semantic part description BEFORE the coordinate
    # so the language head conditions the visual head — reduces center bias.
    "affordance": (
        "{text}. Please predict the affordance point and manipulation "
        "constraints for completing this task. First describe the semantic "
        "part to interact with as 'affordance_hint: <part description>'. "
        "The hint must be a specific, visually distinctive noun phrase — "
        "name a part that actually exists on the object (do NOT invent a "
        "handle on a handle-less object like a bowl, plate, or ball) and "
        "include a discriminative modifier (color, material, position, or "
        "relation to another object) whenever the scene has multiple "
        "similar objects. Then output the affordance coordinates as [u, v] "
        "in normalized image space, gripper_width, and approach vector as "
        "[x, y, z]."
    ),
    # Pointing: RoboBrain2.5's pointing task (2D coordinate output)
    "pointing": (
        "{text}. Please provide its 2D coordinates. Your answer should be "
        "formatted as a tuple, i.e. [(x, y)], where the tuple contains the "
        "x and y coordinates of a point satisfying the conditions above."
    ),
    # Trajectory: RoboBrain2.5's 3D trajectory prediction
    "trajectory": (
        "Please predict 3D end-effector-centric waypoints to complete the "
        'task successfully. The task is "{text}". Your answer should be '
        "formatted as a list of tuples, i.e., [(x1, y1, d1), (x2, y2, d2), "
        "...], where each tuple contains the x and y coordinates and the "
        "depth of the point."
    ),
    # Grounding: bounding box prediction
    "grounding": (
        "Please provide the bounding box coordinate of the region this "
        "sentence describes: {text}."
    ),
    # Task planning: V2 protocol — reasoning leads inside <think>, then Goal,
    # Scene, and per-step affordance_region + categorized constraints + done_when.
    # No numeric [u, v] coordinates — Lang-SAM grounds affordance_region at runtime.
    "planning": (
        'Plan the manipulation steps to complete the task: "{text}". '
        'First, reason inside a single <think>...</think> block (scene '
        'analysis, strategy, affordance reasoning). Then output: a single '
        '"Goal:" line with lifted goal predicates (sole termination '
        'criterion, order-invariant), a "Scene:" object list, and 2–5 '
        '"Step N: action(target [-> dest])" blocks. Each step has an '
        'indented affordance_region (specific, visually distinctive '
        'description of the functional part — never invent a part that '
        'is not in the image), constraints organized by category '
        '(contact / spatial / pose / direction / safety) with role labels '
        '(completion / safety / progress), and a done_when condition. '
        'Approach direction belongs inside the direction: category, not as '
        'a separate line.'
    ),
    # General VQA: pass through as-is
    "general": "{text}",
}


# ---------------------------------------------------------------------------
# Output parsing (shared by inference and evaluation)
# ---------------------------------------------------------------------------

_AFF_RE = re.compile(
    # Legacy [u, v] / [u=, v=] coords — V2 trained model no longer emits these
    # but the base model and any V1 LoRA still do.
    r"affordance[:\s]*\[\s*(?:u=)?([0-9.]+)[,\s]+(?:v=)?([0-9.]+)\s*\]", re.I,
)
# affordance_hint: legacy V1 field — kept for back-compat with base model.
_HINT_RE = re.compile(
    r"affordance_hint[:\s]+([^\n.]+?)(?=\s*(?:\n|\.|affordance[:\s]*\[))", re.I,
)
# affordance_region: V2 field — Lang-SAM resolves this to image coords at runtime.
# Captures to end of line; allow longer phrasing than the legacy hint.
_REGION_RE = re.compile(r"affordance_region[:\s]+(.+?)(?=\n|$)", re.I)
# <think>...</think> reasoning block (V2). DOTALL so it spans newlines.
_THINK_RE = re.compile(r"<think>(.*?)</think>", re.I | re.S)
# Goal: lifted predicate list (V2), one line.
_GOAL_LINE_RE = re.compile(r"^Goal:\s*(.+)$", re.I | re.M)
_WID_RE = re.compile(r"gripper_width\s*=\s*([0-9.]+)", re.I)
_APP_RE = re.compile(
    # Match both "[0, 0, -1]" and "[x=0, y=0, z=-1]"
    r"approach[=:\s]*\[\s*(?:x=)?([-0-9.e+]+)[,\s]+"
    r"(?:y=)?([-0-9.e+]+)[,\s]+(?:z=)?([-0-9.e+]+)\s*\]",
    re.I,
)


def parse_affordance_output(text: str) -> dict:
    """Parse affordance output into structured fields.

    Expected format::

        affordance_hint: the handle of the mug.
        affordance: [u, v]. constraint: gripper_width=X, approach=[x, y, z].

    Returns:
        dict with keys: u, v, gripper_width, approach, affordance_hint
        (each None if not found).
    """
    out: dict = {"u": None, "v": None, "gripper_width": None,
                 "approach": None, "affordance_hint": None}
    m = _AFF_RE.search(text)
    if m:
        out["u"] = float(m.group(1))
        out["v"] = float(m.group(2))
    m = _WID_RE.search(text)
    if m:
        out["gripper_width"] = float(m.group(1))
    m = _APP_RE.search(text)
    if m:
        out["approach"] = [float(m.group(i)) for i in range(1, 4)]
    m = _HINT_RE.search(text)
    if m:
        out["affordance_hint"] = m.group(1).strip().strip(".,;")
    return out


_STEP_RE = re.compile(
    r"Step\s+(\d+):\s*(\w+)\(([^)]*)\)", re.I,
)

# Matches "action(target -> destination)" pattern
_STEP_DEST_RE = re.compile(
    r"Step\s+(\d+):\s*(\w+)\((.+?)\s*->\s*(.+?)\)", re.I,
)

# Fallback for outputs where the model dropped the "Step N:" prefix and/or
# newlines (common with the base model on the compact-format prompt). We
# enumerate the manipulation primitives explicitly to avoid matching predicates
# like distance(...) or holding(...) inside constraint lines.
_ACTION_KW = (
    r"(?:reach|grasp|pick|lift|transport|place|push|pull|insert|pour|"
    r"rotate|release|flip|wipe|open|close|press)"
)
_STEP_FALLBACK_DEST_RE = re.compile(
    rf"\b({_ACTION_KW})\(\s*([^()]*?)\s*->\s*([^()]+?)\s*\)", re.I,
)
_STEP_FALLBACK_RE = re.compile(
    rf"\b({_ACTION_KW})\(\s*([^()]*)\s*\)", re.I,
)

# Matches constraint lines: "category: pred(args) [role]; pred(args) [role]"
_CONSTRAINT_CATEGORIES = {"contact", "spatial", "pose", "direction", "safety"}
_CONSTRAINT_LINE_RE = re.compile(
    r"^\s*(contact|spatial|pose|direction|safety):\s*(.+)$", re.I | re.M,
)
_PRED_RE = re.compile(
    r"(\w+)\(([^)]*)\)\s*(?:\[(\w+)\])?",
)

# Matches "Scene: obj1, obj2, ..." line
_SCENE_RE = re.compile(r"^Scene:\s*(.+)$", re.I | re.M)


def parse_planning_output(text: str) -> dict:
    """Parse task planning output into structured steps with constraints.

    V2 format (current training target)::

        <think>SCENE ANALYSIS - ... STRATEGY - ... AFFORDANCE REASONING - ...</think>
        Goal: stacked([cup_a, cup_b]); on(cup_a, table)
        Scene: cup_a, cup_b, table
        Step 1: reach(cup_a)
          affordance_region: the rim of the red cup
          contact: gripper_state(open) [progress]
          spatial: distance(gripper, cup_a, <, 0.03) [completion]
          direction: approach_axis(0, 0, -1) [progress]
          safety: no_collision(gripper, cup_b)
          done_when: distance(gripper, cup_a) < 0.03 AND gripper_state(open)

    V1 format (still parsed for base-model / legacy LoRA evals)::

        Step 1: reach(cup handle)
          affordance_hint: the handle of the red cup
          affordance: [0.35, 0.42], approach: [0, 1, 0]
          done_when: gripper_near(cup_handle)

    Returns:
        dict with keys: reasoning (str), goal (list of {pred, args}),
        scene_objects (list), steps (list). Each step has: step, action,
        target, destination?, affordance_region (V2) / affordance_hint (V1),
        affordance (V1 only), approach (V1 only), constraints (dict of
        category->list), done_when.
    """
    result = {"reasoning": "", "goal": [], "scene_objects": [], "steps": []}

    # Extract and strip <think>...</think> so step parsing never sees its
    # contents (reasoning text contains action keywords like "reach(" that
    # would otherwise be misparsed as steps by the fallback regex).
    think_m = _THINK_RE.search(text)
    if think_m:
        result["reasoning"] = think_m.group(1).strip()
        text = _THINK_RE.sub("", text)

    # Goal line — lifted predicates separated by ';'.
    goal_m = _GOAL_LINE_RE.search(text)
    if goal_m:
        for pred_m in _PRED_RE.finditer(goal_m.group(1)):
            result["goal"].append({
                "pred": pred_m.group(1),
                "args": [a.strip() for a in pred_m.group(2).split(",") if a.strip()],
            })

    # Parse scene objects
    scene_m = _SCENE_RE.search(text)
    if scene_m:
        result["scene_objects"] = [
            o.strip() for o in scene_m.group(1).split(",") if o.strip()
        ]

    # Primary split: "Step N:" markers. Fallback: action-keyword splits when
    # the model collapsed the format (no Step prefix and/or no newlines).
    primary_parts = re.split(r"(?=Step\s+\d+:)", text.strip())
    has_step_header = any(
        _STEP_DEST_RE.search(p) or _STEP_RE.search(p) for p in primary_parts
    )
    if has_step_header:
        parts = primary_parts
        use_fallback = False
    else:
        parts = re.split(rf"(?=\b{_ACTION_KW}\()", text.strip(), flags=re.I)
        use_fallback = True

    auto_step_num = 0
    for part in parts:
        part = part.strip()
        if not part:
            continue

        step: dict = {"constraints": {}}

        if not use_fallback:
            # Try destination pattern first: "Step N: action(target -> dest)"
            m = _STEP_DEST_RE.search(part)
            if m:
                step["step"] = int(m.group(1))
                step["action"] = m.group(2)
                step["target"] = m.group(3).strip()
                step["destination"] = m.group(4).strip()
            else:
                m = _STEP_RE.search(part)
                if m:
                    step["step"] = int(m.group(1))
                    step["action"] = m.group(2)
                    step["target"] = m.group(3).strip()
        else:
            # Fallback: model dropped "Step N:" prefix. Match a leading
            # action(target [-> dest]) and auto-number sequentially.
            m = _STEP_FALLBACK_DEST_RE.match(part)
            if m:
                auto_step_num += 1
                step["step"] = auto_step_num
                step["action"] = m.group(1).lower()
                step["target"] = m.group(2).strip()
                step["destination"] = m.group(3).strip()
            else:
                m = _STEP_FALLBACK_RE.match(part)
                if m:
                    auto_step_num += 1
                    step["step"] = auto_step_num
                    step["action"] = m.group(1).lower()
                    step["target"] = m.group(2).strip()

        if "step" not in step:
            continue

        # V2: affordance_region — textual description, Lang-SAM grounds at runtime.
        m = _REGION_RE.search(part)
        if m:
            step["affordance_region"] = m.group(1).strip().strip(".,;")

        # V1 back-compat: affordance_hint + [u, v] coords.
        m = _HINT_RE.search(part)
        if m:
            step["affordance_hint"] = m.group(1).strip().strip(".,;")
        m = _AFF_RE.search(part)
        if m:
            step["affordance"] = [float(m.group(1)), float(m.group(2))]

        # Parse approach (handle "approach: [...]", "approach=[...]",
        # and "approach: [x=..., y=..., z=...]")
        app_m = re.search(
            r"approach[=:\s]+\[\s*(?:x=)?([-0-9.e+]+)[,\s]+"
            r"(?:y=)?([-0-9.e+]+)[,\s]+(?:z=)?([-0-9.e+]+)\s*\]",
            part, re.I,
        )
        if app_m:
            step["approach"] = [float(app_m.group(i)) for i in range(1, 4)]

        # Parse constraint categories (new format)
        for cat_m in _CONSTRAINT_LINE_RE.finditer(part):
            category = cat_m.group(1).lower()
            constraint_str = cat_m.group(2)
            constraints = []
            for pred_m in _PRED_RE.finditer(constraint_str):
                c = {
                    "pred": pred_m.group(1),
                    "args": [a.strip() for a in pred_m.group(2).split(",") if a.strip()],
                }
                if pred_m.group(3):
                    c["role"] = pred_m.group(3)
                elif category == "safety":
                    c["role"] = "safety"
                constraints.append(c)
            if constraints:
                step["constraints"][category] = constraints

        # Legacy format fallback: parse gripper field
        if not step["constraints"]:
            m = _WID_RE.search(part)
            if m:
                step["gripper_width"] = float(m.group(1))
            gripper_m = re.search(r"gripper:\s*(\S+)", part, re.I)
            if gripper_m:
                step["gripper"] = gripper_m.group(1).strip().rstrip(",")

        # Parse done_when
        done_m = re.search(r"done_when:\s*(.+?)(?:\n|$)", part, re.I)
        if done_m:
            step["done_when"] = done_m.group(1).strip()

        result["steps"].append(step)

    return result


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def augment_prompt(text: str, task_type: str = DEFAULT_TASK_TYPE) -> str:
    """Apply task-specific prompt augmentation.

    Matches RoboBrain2.5's inference.py prompt patterns so the model
    sees the same style of instructions it was pretrained on.
    """
    template = TASK_TEMPLATES.get(task_type, TASK_TEMPLATES["general"])
    return template.format(text=text)


def build_messages(
    user_text: str,
    assistant_text: str | None = None,
    system_prompt: str | None = DEFAULT_SYSTEM_PROMPT,
    task_type: str = DEFAULT_TASK_TYPE,
    image=None,
) -> list[dict]:
    """Build chat messages in Qwen3-VL format.

    Args:
        user_text: Raw user prompt (will be augmented by task_type).
        assistant_text: Target response (None for inference).
        system_prompt: System message (None to omit).
        task_type: Task type for prompt augmentation.
        image: Optional PIL Image to include in the user message
               (for native VLM ViT path).

    Returns:
        List of message dicts ready for apply_chat_template().
    """
    augmented = augment_prompt(user_text, task_type)

    # Use planning-specific system prompt when task_type is "planning"
    if task_type == "planning" and system_prompt == DEFAULT_SYSTEM_PROMPT:
        system_prompt = PLANNING_SYSTEM_PROMPT

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    user_content = []
    if image is not None:
        user_content.append({"type": "image", "image": image})
    user_content.append({"type": "text", "text": augmented})
    messages.append({"role": "user", "content": user_content})

    if assistant_text is not None:
        messages.append({"role": "assistant", "content": assistant_text})
    return messages


def build_chat_inputs(
    prompts: list[str],
    targets: list[str],
    tokenizer,
    device: str,
    max_length: int = 512,
    system_prompt: str | None = DEFAULT_SYSTEM_PROMPT,
    task_types: list[str] | None = None,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Build tokenized inputs with proper chat template and label masking.

    Uses Qwen3-VL's native chat template so the model sees the same
    format it was pretrained on.  Only assistant response tokens
    contribute to the LM loss; system + user tokens are masked with -100.

    Optimized: one ``apply_chat_template()`` call per sample, then
    batched tokenization (2 batch calls total instead of 2*B individual).

    Args:
        prompts: List of task descriptions.
        targets: List of target responses.
        tokenizer: HuggingFace tokenizer (from AutoProcessor.tokenizer).
        device: Target device string.
        max_length: Maximum sequence length.
        system_prompt: Optional system message (None to omit).
        task_types: Per-sample task types (default: all "affordance").

    Returns:
        input_ids:      [B, L]
        attention_mask: [B, L]
        labels:         [B, L] with -100 for non-target positions
    """
    if task_types is None:
        task_types = [DEFAULT_TASK_TYPE] * len(prompts)

    # Step 1: Build all text strings (one apply_chat_template per sample)
    all_full_texts = []
    all_prompt_texts = []

    for prompt, target, task_type in zip(prompts, targets, task_types):
        messages_full = build_messages(prompt, target, system_prompt, task_type)
        full_text = tokenizer.apply_chat_template(
            messages_full, tokenize=False, add_generation_prompt=False,
        )
        # Extract prompt prefix by finding the assistant marker in the full text
        # This avoids a second apply_chat_template() call per sample
        marker_pos = full_text.find(_ASSISTANT_MARKER)
        prompt_text = full_text[:marker_pos + len(_ASSISTANT_MARKER)]

        all_full_texts.append(full_text)
        all_prompt_texts.append(prompt_text)

    # Step 2: Batch tokenize (2 calls total, not 2*B)
    full_enc = tokenizer(
        all_full_texts, return_tensors="pt",
        padding=True, truncation=True, max_length=max_length,
    )
    prompt_enc = tokenizer(
        all_prompt_texts, return_tensors="pt",
        padding=True, truncation=True, max_length=max_length,
    )

    input_ids = full_enc.input_ids.to(device)
    attention_mask = full_enc.attention_mask.to(device)

    # Step 3: Build labels — mask prompt tokens and padding
    prompt_lens = prompt_enc.attention_mask.sum(dim=1)  # [B]
    labels = input_ids.clone()
    for i, plen in enumerate(prompt_lens):
        labels[i, :plen] = -100
    labels[attention_mask == 0] = -100

    return input_ids, attention_mask, labels


def format_inference_prompt(
    text: str,
    tokenizer,
    system_prompt: str | None = DEFAULT_SYSTEM_PROMPT,
    task_type: str = DEFAULT_TASK_TYPE,
) -> tuple[str, torch.Tensor]:
    """Format a single prompt for inference (no target).

    Returns the full prompt string (with generation prefix) and its token IDs,
    ready for model.generate() or manual autoregressive generation.

    Returns:
        prompt_text: The formatted prompt string.
        input_ids: [1, L] token ID tensor.
    """
    messages = build_messages(text, None, system_prompt, task_type)
    prompt_text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
    )
    enc = tokenizer(prompt_text, return_tensors="pt")
    return prompt_text, enc.input_ids
