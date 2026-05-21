# VLM 约束规划 + VLA 动作执行 + MPC 预测验证机器人操作框架（v2 修订版）

> 本文档是对 [`vlm_vla_mpc_robot_framework_outline.md`](./vlm_vla_mpc_robot_framework_outline.md) 的整合修订，**不替换旧版**。
> 旧版作为"完整设想 / 系统模块图"保留作为参考；本版作为"实际推进路线 + 修订后架构"，是后续实现和论文工作的主依据。
>
> v2 的核心改动来自三个事实/约束的暴露：
>
> 1. **真实数据是 RGB-D**，不是纯 RGB —— 简化了 perception / grounding / MPC 的实现路径。
> 2. **目标场景包含双臂协作**（含 handover、co-manipulation） —— 暴露了 VLM 的"运动学盲区"和 outline §10 "顺序自由"原则的边界。
> 3. **VLM 在框架中担任双重角色**：既是前置 planner，又是旁路 supervisor —— 需要明确两个角色的输入 / 输出 / 触发时机 / 权限边界。

---

## 0. v2 与 v1 的差异速览

| v1 设计 | v2 修订 | 原因 |
|---|---|---|
| 四层 stack：VLM → Grounding → VLA → MPC | 五层 stack：VLM-planner → **Embodiment Grounder** → Grounding → VLA → MPC，旁路 **VLM-supervisor** | VLM 不懂身体；VLM 监督需要权限隔离 |
| §10 任务顺序"完全自由 / 只看 final state" | 拆成 **sequencing constraint**（可交换）vs **synchronization constraint**（handover 必须时序对齐） | 双臂场景 handover 时序错位 = 物理失败 |
| §11 失败恢复 4×4 启发式矩阵 | 三条线：MPC 战术修正 / supervisor 触发 replan / irreversible 直接 abort | 4×4 矩阵不可维护，且与权限层级冲突 |
| §3 复杂 3D scene construction | RGB-D 直接反投影点云 | depth 给了，不需要 SfM/NeRF |
| §5 八级 affordance filter pipeline | LangSAM mask + depth lift + 单一启发式打分 | 八级 filter 的权重不可学，part-level seg 不成熟 |
| §7 World Model 分 A/B/C 三层 | 第一版**只做 constraint projector**（去掉 "World Model" 这个 paper claim） | Stage B/C 是独立研究方向，超出 scope |
| 约束表示用自然语言 JSON 字符串 | **冻结的 predicate dictionary**（约 15–20 个 predicate，每个有 `evaluate()` + `cost()` 双实现） | 没有冻结字典，VLM 训练目标和 MPC 实现永远对不齐 |
| 假设 VLM 输出包含 arm 标签和 handover step | **VLM embodiment-agnostic**，arm assignment 和 handover 由 Embodiment Grounder 推断 | 双臂训练数据稀缺；同一 VLM 跨 embodiment 复用 |
| 静态 plan（target / location / affordance 写死，runtime 不变）| **Deferred references + Scene Blackboard + L2.5 Semantic Resolver**：plan 含 `?placeholder`，每步入口由 VLM-primary + rule-fallback 解析；runtime 可加约束、可 refine affordance | 散落 / 不可预测 layout 必须 closed-loop；VLM 的 world knowledge 必须在 runtime 持续贡献，否则架构等于"花 7B 参数训了个填空模板生成器" |

---

## 1. 五条设计纪律（贯穿全文）

这五条是 v2 框架的"宪法"，所有模块设计都必须遵守：

### D1. Constraint contract，不是 action script
VLM-planner 输出的是一份**约束契约**：goal predicate（验收标准）+ per-step constraints（过程约束）。VLA 在契约内自由发挥，MPC 实时把越界动作拍回来。**VLA 的动作序列不需要与 VLM 的"步骤"逐一对应**，只要最终 goal predicate 满足、过程中无 hard constraint 违反，即视为成功。

### D2. Outcome-based supervision，不是 method matching
VLM-supervisor 只判断**结果**（goal 是否推进、约束是否违反、stage 是否完成），不判断**过程**（VLA 用的方法是否与 plan 一致、轨迹是否与设想吻合）。违反这条 = 退化成 rigid script following，框架核心论点崩塌。

### D3. VLM 是 embodiment-agnostic，身体在 Grounder
VLM 不知道也不应该知道"我有几只手、每只手能到哪里"。Reachability、arm assignment、handover 触发完全由 Embodiment Grounder 用 IK / 几何 / 当前状态决定。这让同一个 VLM 可以跨单臂 / 双臂 / 移动操作复用。

### D4. Predicate dictionary 是窄腰，必须冻结
VLM 能输出的 predicate 集合 ≡ MPC 能算的 predicate 集合 ≡ Supervisor 能判断的 predicate 集合。**三者必须 1:1 对齐**。这份字典是项目的"narrow waist"，必须在 day 1 就冻结（见 §3）。

### D5. Frequency separation：反应 / 战术 / 语义 / 战略 四层权限
- **Layer 1 反应层（10–30 Hz）**：VLA 提议单步动作 `a_t`。
- **Layer 2 战术层（10–30 Hz）**：MPC 验证 / 修正 `a_t → a_t*`。
- **Layer 2.5 语义层（step 入口/退出，0.5–2 Hz）**：VLM-Binder / VLM-Refiner 解析 deferred reference、生成 runtime 约束、refine affordance。**VLM-primary + rule-fallback**（见 §11.5）。
- **Layer 3 战略层（事件驱动 / 0.2–1 Hz）**：VLM-supervisor 判断 stage / replan / abort。

频率越高的环路权限越大但视野越窄；频率越低的环路视野越宽但权限越克制。L2.5 与 L3 都用 VLM，但分工不同：**L2.5 在每步绑定/精化**（默认在 main loop 里，靠 cache/skip/fallback 不阻塞），**L3 在多步异常时决策**（旁路，事件触发）。VLM-supervisor **不直接修改单步动作**，只能改 stage / 触发 replan / abort；L2.5 **不修改 plan 结构**，只填空 deferred reference + 追加 step 内约束。

---

## 2. 修订后的总体架构

```text
                       User Instruction
                              │
                              ▼
              ┌───────────────────────────────┐
              │  VLM-Planner (RoboBrain LoRA) │   出 plan.json (含 ?deferred refs)
              │  (embodiment-agnostic)        │   • <think> 推理
              └───────────────────────────────┘   • Goal: predicate
                              │                   • binding_initialization
                              ▼                   • per-step:
              ┌───────────────────────────────┐     - ?refs + binders
              │  Embodiment Grounder           │    - constraints (predicate list)
              │  • 3D reachability per arm    │     - runtime / refinement queries
              │  • arm assignment              │
              │  • handover insertion          │
              │  • bi-manual coordination      │
              └───────────────────────────────┘
                              │ embodiment-grounded plan (?refs 未解析)
                              ▼
  ╔═══════════════════════════════════════════════════════════════════╗
  ║  Per-Step Entry — L2.5 Semantic Resolution (0.5–2 Hz)              ║
  ║                                                                     ║
  ║    ┌──────────────────────┐    ┌────────────────────────┐         ║
  ║    │  VLM-Binder           │ ←→ │  Scene Blackboard       │ ←──┐   ║
  ║    │ (semantic_query +     │    │  • object states        │    │   ║
  ║    │  rule fallback)       │    │  • symbol bindings      │    │   ║
  ║    └──────────────────────┘    │  • execution history    │    │   ║
  ║              ↓                  └────────────────────────┘    │   ║
  ║    ┌──────────────────────┐                                    │   ║
  ║    │  VLM-Refiner          │   runtime constraints              │   ║
  ║    │  (skip if scene       │   affordance refinement            │   ║
  ║    │   unchanged)          │                                    │   ║
  ║    └──────────────────────┘                                    │   ║
  ║              ↓                                                  │   ║
  ║    ┌──────────────────────┐                                    │   ║
  ║    │ Affordance Grounding  │   LangSAM + depth lift             │   ║
  ║    │ (resolved text → 3D)  │                                    │   ║
  ║    └──────────────────────┘                                    │   ║
  ║              ↓                                                  │   ║
  ║        resolved step (concrete targets + cstrs + 3D points)     │   ║
  ╚═════════════════════════════════════════════════════════════════│═══╝
                              ↓                                     │
   ╔═══════════════════════════════════════════════════════════════│════╗
   ║  Inner Loop (L1+L2, 10–30 Hz)                                 │    ║
   ║   obs_t  →  VLA  →  a_t                                       │    ║
   ║              ↓                                                 │    ║
   ║          MPC verify/correct  →  a_t*                          │    ║
   ║              ↓                                                 │    ║
   ║          robot.execute(a_t*)                                  │    ║
   ║              │  logs: rejects, corrections                    │    ║
   ╚════════════════════════════════════════════════════════════════│════╝
                              │  step complete → bindings updated  │
                              └────────────────────────────────────┘
                              │  (异常 / milestone trigger)
                              ▼
              ┌───────────────────────────────┐
              │  VLM-Supervisor (L3)           │   旁路, 事件驱动
              │  (same model, different       │   only judges outcomes
              │   prompt / adapter)           │   never edits single action
              └───────────────────────────────┘
                              │
                              ▼
                  continue / advance_stage /
                  refine_plan / full_replan / abort
```

**两条主线 + 一个 per-step gate + 一条旁路**：
- 主线 A（planning）：VLM-planner → Embodiment Grounder （产出含 deferred refs 的 plan）
- **Per-step gate（L2.5）**：VLM-Binder + VLM-Refiner + Affordance Grounding，每个 step 进入前解析 `?refs`、读 / 写 Scene Blackboard、（必要时）VLM 加 runtime 约束。**默认在 main loop 内**，靠 cache / skip / fallback 不阻塞。
- 主线 B（execution）：VLA → MPC → robot
- 旁路（supervision）：VLM-supervisor 事件驱动接入，权限仅限战略层（改 plan 结构 / 终止任务）

---

## 3. Predicate Dictionary（项目窄腰）

这是 v2 最重要的新增物。在 day 1 冻结这份字典，VLM 训练数据、MPC 实现、supervisor 判断、score.py 评测全部基于它。

### 3.1 字典结构

每个 predicate 是一个 Python 对象，提供两种实现：

```python
class Predicate:
    name: str
    arity: int                    # 参数个数
    arg_types: List[str]          # 每个参数的类型（object / point / vector / scalar）
    
    def evaluate(self, state, args) -> bool:
        """硬判断：约束满足/不满足"""
    
    def cost(self, state, args) -> float:
        """软代价：越大违反越多；满足时 = 0"""
```

### 3.2 第一版 predicate 集合（约 18 个）

| 类别 | Predicate | 签名 | 用途 |
|---|---|---|---|
| **Spatial** | `above(A, B)` | (obj, obj) → bool | A 在 B 上方 |
| | `on(A, B)` | (obj, obj) → bool | A 接触 B 顶面 |
| | `inside(A, B)` | (obj, obj) → bool | A 在 B 内部 |
| | `left_of / right_of / front_of / behind` | (obj, obj) → bool | 相对位置 |
| | `dist_lt(A, B, eps)` | (obj/point, obj/point, scalar) → bool | 距离小于阈值 |
| **Contact** | `contact(A, B)` | (obj, obj) → bool | A 与 B 接触 |
| | `grasp_stable(arm, obj)` | (arm, obj) → bool | arm 稳定抓住 obj |
| | `collision_free(A, B)` | (obj/arm, obj/arm) → bool | A 与 B 不碰撞 |
| **Pose** | `upright(A)` | (obj) → bool | A 处于直立姿态 |
| | `aligned(A_axis, B_axis)` | (vector, vector) → bool | 两轴对齐 |
| | `perpendicular(A_axis, B_axis)` | (vector, vector) → bool | 两轴垂直 |
| **Direction** | `approach_along(arm, dir)` | (arm, vector) → bool | arm 沿 dir 方向接近 |
| **Safety** | `above_plane(A, plane, margin)` | (obj, plane, scalar) → bool | 不低于桌面等 |
| | `inside_workspace(arm, point)` | (arm, point) → bool | arm 可达 |
| **Temporal** | `before(event_A, event_B)` | (event, event) → bool | A 事件早于 B（**handover 用**） |
| | `simultaneous(event_A, event_B, tol)` | (event, event, scalar) → bool | A 与 B 同时（co-manipulation） |
| | `stable_for(state_pred, duration)` | (predicate, scalar) → bool | 某状态稳定持续 |

### 3.3 设计约束

- **封闭集合**：VLM-planner 输出只能用这 18 个 predicate 的组合。训练数据生成时严格 schema check，不允许自由文本约束。
- **可微近似**：`cost()` 必须返回可微 soft 形式（如 `dist_lt` 用 `max(0, d - eps)` 而不是阶跃），供 MPC constraint projection 使用。
- **参数类型严格**：`arg_types` 强制对齐，VLM 出错（如把 vector 传给 obj 参数）时直接拒绝。
- **存放位置**：`mpc/predicates.py`（单一权威实现），训练数据生成器、MPC、supervisor 全部 import 同一份。

### 3.4 训练数据对齐

V2 plan format 的 `constraints` 字段（contact / spatial / pose / direction / safety 五类）需要重新生成成 predicate dictionary 严格调用形式。例如：

```json
// v1 (自然语言)
{"constraints": {"hard": ["avoid collision with knife"]}}

// v2 (predicate)
{"constraints": [
  {"pred": "collision_free", "args": ["gripper_left", "knife"], "role": "safety"}
]}
```

这意味着 ~26k 条已生成 plan.json 需要做一次 schema migration。预计成本：单次批量推理（gpt-5-mini 走 yunwu.ai），半天完成。

---

## 4. VLM-Planner（修订）

### 4.1 角色（不变）
任务理解 + 空间推理 + affordance 提议 + 约束生成 + stage 规划。

### 4.2 角色（明确不做）
- **不输出 arm 标签**（左/右/双臂）—— 交给 Embodiment Grounder
- **不输出 handover step** —— 交给 Embodiment Grounder
- **不输出像素 UV 坐标** —— 交给 LangSAM grounding
- **不输出低层动作** —— 交给 VLA

### 4.3 输出 schema（V2 格式 + predicate dictionary 对齐）

```json
{
  "think": "桌面上有红色杯子和盘子。任务要求把杯子放到盘子右边。需要先抓住杯子侧面，再平移到盘子右侧位置，最后释放。",
  "goal": [
    {"pred": "right_of", "args": ["cup", "plate"]},
    {"pred": "dist_lt", "args": ["cup_center", "target_point", 0.05]}
  ],
  "scene": "red cup at left, white plate at center, no obstacles nearby",
  "steps": [
    {
      "stage": "approach",
      "target": "cup",
      "affordance_region": "the side surface of the red cup facing the robot",
      "constraints": [
        {"pred": "approach_along", "args": ["active_arm", [-1, 0, 0]], "role": "progress"},
        {"pred": "above_plane", "args": ["gripper", "table", 0.02], "role": "safety"},
        {"pred": "collision_free", "args": ["gripper", "knife"], "role": "safety"}
      ],
      "termination": [
        {"pred": "dist_lt", "args": ["gripper_tip", "cup_side", 0.03]}
      ]
    },
    {
      "stage": "grasp",
      "target": "cup",
      "affordance_region": "the side surface of the red cup",
      "constraints": [
        {"pred": "grasp_stable", "args": ["active_arm", "cup"], "role": "completion"},
        {"pred": "upright", "args": ["cup"], "role": "safety"}
      ],
      "termination": [
        {"pred": "grasp_stable", "args": ["active_arm", "cup"]}
      ]
    },
    {
      "stage": "transport",
      "target": "cup",
      "affordance_region": null,
      "constraints": [
        {"pred": "upright", "args": ["cup"], "role": "safety"},
        {"pred": "dist_lt", "args": ["cup_center", "target_point", 0.05], "role": "progress"}
      ],
      "termination": [
        {"pred": "dist_lt", "args": ["cup_center", "target_point", 0.05]}
      ]
    }
  ]
}
```

注意：
- `active_arm` 是占位符，由 Embodiment Grounder 替换成具体 `left_arm` 或 `right_arm`。
- `target_point` 是符号引用，由 Grounder + LangSAM 解析成 3D 坐标。
- `role` 字段（progress / completion / safety）用于评分加权。

### 4.4 训练目标修订
- V2 LoRA 训练目标 schema 需要更新为上述 predicate dictionary 严格调用形式（见 §3.4）。
- 添加 predicate-level metric 到 score.py：goal predicate 命中率、constraint predicate F1、不在字典内的 predicate 比例（应为 0）。

---

## 5. Embodiment Grounder（新模块）

### 5.1 角色
把 embodiment-agnostic 的 VLM plan 翻译成 embodiment-grounded plan：决定每个 step 用哪只手、是否需要 handover、是否需要双臂协作。

### 5.2 输入 / 输出

```python
EmbodimentGrounderInput = {
    "vlm_plan": ...,                # §4.3 的输出
    "scene_rgbd": (rgb, depth),
    "robot_state": {
        "left_arm":  {"joint_state": ..., "ee_pose": ..., "holding": None},
        "right_arm": {"joint_state": ..., "ee_pose": ..., "holding": None},
    },
    "embodiment_spec": {            # 机器人 URDF + workspace 描述
        "arm_ids": ["left_arm", "right_arm"],
        "ik_solver": ...,
        "workspace_polytope": {"left_arm": ..., "right_arm": ...},
    }
}

EmbodimentGrounderOutput = {
    "grounded_steps": [             # 每步带 arm 标签
        {"arm": "left_arm", "stage": "approach", ...},
        {"arm": "left_arm", "stage": "grasp", ...},
        {"arm": "left_arm", "stage": "lift_to_handover", ...},   # 自动插入
        {"arm": "right_arm", "stage": "approach_for_handover", ...},
        {"arm": "right_arm", "stage": "grasp_for_handover",
         "temporal_constraints": [
             {"pred": "before", "args": ["right_grasp_stable", "left_release"]}
         ]},
        {"arm": "left_arm", "stage": "release_after_handover", ...},
        {"arm": "right_arm", "stage": "transport", ...},
    ],
    "diagnostics": {
        "any_unreachable_step": False,
        "handovers_inserted": 1,
        "arms_used": ["left_arm", "right_arm"],
    }
}
```

### 5.3 核心算法（启发式 + IK，1–2 周可实现第一版）

```python
def ground_plan_to_embodiment(plan, scene_rgbd, robot_state, embodiment):
    grounded = []
    # 1. lift affordance regions 到 3D
    region_3d = {}
    for step in plan.steps:
        if step.affordance_region:
            mask = langsam.segment(scene_rgbd.rgb, step.affordance_region)
            region_3d[step.id] = lift_mask_to_3d(mask, scene_rgbd.depth)
    
    # 2. per-step arm assignment
    current_holder = {arm: None for arm in embodiment.arm_ids}
    for step in plan.steps:
        target_3d = region_3d.get(step.id) or resolve_symbolic_point(step.target)
        reach = {arm: embodiment.ik_solver.reachable(target_3d, arm, robot_state[arm])
                 for arm in embodiment.arm_ids}
        
        # case A: 上一步已经握着相关物体 → 优先继续用同一只手
        for arm in embodiment.arm_ids:
            if current_holder[arm] == step.target and reach[arm]:
                grounded.append({**step, "arm": arm})
                break
        else:
            # case B: 至少一只手可达 → 启发式选臂
            reachable_arms = [a for a, ok in reach.items() if ok]
            if reachable_arms:
                arm = pick_by_heuristic(reachable_arms, robot_state, target_3d)
                grounded.append({**step, "arm": arm})
                update_holder_if_grasp(current_holder, step, arm)
            else:
                # case C: 当前 holder 够不到，但另一只手够得到 → 触发 handover
                holder_arm = [a for a, obj in current_holder.items() if obj == step.target]
                if holder_arm:
                    other_arm = [a for a in embodiment.arm_ids if a != holder_arm[0]][0]
                    if embodiment.ik_solver.reachable(target_3d, other_arm, robot_state[other_arm]):
                        grounded.extend(insert_handover_subplan(
                            from_arm=holder_arm[0],
                            to_arm=other_arm,
                            obj=step.target,
                            scene=scene_rgbd
                        ))
                        current_holder[holder_arm[0]] = None
                        current_holder[other_arm] = step.target
                        grounded.append({**step, "arm": other_arm})
                    else:
                        return RequestReplan(reason="object_unreachable_by_any_arm", step=step)
                else:
                    return RequestReplan(reason="target_unreachable_no_holder", step=step)
    
    # 3. 检测 co-manipulation：同一物体被同时引用 → 双臂共操作
    grounded = detect_and_mark_bimanual(grounded)
    return grounded
```

### 5.4 Handover sub-plan 模板

```python
HANDOVER_TEMPLATE = [
    # 1. source 臂把物体抬到双臂共同工作区
    {"arm": SRC, "stage": "lift_to_handover_zone",
     "target_point": "handover_zone_center",     # workspace 交集中心
     "constraints": [
         {"pred": "grasp_stable", "args": [SRC, OBJ], "role": "safety"},
         {"pred": "upright", "args": [OBJ], "role": "safety"},
     ]},
    
    # 2. target 臂接近交接位
    {"arm": TGT, "stage": "approach_for_handover",
     "target_point": "near_object_held_by_src",
     "constraints": [
         {"pred": "collision_free", "args": [TGT, SRC], "role": "safety"},
         {"pred": "approach_along", "args": [TGT, "opposing_to_src"], "role": "progress"},
     ]},
    
    # 3. target 臂闭合夹爪（必须在 src 还稳定握持时）
    {"arm": TGT, "stage": "grasp_for_handover",
     "constraints": [
         {"pred": "grasp_stable", "args": [TGT, OBJ], "role": "completion"},
     ],
     "temporal_constraints": [
         {"pred": "before", "args": ["src_grasp_stable", "tgt_close_gripper"]},
         {"pred": "before", "args": ["tgt_grasp_stable", "src_release"]},   # ← 关键
     ]},
    
    # 4. source 臂松开（必须在 target 稳定握持后）
    {"arm": SRC, "stage": "release_after_handover",
     "temporal_constraints": [
         {"pred": "before", "args": ["tgt_grasp_stable", "src_release"]},
         {"pred": "stable_for", "args": ["tgt_grasp_stable", 0.3]},   # 0.3s
     ]},
    
    # 5. source 臂撤退
    {"arm": SRC, "stage": "retreat",
     "constraints": [
         {"pred": "collision_free", "args": [SRC, TGT], "role": "safety"},
     ]},
]
```

注意第 3、4 步的 `temporal_constraints`：**handover 的成败完全取决于时序对齐**，MPC 必须能强制这类约束（见 §7）。

### 5.5 Co-manipulation 标记

当 grounded plan 中两个不同 arm 的 step 在时间窗口内引用同一物体（如 "抬大箱子"），自动标记为 `coordinated: true`，MPC 在该窗口内启用双臂耦合约束（如 `dist_lt(left_gripper, right_gripper, max_box_size)` + `aligned(left_force, right_force_opposite)`）。

---

## 6. Affordance Grounding（简化）

### 6.1 v1 的八级 filter pipeline 砍掉

仅保留：

```python
def ground_affordance(region_text, scene_rgbd):
    mask = langsam.segment(scene_rgbd.rgb, region_text, fallback_to_target_noun=True)
    if mask is None or mask.sum() < MIN_PIXELS:
        return None
    point_3d = lift_mask_centroid_to_3d(mask, scene_rgbd.depth)
    normal_3d = estimate_normal_from_depth(scene_rgbd.depth, mask)
    return {
        "contact_point": point_3d,
        "surface_normal": normal_3d,
        "mask": mask,
    }
```

### 6.2 候选点 vs 单点
- 仅当 mask 面积大且形状复杂时（如长条把手），从 mask 上等距采样 5–10 个候选点；否则用 centroid。
- 候选的 IK 可达性检查由 Embodiment Grounder 在 arm assignment 时做，不在 affordance grounding 里做（**单一职责**）。

### 6.3 RGB-D 的礼物
- surface normal 直接从 depth 邻域算梯度，不需要训 normal estimator
- depth 缺失（透明物体、反光）自动 fallback：用 mask 中心 + 推断平面深度
- 不需要 SfM / NeRF / 3DGS 重建——depth 直接给点云

---

## 7. MPC（限定为 Constraint Projector）

### 7.1 v1 的 World Model 三阶段砍到只剩 Stage A

第一版 MPC **只做约束投影**，不做 forward dynamics 预测。即：

\[
a^* = \arg\min_a \|a - a_{vla}\|^2 \quad \text{s.t.} \quad \forall i: c_i(\text{kinematic\_forward}(s_t, a)) \leq 0
\]

`kinematic_forward` 仅做：
- FK：把 EE delta action 映射到 EE 新位姿
- Rigid attach：被抓物体跟随 gripper 移动
- 不预测物体动力学（不计算"推下去会不会倒"这类问题）

**这是诚实的定位**：MPC = differentiable constraint projector，不是 learned world model。"Predictive Action Shielding" 这个 paper claim 在 v2 中**暂时取消**，等 Stage B/C 落地再加。

### 7.2 第一版实现

```python
def mpc_verify_and_correct(state, a_vla, active_constraints, embodiment):
    # 1. 硬约束 gating
    pred_state = kinematic_forward(state, a_vla, embodiment)
    hard_violations = [c for c in active_constraints
                       if c.role == "safety" and not c.evaluate(pred_state)]
    
    if not hard_violations:
        return Accept(a_vla)
    
    # 2. 约束投影：在 a_vla 邻域采样 K 个动作，选满足 hard 且 cost 最小的
    candidates = sample_around(a_vla, K=64, sigma=0.02)
    valid = []
    for a in candidates:
        pred = kinematic_forward(state, a, embodiment)
        if all(c.evaluate(pred) for c in active_constraints if c.role == "safety"):
            cost = sum(c.cost(pred) for c in active_constraints) \
                 + LAMBDA_V * np.linalg.norm(a - a_vla)
            valid.append((cost, a))
    
    if not valid:
        return Reject(reason="no_valid_correction", violations=hard_violations)
    
    return Correct(min(valid)[1])
```

### 7.3 时序约束的特殊处理（双臂）

`before`、`simultaneous`、`stable_for` 这些 temporal predicate 不能在单步 MPC 里直接评估——需要一个 **事件总线**：

```python
class EventBus:
    def emit(self, event_name, timestamp): ...
    def has_occurred(self, event_name) -> bool: ...
    def time_since(self, event_name) -> float: ...

# 在执行循环中
if grasp_stable(right_arm, obj).evaluate(state):
    bus.emit("tgt_grasp_stable", now)

# MPC 在评估 a_vla 时
def evaluate_temporal(constraint, state, bus):
    if constraint.pred == "before":
        e1, e2 = constraint.args
        # 如果 a_vla 会触发 e2，但 bus 还没记录 e1 → 违反
        if would_trigger(a_vla, e2) and not bus.has_occurred(e1):
            return False
    ...
```

这一段是双臂 framework 最 tricky 的工程部分，但 predicate dictionary 把它收纳成有限几种情况，可控。

---

## 8. VLM-Supervisor（新模块）

### 8.1 角色
战略层异常检测 + replan 触发 + abort 决策。**不修改单步动作**。

**与 L2.5 Semantic Resolver（§11.5）的分工**：

| 维度 | L2.5 | L3 (本节) |
|---|---|---|
| 触发频率 | 每个 step 入口/退出 | 事件驱动（异常 / milestone） |
| 修改权限 | 填补 plan 中 `?refs`；追加 step 内约束 | 修改 plan 结构（删 / 加 / 重写 step） |
| 默认成本 | 多数走 cache/skip/fallback，~100ms/step | 多数路径 0 调用，触发时 200–500ms |
| 失败模式 | fallback rule | 升级到 full replan |

**不重叠原则**：L2.5 从不修改 plan 结构；L3 从不解析单个 binding。两者可以同模型不同 prompt 实现（推荐），但调用时机和权限严格分离。如果都能处理同一类决策（如"剩余 plan 还能跑吗"），优先 L2.5（更轻），失败再升 L3。

### 8.2 输入

```python
SupervisorInput = {
    "current_rgbd": (rgb, depth),
    "active_plan": ...,              # 当前 grounded plan
    "current_stage_idx": int,
    "history": {
        "actions_last_n_seconds": ...,
        "mpc_verdicts_last_n": [...],     # accept / correct / reject 序列
        "progress_score_trend": ...,
        "time_in_current_stage": float,
    },
    "robot_state": ...,
}
```

### 8.3 输出 schema

```json
{
  "stage_status": "in_progress | completed | failed | stuck",
  "progress_assessment": "advancing | stalled | regressing",
  "anomalies_observed": [
    "object_dropped",
    "wrong_object_grasped",
    "handover_partner_arm_idle",
    "occlusion_severe"
  ],
  "decision": "continue | advance_stage | replan | abort",
  "rationale": "VLA pushing cup for 5s, cup center hasn't moved — likely contact failure",
  "replan_hint": "switch from push to pick-and-place"
}
```

### 8.4 触发条件（事件驱动）

正常运行时 supervisor 不被调用；只在以下任一条件触发：

```python
def should_invoke_supervisor(state, history, plan):
    return (
        history.mpc_consecutive_rejects >= 5
        or history.time_since_last_stage_transition > 10
        or history.progress_score_regressed_for > 3
        or scene_changed_significantly(state, history.last_supervised_state)
        or vla_confidence_below(0.3)
        or stage_timeout_reached(plan.current_stage)
        or dead_lock_suspected(state)         # 双臂特有：两臂都不动 + 任务未完成
    )
```

### 8.5 Outcome-based 原则（强制）

| ✅ 合法判断 | ❌ 不合法判断 |
|---|---|
| "杯子有没有朝目标方向移动" | "VLA 用的 push direction 是否符合 plan" |
| "stage termination predicate 满足了吗" | "VLA 走的轨迹是否与 plan 设想吻合" |
| "有没有违反 goal-level 约束" | "VLA 选的 contact point 是否是 plan 推荐的那个" |
| "是不是卡住了 / 在退化" | "VLA 是不是按 plan 的步骤顺序在做" |

违反这条 = framework 退化成 rigid script。

### 8.6 实现策略：rule-based stub 先行

**第一版用规则做 supervisor**，能解决约 80% 的不一致问题：

```python
def rule_based_supervisor(state, plan, history):
    # 1. abort：不可逆失败
    if irreversible_failure_detected(state):
        return Decision("abort", "irreversible")
    # 2. advance：stage termination 满足
    if all(p.evaluate(state) for p in plan.current_stage.termination):
        return Decision("advance_stage", "termination predicates satisfied")
    # 3. replan：长时间无进展
    if history.no_progress_for(seconds=5):
        return Decision("replan", "no progress for 5s")
    if history.mpc_rejected_consecutively(n=8):
        return Decision("replan", "8 consecutive MPC rejects")
    if stage_timeout_reached(plan.current_stage):
        return Decision("replan", "stage timeout")
    if dead_lock_suspected(state):
        return Decision("replan", "bimanual dead-lock")
    # 4. continue
    return Decision("continue", "all checks passed")
```

VLM supervisor 仅在 stub **没有覆盖的复杂语义判断**上启用（如 "杯子是否被打翻"、"夹爪是否抓空"）。优先级低于先把 stub 跑通。

---

## 9. 失败处理（简化为三条线）

砍掉 v1 §11 的 4×4 启发式矩阵。新设计：

```text
┌─────────────────────┬──────────────────────────────────┬────────────────────┐
│ 失败级别            │ 检测者                           │ 处理动作           │
├─────────────────────┼──────────────────────────────────┼────────────────────┤
│ 战术失败            │ MPC（单步约束违反）              │ Local correction   │
│ (single action      │                                  │ (constraint        │
│  unsafe / invalid)  │                                  │  projection)       │
├─────────────────────┼──────────────────────────────────┼────────────────────┤
│ 战略失败            │ VLM-supervisor (rule stub +      │ Replan with        │
│ (off-plan, stuck,   │  VLM fallback)                   │ failure context    │
│  no progress)       │                                  │ → VLM-planner      │
├─────────────────────┼──────────────────────────────────┼────────────────────┤
│ 不可逆失败          │ VLM-supervisor (visual check) +  │ Abort + 通知人     │
│ (object broken,     │ 物理传感器                       │                    │
│  fell off table)    │                                  │                    │
└─────────────────────┴──────────────────────────────────┴────────────────────┘
```

Replan 时必须把 **failure context** 传回 VLM-planner：

```json
{
  "replan_reason": "8 consecutive MPC rejects in stage 'grasp'",
  "failed_stage": "grasp",
  "last_attempted_action_summary": "right_arm tried to grasp cup but collided with knife",
  "scene_changes_since_initial_plan": ["knife moved", "cup tilted"]
}
```

VLM-planner 用这个 context 重新生成 plan，而不是从零开始。

---

## 10. 双臂协作的 first-class 处理

### 10.1 把 v1 §10 拆开
v1 主张 "顺序自由 / 只看 final state"。v2 修正：**约束分两类**：

| 类型 | 含义 | 是否可交换 | 例子 |
|---|---|---|---|
| **Sequencing constraint** | 任务逻辑顺序 | 通常可交换 | 叠 3 个相同碗的顺序 |
| **Synchronization constraint** | 物理时序对齐 | 不可交换 | handover 中 tgt 抓稳 → src 松手 |

VLM-planner 只产 sequencing-level plan；synchronization 约束由 Embodiment Grounder 的 handover template / co-manipulation 检测自动注入。

### 10.2 三种双臂情景

1. **独立并行**：两臂做独立任务（左臂搅拌、右臂取盐）。Grounder 把 grounded plan 分成两条 arm-track，分别送进两个 VLA inference 实例。MPC 加双臂避碰约束。

2. **Handover**：物体从一臂交给另一臂。Grounder 自动插入 §5.4 模板。MPC 强制 temporal predicates。

3. **Co-manipulation**：两臂共同操作一个物体（抬大箱子）。Grounder 标记 `coordinated: true`。MPC 加耦合约束（相对距离、力对称）。VLA 需要"双臂同步"的能力——若 VLA 不原生支持，由 MPC 把双臂动作投影到一致状态。

### 10.3 Dead-lock 检测
两臂都不动 + 任务未完成 + 持续 N 秒 → Supervisor 触发 replan。这是双臂 framework 必须有的兜底。

---

## 11. RGB-D 数据的应用清单

| 应用点 | 用法 |
|---|---|
| Affordance grounding | LangSAM mask → depth lift → 3D contact point |
| Surface normal | depth 邻域梯度，无需训练 |
| 物体姿态估计 | depth-based ICP / pose registration（mature 工具如 FoundationPose） |
| MPC 几何约束 | depth 点云直接做碰撞检测（pybullet / cuRobo） |
| Reachability 可视化 | 把每只手 workspace 投影到 depth image，得到 reachability heatmap |
| Scene change detection | 当前 depth vs 历史 depth 的差异 → supervisor 触发条件 |
| VLM 视觉输入 | depth colormap 拼到 RGB 旁边 喂 VLM；或更精细的 depth-aware encoder（RoboBrain-3DGS 方向） |

---

## 11.5 Closed-Loop Plan Refinement（L2.5 Semantic Resolver）

> 这一节是 v2 文档发布后的扩充，解决一个原 v2 设计回避的问题：**plan 一旦生成，runtime 的 VLM general knowledge 实际上没在被使用**。

### 11.5.0 为什么需要这层

v2 原始设计有一个隐含假设：**plan 生成后，target / location / affordance 写死**，runtime 仅靠 MPC（战术）和 Supervisor（异常）维持闭环。但实际场景里有大量"plan 生成时不知道、执行时才确定"的参数：

- **散落 layout**：三个碗散落在桌面，"哪个当 base / 在哪叠"必须执行时决定
- **VLA 的自由度**：VLM 写 "pick bowl_1"，VLA 可能实际抓了 bowl_2——后续 step 必须基于"实际抓到的那只"重新理解
- **场景变化**：执行中桌上多了用户的手机、某个碗倾斜了、汤洒了——需要 runtime 加约束
- **Affordance 漂移**：VLA grasp 完发现物体倾斜，下一步的 placement 应该重新选 affordance

如果完全用 rule-based binder 填补这些位置（"哪个 base？最近那个"），**VLM 的 world knowledge 在 runtime 完全沉睡**——架构等于"花 7B 参数训了个填空模板生成器"。

L2.5 的设计目的：**让 VLM 在 runtime 也持续贡献，但靠 cache / skip / fallback 不阻塞 main loop**。

### 11.5.1 Deferred References：符号引用语法

Plan 用 `?name` 占位符表达"运行时绑定的参数"：

| 符号示例 | 含义 | 绑定时机 |
|---|---|---|
| `?any_bowl_in_scene` | 任意一个桌面、未被处理的碗 | step 入口 |
| `?bowl_in_gripper` | 当前夹爪中的物体 | grasp 成功后 |
| `?stack_base` / `?stack_top` | 当前堆叠的底层 / 顶层物体 | 第一次 place / 每次 place |
| `?remaining_bowls` | 还没被堆叠的碗集合 | 每次 place 后更新 |
| `?stacking_center` | 堆叠基准位置 | binding_initialization |
| `?next_bowl_to_pick` | 下一个该抓的碗 | step 入口 |
| `?base_bowl` | 选定作为基底不动的碗 | binding_initialization（VLM 决定） |

这些符号**不进入 predicate dictionary**——它们是 plan 层的变量，predicate 求值时已被解析成具体对象/位置。

### 11.5.2 Scene Blackboard

所有模块共享的运行时状态：

```python
class SceneBlackboard:
    # 实时物体状态（perception 持续更新，5–10 Hz）
    objects: Dict[str, ObjectState]
    robot_state: RobotState
    
    # 符号绑定表（step 执行后更新）
    bindings: Dict[str, Union[str, Point3D, List[str]]]
    
    # 执行历史（最近 N step）
    history: List[StepExecutionRecord]
    
    def resolve(self, value_or_symbol):
        """递归解析 ?reference → concrete value
        递归是因为 binding 可以引用别的 binding。"""
        if not is_symbol(value_or_symbol):
            return value_or_symbol
        bound = self.bindings.get(value_or_symbol)
        if bound is None:
            raise UnboundReference(value_or_symbol)
        return self.resolve(bound)
    
    def update_after_step(self, step, execution_result):
        """根据 step 的 binding_after_completion 更新绑定"""
        for symbol, binder_spec in step.binding_after_completion.items():
            self.bindings[symbol] = self._evaluate_binder(binder_spec, execution_result)
```

Blackboard 的 binding 表是**唯一权威的运行时状态镜像**——L2.5 / Inner Loop / Supervisor 都从它读，避免各自维护一套 scene state。

### 11.5.3 Semantic Binder：VLM-primary + rule-fallback

每个 deferred reference 的绑定声明：

```json
"?base_bowl": {
  "binding_method": "vlm_semantic_query",
  "query": "Which bowl is the most suitable as the stack base? Consider size (larger = more stable), surface flatness, current stability on table, and accessibility. Output one bowl ID with one-sentence reason.",
  "candidate_set": "all_bowls_in_scene",
  "output_schema": {"chosen": "string", "reason": "string"},
  "fallback_rule": "nearest_to_centroid(all_bowls)",
  "fallback_trigger": "vlm_latency > 500ms OR vlm_confidence < 0.6 OR vlm_output_invalid"
}
```

三种 `binding_method`：

| method | 含义 | 用途 | 成本 |
|---|---|---|---|
| `compute` | 纯计算，调用确定函数 | `centroid_of`, `nearest_to`, `position_of`, `all_except`, `remove` 等 | <1ms |
| `vlm_semantic_query` | VLM 看 scene + query 决定 | 选 base 碗、选下一个抓什么、判断 stack 是否稳定 | 100–300ms |
| `vlm_with_compute_fallback` | 优先 VLM，超时/失败回落 rule | 多数语义决策（需 reliability 兜底） | 100–300ms 或 <1ms |

**第一版冻结的 compute binder 集合**（约 10 个）：

```
centroid_of(set)
nearest_to(point, from=set)
farthest_from(point, from=set)
random_choice(set)
all_except(set, item)
remove(set, item)
union(set1, set2)
intersect(set1, set2)
position_of(object)
bounding_box_of(set)
```

binder 函数集合是项目的**第二个窄腰**（第一个是 predicate dictionary）——所有模块只用这 10 个，不允许自由扩展（避免 schema 漂移）。

### 11.5.4 Runtime Constraint Generation

每个 step 可以声明一个 `runtime_constraint_query`，由 VLM 在 step 入口看 scene 后追加约束：

```json
{
  "stage": "pick_next_bowl",
  "binding_at_entry": {...},
  "runtime_constraint_query": {
    "prompt": "Before picking, scan the scene for new hazards: spilled liquid, user's hand, broken bowl edges, stack tilting? Output additional safety constraints if any.",
    "output_schema": {
      "additional_constraints": [
        {"pred": "...", "args": [...], "role": "safety", "reason": "..."}
      ]
    },
    "skip_if_scene_unchanged": true,
    "max_added_constraints": 3
  },
  "constraints": [...]
}
```

**关键约束**：
- `skip_if_scene_unchanged: true`：上一步到这一步 scene depth diff < threshold 时跳过 VLM call
- `max_added_constraints: 3`：限制 VLM 一次最多加 3 条，防止 prompt-injection 式约束爆炸
- 输出的 `pred` 必须来自冻结的 predicate dictionary——否则丢弃并记录 "VLM hallucinated predicate"

### 11.5.5 Affordance Refinement

某些 step（特别是 place / handover 类）需要在执行前 refine affordance：

```json
{
  "stage": "place_on_stack",
  "target": "?bowl_in_gripper",
  "affordance_refinement_query": {
    "prompt": "Look at the bowl currently in the gripper. Is it tilted or off-center in the grasp? If so, suggest an orientation adjustment for placement.",
    "output_schema": {
      "orientation_offset_deg": "number",
      "lateral_offset_cm": "number"
    },
    "skip_if_grasp_was_clean": true
  }
}
```

`skip_if_grasp_was_clean` 的判断来源：上一步 grasp 的 MPC 输出无 correction → grasp 干净 → 跳过 refinement。

### 11.5.6 L2.5 Controller（预算 + 缓存 + skip + fallback）

这是 L2.5 的"工程心脏"——所有 VLM 调用都要走它：

```python
class L25Controller:
    def __init__(self, vlm, blackboard, budget_ms_per_step=500):
        self.vlm = vlm
        self.bb = blackboard
        self.budget = budget_ms_per_step
        self.cache = LRUCache(maxsize=128)
        self.scene_diff_threshold = 0.05
        self.budget_consumed_this_step = 0
    
    def resolve_binding(self, deferred_ref):
        # 1. Cache hit on (query, scene_hash)
        key = (deferred_ref.query_hash, self.bb.scene_hash())
        if key in self.cache:
            return self.cache[key]
        
        # 2. Skip if scene unchanged and fallback available
        if (self.bb.scene_unchanged_since_last_call() 
            and deferred_ref.has_fallback()):
            return self._exec_fallback(deferred_ref)
        
        # 3. Budget check
        if self.budget_consumed_this_step + ESTIMATED_VLM_LATENCY > self.budget:
            return self._exec_fallback(deferred_ref)
        
        # 4. Actual VLM call
        t0 = time.time()
        result = self.vlm.query(
            deferred_ref.query,
            scene=self.bb.current_scene(),
            schema=deferred_ref.output_schema,
            timeout_ms=300,
        )
        elapsed = (time.time() - t0) * 1000
        self.budget_consumed_this_step += elapsed
        
        # 5. Validate
        if not self._validate(result, deferred_ref.output_schema):
            return self._exec_fallback(deferred_ref)
        
        self.cache[key] = result
        return result
    
    def reset_per_step_budget(self):
        self.budget_consumed_this_step = 0
```

设计要点：

- **Cache key 是 (query_hash, scene_hash)**：同 scene 同 query 不重算
- **Scene hash 用 depth-image 低分辨率 hash**，对相机抖动不敏感
- **Skip 默认走 fallback rule**，rule 在多数 case 上和 VLM 等价
- **Budget 是 per-step**，跨 step 重置——单步内最多 500ms 的 L2.5 开销
- **Validate failure 也走 fallback**——VLM 输出不符合 schema（如不在 candidate set 内、predicate 不在 dict 内）当作"VLM 不可用"

### 11.5.7 Worked Example：散落三个碗

完整 plan 模板见 conversation log 中的 "scattered bowls + semantic binder" template。执行 trace：

```
t=0  Plan 进入 L2.5：解析 binding_initialization
     - ?base_bowl: VLM call → "bowl_2 because it's most centrally positioned"
     - ?stacking_center: compute → position_of(bowl_2) = (0.4, 0.0, 0.76)
     - ?bowls_to_pick: compute → {bowl_1, bowl_3}

t=0+ Step 1 establish_base 进入 L2.5：
     - 无 deferred refs 需要解析
     - runtime_constraint_query: skip (scene unchanged)
     执行（no-op observe）
     更新 blackboard: ?stack_top := bowl_2

t=1  Step 2 pick_next_bowl/iter_1 进入 L2.5：
     - ?next_bowl_to_pick: VLM call → "bowl_1, closer and unoccluded"
       (or cache fallback if scene unchanged)
     - runtime_constraint_query: VLM looks at scene → adds {collision_free(gripper, bowl_3)}
     - affordance_region: VLM call → "the outer rim of bowl_1 facing the robot"
     执行 pick
     更新 blackboard: ?bowl_in_gripper := bowl_1, ?bowls_to_pick := {bowl_3}

t=2  Step 3 place_on_stack/iter_1 进入 L2.5：
     - affordance_refinement_query: skip (MPC reported clean grasp)
     执行 place
     更新 blackboard: ?stack_top := bowl_1, ?bowl_in_gripper := null

t=2+ milestone_replan_trigger=true → L3 Supervisor 介入：
     - decision: continue (plan structurally OK, just bindings advanced)

t=3  Step 4 pick_next_bowl/iter_2 进入 L2.5：
     ... 类似 t=1，但 candidate set 只有 bowl_3

t=4  Step 5 place_on_stack/iter_2 进入 L2.5：
     ... 类似 t=2
```

整个执行中 VLM 被调用约 **5–8 次**（多数 cache 命中或 skip），总 L2.5 开销 ~1.5s，分摊到 5 个 step 平均每步 300ms 增量——可接受。

### 11.5.8 L2.5 与 L3 Supervisor 的分工（见 §8.1）

详细对比表见 §8.1。要点重述：

- L2.5 **从不修改 plan 结构**——只填空 + 加约束
- L3 **从不解析单个 binding**——只判断"plan 结构是否还合理"
- 如果两者都能处理（如"剩余 plan 还能跑吗"），优先 L2.5（更轻），失败再升 L3

### 11.5.9 训练数据影响

现有 V2 schema 的 plan 全是 hardcoded reference（"bowl_1" / "bowl_2"），需要做一次 **deferred reference 改造**：

| 改造项 | 方法 | 成本 |
|---|---|---|
| Hardcoded object IDs → `?refs` | 规则改写（pattern matching） | 半天，自动 |
| 添加 `binding_initialization` 字段 | LLM-assisted 标注（gpt-5-mini） | 1 天，半自动 |
| 添加 `vlm_semantic_query` 的 query 文本 | 手动 + LLM 模板 | 2 天，需要审核 |
| 添加 `runtime_constraint_query`（可选） | 仅高价值任务标注 | 选择性，3–5 天 |

**保守迁移路径**：先只迁移 stacking / pick-place 类多步任务（约 ~30% 数据 ≈ 8k 条），其他保持 hardcoded。第一版训练效果好再扩到全量。

---

## 12. MVP 实施路线

### 12.1 Scope 选择
推荐 **P1（grounding 路径）+ P2 简化版（constraint shielding）**，把 P3（plan-conditioned VLA）放到 future work。

| 路径 | 核心 claim | 复用现有工作 |
|---|---|---|
| **P1** | 训过的 VLM 出 affordance region + LangSAM > zero-shot VLM 出 keypoint | V2 LoRA 70% 已完成 |
| **P2 简化版** | constraint-projection MPC 让通用 VLA 在 safety-critical 任务上不碰撞 | 套 OpenVLA 黑盒，不自训 VLA |

### 12.2 6 个月 milestone（含 v2 新增的双臂目标）

| 月 | 交付 |
|---|---|
| M1 | Predicate dictionary v1（18 个 predicate，`evaluate` + `cost` 双实现）+ schema migration script |
| M2 | V2 LoRA 训练数据迁移到 predicate schema；重训 + score.py 加 predicate-level metric |
| M3 | Embodiment Grounder v1（IK-based reachability + 启发式 arm assignment + handover 模板）|
| M3 | MPC v1（constraint projector，运行在 RGB-D 点云上）|
| M4 | Rule-based supervisor stub + 三条线失败处理 |
| M4 | Isaac Lab 上跑通单臂 + 双臂 4 个 task 的 closed-loop demo |
| M5 | OpenVLA 集成（黑盒先验路径）；A/B/C ablation：grounding only / + projection / + supervisor |
| M6 | 双臂 handover benchmark 评测 + paper draft 第一版 |

### 12.3 首批 task（含双臂）

```text
单臂：
  1. push object to target spatial relation
  2. pick and place with obstacle avoidance
  3. stack three same-size bowls

双臂：
  4. handover: 把杯子从左桌交给右臂放到右桌
  5. co-manipulation: 双手抬箱子
  6. parallel: 左臂扶罐 + 右臂拧盖
```

### 12.4 平台选择（待定）
推荐 **Isaac Lab**（仓库已有 `isaac_integration/`），原因：原生支持双臂 + RGB-D + URDF + IK，与 v2 架构完全匹配。备选 RoboCasa（家居场景丰富）和 LIBERO（评测标准化）。

---

## 13. 与 v1 outline 章节对照表

| v1 章节 | v2 状态 | v2 对应位置 |
|---|---|---|
| §0 背景 | 保留 | 本文 §0 |
| §1 系统定位 | 保留 + 五条纪律 | 本文 §1 |
| §2 总体架构 | **重写** 加 Grounder + Supervisor | 本文 §2 |
| §3 Perception | **简化** RGB-D 直出点云 | 本文 §6 / §11 |
| §4 VLM | **拆分** Planner（§4） + Supervisor（§8） | 本文 §4 / §8 |
| §5 Affordance Grounding | **简化** 砍掉 8 级 filter | 本文 §6 |
| §6 VLA | 大致保留，明确不需要 constraint-conditioned | （v1 §6 仍可参考） |
| §7 MPC / World Model | **修订** 限定为 constraint projector | 本文 §7 |
| §8 Execution loop | 保留 | （v1 §8 仍可参考） |
| §9 操作点幻觉 | 已被 affordance_region + LangSAM 解决 | 本文 §6 / §11 |
| §10 顺序问题 | **拆分** sequencing vs synchronization | 本文 §10 |
| §11 4×4 失败矩阵 | **替换** 三条线 | 本文 §9 |
| §12 中间表示 | 部分被 predicate dict 取代 | 本文 §3 |
| §13 MVP | **替换** 6 个月 milestone | 本文 §12 |
| §14 评估指标 | 保留 + 加 predicate-level | （需新增评测脚本）|
| §15 消融 | 保留 + 加 supervisor 消融 | （v1 §15 仍可参考）|
| §16 创新点 | **收紧** P1 + P2 双重 claim | 本文 §12 |
| §17 命名 | 保留 | （v1 §17 仍可参考）|
| §18 后续问题 | 多数已答 | 本文 §14 |

---

## 14. v2 未解决的开放问题

1. **Predicate dictionary 的边界**：18 个够不够？例如 "pouring"、"stirring" 这类连续动作如何 predicate 化？
2. **VLA 选型最终决定**：OpenVLA / π0 / RDT / 自训？需要 benchmark 双臂任务上的现成 VLA 表现。
3. **Embodiment Grounder 的 IK solver 速度**：每步 plan 都做 IK 检查在 closed-loop 里是否够快？需要 benchmark cuRobo / Pinocchio / KDL。
4. **Co-manipulation 的 VLA 同步**：单 VLA 实例如何同时给两臂出动作？双 VLA 实例如何同步？这部分 v2 没给完整答案。
5. **Supervisor 何时升级到 VLM**：rule stub 的覆盖率达到多少时再引入 VLM supervisor？什么 trigger 条件下用 VLM 而不是 rule？
6. **Sim-to-real**：所有约束、reachability、handover 模板在 sim 里调通后，real robot 的 perception 噪声会让多少策略失效？需要明确 sim-to-real gap 的处理路线（先 sim only 发 paper 还是 sim+real demo）。
7. **Failure context 编码**：replan 时 failure context 怎么序列化给 VLM-planner 才能让它产生不同于上次的 plan？（避免 loop）
8. **VLM-Binder vs VLM-Supervisor 是否同模型不同 prompt？** 推荐 yes（一份 LoRA），但要 benchmark 同模型在两种 prompt 下的稳定性是否够；若不够，是否需要分别训两个 adapter？
9. **L2.5 budget 调优**：500ms/step 是否合理？不同复杂度任务（pick-place vs 双臂 handover）应该用不同 budget？budget 满了走 fallback 的覆盖率需要 monitoring metric。
10. **Binder 函数集合的边界**：10 个 compute binder + 若干 semantic binder 够不够？跨任务复用率如何？需要类似 predicate dict 的"使用率统计"。
11. **训练数据 deferred reference 改造范围**：是否要全量 26k V2 plans 都改？还是选择性改 multi-step 任务？改造后 VLM 训练目标是"会输出 ?refs + binders"——这本身需要新评测维度（binder 选择正确率、query 文本合理性）。
12. **L2.5 cache 失效策略**：scene_hash 用 depth low-res hash 是否对相机抖动鲁棒？多人 / 多 viewpoint 系统怎么共享 cache？
13. **Milestone replan vs Full replan 的策略阈值**：L2.5 rebind 几乎免费、L3 refine 一次 VLM call、L3 full replan 重新生成整个 plan——三档之间什么条件下升级？

---

## 15. 总结

v2 框架的核心简化和强化：

```text
简化：
  - 砍 World Model 三层模型 → MPC 只做 constraint projection
  - 砍 8 级 affordance filter → LangSAM + depth lift
  - 砍 4×4 失败矩阵 → 三条线
  - 砍复杂 3D scene construction → RGB-D 直接给点云

强化：
  - 新增 Predicate Dictionary（项目第一窄腰）
  - 新增 Embodiment Grounder（解决 VLM 运动学盲区 + 双臂）
  - 新增 VLM-Supervisor 旁路（L3 战略层异常检测）
  - 新增 Temporal Predicates（handover 时序约束）
  - 拆开 Sequencing vs Synchronization 约束
  - 新增 Deferred References + Scene Blackboard（plan 层 closed-loop）
  - 新增 L2.5 Semantic Resolver（runtime VLM 持续参与，靠 cache/skip/fallback 不阻塞）
  - 新增 Binder 函数集合（项目第二窄腰）

研究 claim 收紧：
  - P1: VLM-trained affordance region + LangSAM > zero-shot keypoint
  - P2 (简化版): constraint-projection MPC 减少 VLA 碰撞
  - P3: 留作 future work

L2.5 引入后新增的可证伪 claim：
  - 在散落 / 长尾任务上，L2.5 (VLM-primary binder) > rule-only binder
  - L2.5 的 cache + skip + fallback 让 VLM-in-loop 的平均开销 < 300ms/step
```

**最核心的设计纪律**：

> 五层 stack + 一个 per-step gate（L2.5）+ 一条旁路 supervisor（L3）；**四个** frequency band；**两份**冻结字典（predicate dict + binder set）；一份共享的 Scene Blackboard。
>
> VLM 不知道身体；MPC 不预测未来；Supervisor 不修改动作；L2.5 不修改 plan 结构；VLA 不验证安全。
>
> 每个模块只做自己擅长的事；VLM 的 world knowledge 在 runtime 通过 cache/skip/fallback **经济地**参与，而不是阻塞或缺席。
