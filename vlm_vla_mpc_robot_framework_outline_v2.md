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
| MPC 限定为 constraint projector（无 forward dynamics） | **Hybrid MPC（Stage A/B/C with PointWorld）**：A = constraint projector（默认）；B = PointWorld 单步预测（接触瞬间 / 关键事件）；C = PointWorld CEM/MPPI 多步优化（contact-rich / 双臂耦合）。Mode 由 VLM plan 的 `mpc_mode` hint 或 L2.5 动态选择 | 单纯 constraint projector 看不到 H 步后的延迟违反（"推 5 步后碗会倾倒"）；PointWorld always-on 又太贵——按任务复杂度三档 **lazy evaluation of expensive predictions** |
| 单向 pipeline：VLM → 执行；失败再 replan | **执行前 plan-critique-revise 闭环（§11.6）**：VLM 出 plan v0 → PointWorld + VLA dry-run 评估 → Critique Synthesizer 反馈 → VLM 修订 → ≤ 3 次迭代收敛后开始执行；执行中保留轻量版同机制（接到 L3 supervisor） | 单向 pipeline 把所有错误推到 runtime catch，开销大、cascading failure 频繁；pre-execution refinement 用 ≤ 30s 换 minutes 级 runtime 失败成本 |
| Embodiment Grounder "启发式 + IK"（未指定栈） | **5 子组件具体栈**：cuRobo（首推）做 IK + collision；WorkspaceMap 预计算 voxel reachability（μs lookup）；ArmAssigner 启发式打分 + L2.5 VLM fallback；HandoverPlanner 模板化；CoManipulationDetector 规则触发 | 含糊技术选型导致工程不可估时；cuRobo 与 PointWorld **共享 GPU + URDF + mesh**，infra 复用避免双套维护 |

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
              │  VLM-Planner (RoboBrain LoRA) │   plan v0
              │  (embodiment-agnostic)        │   • <think> + Goal + Scene
              └───────────────────────────────┘   • per-step ?refs + binders
                              │                   • mpc_mode hints
                              │                   • refinement_recommendation
                              ▼
  ╔═══════════════════════════════════════════════════════════════════╗
  ║  Pre-Execution Refinement Loop  (§11.6, N ≤ 3 iter, ~30s budget)   ║
  ║                                                                     ║
  ║    ┌──────────────────────┐    ┌──────────────────────┐           ║
  ║    │  PointWorld          │    │  VLA (forward-pass    │           ║
  ║    │  全 plan rollout     │    │   only, no execute)   │           ║
  ║    │  → predicted traj    │    │  → action entropy     │           ║
  ║    │  → violation report  │    │    per stage          │           ║
  ║    └──────────┬───────────┘    └──────────┬────────────┘           ║
  ║               └────────────┬─────────────-┘                         ║
  ║                            ▼                                         ║
  ║    ┌──────────────────────────────────────────────────┐             ║
  ║    │  Critique Synthesizer (root-cause analysis)       │             ║
  ║    └──────────┬───────────────────────────────────────┘             ║
  ║               ▼                                                       ║
  ║    ┌──────────────────────┐                                          ║
  ║    │  converged? (process │ ── no ──→ VLM revise(plan, critique)     ║
  ║    │  + goal + VLA conf)  │             ↑ loop back                  ║
  ║    └──────────┬───────────┘                                          ║
  ╚═══════════════│═══════════════════════════════════════════════════════╝
                  ▼ yes / budget exhausted → refined plan
              ┌───────────────────────────────┐
              │  Embodiment Grounder (§5.6)    │
              │  • cuRobo IK + collision       │
              │  • WorkspaceMap (precomputed) │
              │  • ArmAssigner + L2.5 fallback│
              │  • HandoverPlanner template   │
              │  • CoManipulationDetector     │
              └───────────────────────────────┘
                              │ embodiment-grounded plan (?refs 未解析)
                              ▼
  ╔═══════════════════════════════════════════════════════════════════╗
  ║  Per-Step Entry — L2.5 Semantic Resolution (§11.5, 0.5–2 Hz)       ║
  ║   VLM-Binder + VLM-Refiner + Affordance Grounding                  ║
  ║   + Scene Blackboard (单一权威 binding 表)                          ║
  ║   + PointWorld preview query (可选)                                 ║
  ╚═══════════════════════════════════════════════════════════════════╝
                              ↓ resolved step (concrete targets + cstrs)
   ╔══════════════════════════════════════════════════════════════════╗
   ║  Inner Loop (L1+L2, 10–30 Hz; lower with Stage C)                 ║
   ║                                                                    ║
   ║   obs_t (RGB-D) → Perception → point_cloud_t                      ║
   ║   point_cloud_t, plan → VLA → a_t                                 ║
   ║              ↓                                                     ║
   ║   ┌───────────────────────────────────────────────────────┐      ║
   ║   │  MPC Selector (per stage's mpc_mode, §7)               │      ║
   ║   │   Stage A: constraint_projector(state, a_t)           │      ║
   ║   │   Stage B: pointworld_singlestep(pc_t, a_t)            │      ║
   ║   │   Stage C: pointworld_cem(pc_t, a_t, H=8, K=64)        │      ║
   ║   └───────────────────────────────────────────────────────┘      ║
   ║              ↓                                                     ║
   ║   Stage A sanity check (always on; tier above's a_t* 再过一遍)    ║
   ║              ↓                                                     ║
   ║   robot.execute(a_t*)                                             ║
   ║                                                                    ║
   ║   PointWorld Diagnostic (every N step):                           ║
   ║     compare predicted vs observed → if drift > θ:                 ║
   ║       flag supervisor → downgrade_mpc_mode                        ║
   ╚════════════════════════════════════════════════════════════════════╝
                              │ stage complete / anomaly / drift
                              ▼
              ┌───────────────────────────────┐
              │  VLM-Supervisor (L3, §8)       │   旁路, 事件驱动
              │  + During-Execution Refinement │   ≤ 1 iter, ~1–2s
              │    (§11.6.5)                   │
              └───────────────────────────────┘
                              │
                              ▼
              continue / advance_stage / downgrade_mpc_mode /
              refine / full_replan / abort
```

**主线 + gates + 旁路总览**：
- 主线 A（planning）：VLM-planner → **Pre-Execution Refinement Loop（§11.6）** → Embodiment Grounder（§5.6）
- **Per-step gate（L2.5，§11.5）**：VLM-Binder + VLM-Refiner + Affordance Grounding，每个 step 进入前解析 `?refs`、读 / 写 Scene Blackboard；可选 PointWorld preview。**默认在 main loop 内**，靠 cache / skip / fallback 不阻塞。
- 主线 B（execution）：VLA → **Hybrid MPC A/B/C（§7）** → robot；Stage B/C 依赖 PointWorld
- 旁路（supervision，§8）：VLM-supervisor + **During-Execution Refinement（§11.6.5）**，事件驱动，权限战略层（改 plan 结构 / 调 MPC mode / 终止任务）

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

### 4.3.1 v2 后续扩充的新字段（PointWorld + Refinement 引入）

随 §7（Hybrid MPC）和 §11.6（Pre-Execution Refinement）的引入，VLM-Planner schema 增加以下字段：

**Top-level 字段**：

```json
{
  "task": "...",
  "refinement_recommendation": "skip | pointworld_only | full",
  "_refinement_reason": "Bimanual co-manipulation with hot liquid; high process violation risk"
}
```

`refinement_recommendation` 由 VLM 在初始 plan 时输出，控制 Pre-Execution Refinement Loop 的深度：
- `skip`：单步任务、简单 pick-place，跳过 refinement 节省 30s
- `pointworld_only`：多步任务、有动力学依赖，但 VLA 训练分布内
- `full`：contact-rich / 双臂耦合 / 高风险，PointWorld + VLA 双 critic 全开

**Per-stage 字段**（针对 MPC 选档）：

```json
{
  "stage": "lift_pot_off_stove",
  "mpc_mode": "A_constraint_projector | B_pointworld_singlestep | C_pointworld_cem",
  "mpc_horizon": 8,
  "pointworld_focus_objects": ["pot", "stove"],
  "pointworld_ignore_regions": ["far_background"],
  "_mode_reason": "co-manipulation with potentially liquid contents"
}
```

- `mpc_mode`：默认 `A`，VLM 主动升档时显式标注（见 §7.2）
- `mpc_horizon`：仅 mode=C 时有效，CEM/MPPI 的 H 步预测窗口
- `pointworld_focus_objects` / `pointworld_ignore_regions`：让 PointWorld 只 rollout 相关子集（见 §7.6.2），单步延迟显著下降

**Deferred reference 字段**（已在 §11.5 定义）：`binding_initialization` / `binding_at_entry` / `binding_after_completion` / `contact_spec` / `temporal_constraints` / `runtime_constraint_query` / `affordance_refinement_query` / `supervisor_check_after` / `milestone_replan_trigger`。

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

### 5.6 Concrete Tech Stack

> Embodiment Grounder 是框架里**唯一不用 learning** 的核心模块——纯经典 robotics。优势：可证明性强、跨场景稳定、零数据需求。

#### 5.6.1 ReachabilityEngine（IK + collision）

三个候选：

| 选项 | 优势 | 劣势 | 单 IK 延迟 | 推荐场景 |
|---|---|---|---|---|
| **cuRobo (NVIDIA)** | GPU batched IK；内置 SDF collision；differentiable（与 MPC Stage C 集成友好）；与 Isaac Lab 原生兼容 | 需要 CUDA；setup 较复杂 | **1–5 ms (batched)** | **首推**，特别是已用 Isaac 或选了 PointWorld 的场景 |
| Pinocchio + hpp-fcl | CPU 稳定；工业级精度；无 GPU 依赖 | batched 慢；collision wire 自己做 | 5–15 ms | CPU-only 平台 |
| TracIK + MoveIt | ROS 友好；社区大 | python 接口不流畅；collision check 慢 | 20–50 ms | 已在 ROS 生态 |

**推荐 cuRobo**：(1) 与 PointWorld 共享 GPU；(2) differentiable IK 让 Stage C CEM/MPPI 可梯度回传；(3) Isaac Lab 集成最直接。

#### 5.6.2 WorkspaceMap（离线预计算）

每次 IK 查询 ~5ms，plan 阶段几十个候选 → 累计 100+ ms。用预计算 voxel grid 加速：

```python
class WorkspaceMap:
    """离线生成的每臂可达性映射。1cm voxel grid 覆盖工作空间。"""

    def __init__(self, urdf, arm_id, resolution=0.01):
        self.grid = self._precompute_reachability(urdf, arm_id, resolution)
        # 离线：对每个 voxel center 跑 IK，记录 (reachable, manipulability_score)

    def quick_check(self, point_3d) -> bool:
        """O(1) lookup，~1μs"""
        return self.grid[self._point_to_voxel(point_3d)].reachable

    def manipulability(self, point_3d) -> float:
        """Yoshikawa index——可达点的"舒展度"，用于 arm 选择"""
        return self.grid[self._point_to_voxel(point_3d)].manipulability
```

**两阶段策略**：先 `quick_check()` voxel lookup（1μs）筛掉 99% 候选 → 通过的再走完整 IK（5ms）拿 joint config + 精确 collision。

预计算成本：单臂全空间 ~1 小时 GPU，部署时缓存复用。

**双臂的 shared workspace**：

```python
def handover_zone_center(left_map, right_map):
    shared = [v for v in left_map.grid
              if left_map.grid[v].reachable and right_map.grid[v].reachable]
    return centroid([v.center for v in shared])
```

#### 5.6.3 ArmAssigner（启发式 + L2.5 VLM fallback）

```python
def assign_arm(target_3d, robot_state, workspace_maps, current_holder):
    # 1. 物体连续性：某只手已握相关物体则优先继续用
    for arm in ["left", "right"]:
        if current_holder[arm] is not None and is_relevant(current_holder[arm], target):
            if workspace_maps[arm].quick_check(target_3d):
                return arm

    # 2. 可达性筛选
    reachable = [a for a in ["left", "right"] if workspace_maps[a].quick_check(target_3d)]
    if not reachable:
        return None              # → 触发 handover 检测
    if len(reachable) == 1:
        return reachable[0]

    # 3. 双臂都可达——打分
    scores = {}
    for arm in reachable:
        manip = workspace_maps[arm].manipulability(target_3d)
        dist = np.linalg.norm(target_3d - robot_state[arm].base_pos)
        idle = float(current_holder[arm] is None)
        scores[arm] = 0.5 * manip - 0.3 * dist + 0.2 * idle

    # 4. 打分接近（< 5%）→ 触发 L2.5 VLM fallback
    if abs(scores["left"] - scores["right"]) < 0.05 * max(scores.values()):
        return None              # 上层 L2.5 用 vlm_semantic_query 决策

    return max(scores, key=scores.get)
```

#### 5.6.4 HandoverPlanner（模板化）

参数化插值 §5.4 的 HANDOVER_TEMPLATE：

```python
def insert_handover(from_arm, to_arm, obj, scene, workspace_maps):
    handover_pos = handover_zone_center(workspace_maps["left"], workspace_maps["right"])
    sub_steps = []
    for tpl in HANDOVER_TEMPLATE:
        s = tpl.instantiate(src=from_arm, tgt=to_arm, obj=obj, handover_pos=handover_pos)
        if not workspace_maps[s.arm].quick_check(s.target_3d):
            raise HandoverInfeasible(f"{s.arm} cannot reach handover position")
        sub_steps.append(s)
    return sub_steps
```

所有 handover 共用模板——多样性靠 MPC trajectory 层补足。**Grounder 不做选择，只做翻译**。

#### 5.6.5 CoManipulationDetector（规则）

```python
def detect_co_manipulation(grounded_step):
    cs = grounded_step.get("contact_spec")
    if cs is None: return False
    if cs.get("coordination") in ["simultaneous", "simultaneous_co_manipulation"]:
        return True
    if cs.get("min_contacts", 1) >= 2:
        return True
    return False
```

VLM plan 里 `contact_spec` 已明确表达，Detector 只把 flag 翻译成 MPC 模式（启用双臂耦合约束）。

#### 5.6.6 Multi-Embodiment Plugin 设计

```python
class EmbodimentGrounder:
    @classmethod
    def from_embodiment_spec(cls, spec_path):
        spec = load_yaml(spec_path)   # URDF 路径、arm_ids、camera_extrinsics
        return cls(
            ik_solver=cuRobo.from_urdf(spec.urdf),
            workspace_maps={arm: WorkspaceMap.precompute(spec, arm)
                            for arm in spec.arm_ids},
        )
```

部署时按 embodiment 加载不同 spec，**VLM / Predicate dict / Scene Blackboard 都不动**——这是 D3 "VLM embodiment-agnostic" 的回报：换机器人只换 Grounder 配置。

#### 5.6.7 与 PointWorld 共享 URDF / mesh

如果 §7 选了 PointWorld，**Grounder 和 PointWorld 必须共享同一份 URDF + collision mesh**：

```
shared_robot_assets/
├── panda_left.urdf / panda_right.urdf
├── meshes/                  ← 视觉
└── collision_meshes/        ← 简化版，Grounder + PointWorld 共用
```

**硬约束**：部署时校验 mesh hash 一致，不一致直接报错——否则会出现"Grounder 觉得可达但 PointWorld 预测撞了"这类难调试 bug。

#### 5.6.8 时间线

| 阶段 | 交付 | 时间 |
|---|---|---|
| Week 1 | cuRobo 装好 + URDF 加载 + 单元 IK 测试 | 3 天 |
| Week 1 | WorkspaceMap 预计算 + quick_check | 2 天 |
| Week 2 | ArmAssigner 启发式 + L2.5 hook | 3 天 |
| Week 2 | HandoverPlanner + 模板落实 | 2 天 |
| Week 3 | 端到端 demo + CoManipulationDetector | 5 天 |

3 周一个 ready-to-integrate 的 Grounder，**无 research 不确定性**。

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

## 7. MPC（Hybrid A/B/C with PointWorld）

### 7.0 设计变更：v2 早期的"World Model 砍掉"反转

v2 初稿（见 §0 早期 diff）曾把 MPC 限定为 constraint projector，明确砍掉 World Model 这个 paper claim。理由：Stage B/C（object-centric dynamics / point-flow world model）是独立研究方向，超出 scope。

**修订**：本节引入 **PointWorld** 作为 learned world model，但**不是 always-on**，而是按任务复杂度 **lazy evaluation of expensive predictions** —— 三档共存，按需启用。这样既复活了"Predictive Action Shielding"的论文 claim，又避免简单任务被 PointWorld 拖慢。

### 7.1 三档 MPC

| 档位 | 何时启用 | 预测方式 | 评估对象 | 单步延迟 |
|---|---|---|---|---|
| **A. Constraint Projector**（默认）| 简单 pick-place、approach、retreat | FK + rigid attach（确定性） | 单步后 state | < 5 ms |
| **B. PointWorld Single-Step** | 接触发生时（grasp 闭合 / push 启动 / handover 接触瞬间） | PointWorld 1 步预测 | 单步后 point cloud | 30–80 ms |
| **C. PointWorld CEM/MPPI** | 高风险 / contact-rich / 双臂耦合（端锅、倒水、推堆叠物） | PointWorld H 步 rollout × K 候选 | H 步内累计 cost | 200–500 ms |

### 7.2 Mode 选择机制

**主入口**：VLM-Planner 在每个 stage 上加 `mpc_mode` hint：

```json
{
  "stage": "lift_pot_off_stove",
  "mpc_mode": "C_pointworld_cem",
  "mpc_horizon": 8,
  "pointworld_focus_objects": ["pot", "stove"],
  "_reason": "co-manipulation with potentially liquid contents"
}
```

**动态升档**：L2.5 在 step 入口看 scene 后可建议升档（如"现在锅里看起来有液体，升 C 档"）。

**动态降档**：L3 Supervisor 监控 PointWorld 预测误差，发现 OOD 或预测漂移时强制降回 Stage A（见 §7.6.3）。这是兜底机制。

### 7.3 Stage A 实现：Constraint Projector

\[
a^* = \arg\min_a \|a - a_{vla}\|^2 \quad \text{s.t.} \quad \forall i: c_i(\text{kinematic\_forward}(s_t, a)) \leq 0
\]

`kinematic_forward` 仅做 FK + rigid attach（被抓物体跟随 gripper），不预测物体动力学。

```python
def stage_A_mpc(state, a_vla, active_constraints, embodiment):
    pred_state = kinematic_forward(state, a_vla, embodiment)
    hard_violations = [c for c in active_constraints
                       if c.role == "safety" and not c.evaluate(pred_state)]
    if not hard_violations:
        return Accept(a_vla)
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

### 7.4 Stage B 实现：PointWorld Single-Step

```python
def stage_B_mpc(pc_t, a_vla, active_constraints, focus_objects):
    pc_pred = pointworld.predict_single_step(pc_t, a_vla, focus_objects)
    # 在预测点云上评估 predicate（用 cost_on_pointcloud，见 §7.6.1）
    violation = sum(c.cost_on_pointcloud(pc_pred, c.args)
                    for c in active_constraints if c.role == "safety")
    if violation < HARD_VIOLATION_THRESHOLD:
        return Accept(a_vla)
    # 邻域采样修正（同 Stage A 思路，但 cost 来自 PointWorld 预测）
    candidates = sample_around(a_vla, K=64, sigma=0.02)
    valid = []
    for a in candidates:
        pc_p = pointworld.predict_single_step(pc_t, a, focus_objects)
        v = sum(c.cost_on_pointcloud(pc_p, c.args) for c in active_constraints if c.role == "safety")
        if v < HARD_VIOLATION_THRESHOLD:
            cost = sum(c.cost_on_pointcloud(pc_p, c.args) for c in active_constraints) \
                 + LAMBDA_V * np.linalg.norm(a - a_vla)
            valid.append((cost, a))
    if not valid:
        return Reject(reason="no_valid_correction_stageB")
    return Correct(min(valid)[1])
```

### 7.5 Stage C 实现：PointWorld CEM/MPPI

```python
def stage_C_mpc(pc_t, a_vla, active_constraints, focus_objects, H=8, K=64):
    dist = init_distribution(mean=a_vla, sigma=0.03)
    for cem_iter in range(3):  # 3 CEM iterations
        samples = dist.sample(K)             # K H-step sequences
        costs = []
        for a_seq in samples:
            pc_rollout = pointworld.rollout(pc_t, a_seq, focus_objects)  # H steps
            cost = 0
            for h, pc_h in enumerate(pc_rollout):
                cost += sum(c.cost_on_pointcloud(pc_h, c.args) * GAMMA**h
                            for c in active_constraints)
            cost += LAMBDA_V * np.linalg.norm(a_seq[0] - a_vla)
            costs.append(cost)
        elites = select_elites(samples, costs, n=8)
        dist.fit(elites)
    a_star_seq = dist.mean()
    return Correct(a_star_seq[0])   # 只执行第一步，下一时刻重 plan
```

`focus_objects` 让 PointWorld 只 rollout 相关物体子集——VLM 用 world knowledge 给 PointWorld 减负，单步延迟从 ~80ms 降到 ~20ms。

### 7.6 VLM ↔ PointWorld 的 5 个集成点

#### 7.6.1 Predicate dictionary 扩展为 point-cloud-evaluable

每个 predicate 加 `cost_on_pointcloud` 实现：

```python
class Predicate:
    def evaluate(self, state, args) -> bool: ...            # §3 已有
    def cost(self, state, args) -> float: ...                # §3 已有
    def cost_on_pointcloud(self, pc, args) -> float: ...     # 新增
```

实现细节：
- Spatial (above/on/inside)：先从 pc 估 object pose（centroid + PCA axis），走原 cost
- Contact / collision：直接 in-pc 距离查询
- Pose (upright)：从 pc 估主轴

**这件事必须先做**——否则 PointWorld 给的 pc 没法被 cost function 消费。

#### 7.6.2 VLM 标注 `pointworld_focus_objects`

VLM plan 里加：
```json
{
  "pointworld_focus_objects": ["cup", "knife", "plate"],
  "pointworld_ignore_regions": ["far_background", "static_walls"]
}
```

让 PointWorld 只对相关子集 rollout，单步延迟显著下降。**VLM 用 world knowledge 给 PointWorld 减负**——VLM 知道哪些物体相关、PointWorld 不知道。

#### 7.6.3 Supervisor 监控 PointWorld 预测误差

```python
def supervisor_check_world_model(predicted_pc, observed_pc):
    chamfer = compute_chamfer(predicted_pc, observed_pc)
    if chamfer > THRESHOLD:
        return Decision("downgrade_mpc_mode",
                        reason="PointWorld unreliable here",
                        target_mode="A_constraint_projector")
```

**关键兜底**：PointWorld 在当前 scene 上失效时自动降档，防止灾难性失败。

#### 7.6.4 L2.5 用 PointWorld 预测做 anomaly preview

详见 §11.5。L2.5 可以 query VLM "看一眼**预测的** future scene"，做语义判断（"这个 placement 看起来会让 stack 倾斜"），不评估 predicate。这是 VLM 与 world model 协同的最高级形式——VLM 用 common sense 判断 "这预测看起来对吗 / 会不会出事"。

#### 7.6.5 VLA + PointWorld mental sim（可选，第一版不做）

VLA 在 propose action 时用 PointWorld 做 mental simulation。超出"加 MPC"范围，进入"VLA + world model"研究（Dreamer-style），第一版**不做**。

### 7.7 双臂时序约束

`before`、`simultaneous`、`stable_for` 等 temporal predicate 不能在单步 MPC 里直接评估——需要**事件总线**：

```python
class EventBus:
    def emit(self, event_name, timestamp): ...
    def has_occurred(self, event_name) -> bool: ...
    def time_since(self, event_name) -> float: ...

# 执行循环中
if grasp_stable(right_arm, obj).evaluate(state):
    bus.emit("tgt_grasp_stable", now)

# MPC 评估 a_vla 时
def evaluate_temporal(constraint, state, bus):
    if constraint.pred == "before":
        e1, e2 = constraint.args
        if would_trigger(a_vla, e2) and not bus.has_occurred(e1):
            return False
    ...
```

事件总线在 Stage A / B / C 三档都共享——time predicate 的语义不依赖动力学预测方式。这一段是双臂 framework 最 tricky 的工程部分，但 predicate dictionary 把它收纳成有限几种情况，可控。

### 7.8 设计纪律（不要踩的坑）

- **不要砍 Stage A**——永远在，作为 sanity check + 兜底；Stage B/C 输出 a* 后再过一遍 Stage A geometric check
- **不要 always-on Stage C**——简单任务上是 overhead，且增加失败模式
- **不要让 PointWorld 决定 VLA 训练目标**——VLA 独立学 policy，避免训练数据共生导致的失败模式共生
- **双臂数据缺口要警惕**：DROID 单臂、Aloha 双臂但场景少——Stage C 在双臂上的 PointWorld 训练数据是**真问题**，影响 paper claim 可行性

### 7.9 风险清单

| 风险 | Mitigation |
|---|---|
| PointWorld 在接触 / 遮挡场景预测最不准（也是最需要它的时候）| Stage A 兜底 + Supervisor chamfer 监控 + OOD score gating |
| Compute 预算：Stage C 单步 200–500ms，10Hz 控制是上限 | Stage C 仅在关键 stage 启用；其他用 A 或 B |
| PointWorld + VLA 训练数据共生 → 失败模式共生 | 让 PointWorld 和 VLA 训不同数据子集（如不同 augmentation）或不同来源 |
| OOD：测试场景中未见过的物体 / 光照 | PointWorld self-uncertainty head + Supervisor 兜底 + Stage A fallback |
| 双臂场景 PointWorld 训练数据稀缺 | (a) Aloha + sim only；(b) bi-manual 退回 Stage A；(c) 收集专门数据 |

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
    "occlusion_severe",
    "pointworld_drift_high"
  ],
  "decision": "continue | advance_stage | refine | full_replan | abort | downgrade_mpc_mode",
  "rationale": "VLA pushing cup for 5s, cup center hasn't moved — likely contact failure",
  "replan_hint": "switch from push to pick-and-place",
  "refine_target_stages": [4, 5]
}
```

**5 种 decision 的边界**（升级链）：
1. `continue` → 一切正常
2. `advance_stage` → 当前 stage termination 已满足
3. `downgrade_mpc_mode` → PointWorld 在当前 scene 上不可靠（chamfer error 超阈），降回 Stage A（见 §7.6.3）
4. **`refine`** → 剩余 plan 可救但需调整：触发 **During-Execution Refinement Loop**（§11.6.5），只 revise `refine_target_stages` 标注的部分，N ≤ 1 iteration
5. `full_replan` → plan 结构已不合理：回到 VLM-Planner 重生成（带 failure context）
6. `abort` → 不可逆失败，停止

`refine` vs `full_replan` 的关键差异：refine 保留 plan 结构、只改具体 stages；full_replan 从零重生成。refine ~1–2s、full_replan ~5–10s——能 refine 就不 full_replan。

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

## 11.6 Pre-Execution Plan Refinement Loop（三方互馈收敛）

> 这一节扩展 §11.5 的闭环概念：**在执行开始之前**，VLM 与两个 grounded critic（PointWorld + VLA）进行多轮 critique-revise 迭代，让 plan 在 **物理可行性 + 执行可行性** 两个维度都收敛后再开始执行。这把 v2 框架从"单向 pipeline + runtime catch"演化成"sketch + verify + revise"。

### 11.6.0 为什么需要这层

v2 框架到 §11.5 为止，VLM 出的初始 plan 直接进入 Embodiment Grounder 和执行循环。但 **VLM 在 plan 生成时看不到**：

- **物理动力学**：push 5 步后碗会不会倾倒？倒水时液面是否平稳？
- **VLA 训练分布覆盖**：某个 affordance 描述是否在 VLA 见过的样本里？置信度高吗？
- **跨 stage 副作用**：stage 3 的放置会不会挡住 stage 5 的接近路径？

这些问题在 plan 阶段不解决，就只能在 runtime 通过 L3 supervisor 失败重 plan——开销巨大且经常 cascading failure。**Pre-Execution Refinement** 在执行前用 PointWorld + VLA 做"沙盘推演"，把可预见的问题在 plan 阶段就 fix。

### 11.6.1 三方互馈结构

```text
                   PointWorld
                       ↓ 物理可行性反馈
                       ↓ (predicted trajectory + violation report)
       ┌─────────────────────────────────────────────┐
       │           Critique Synthesizer               │
       │  • root cause analysis                        │
       │  • structured issues + suggested revisions    │
       │  • convergence metrics                        │
       └─────────────────────────────────────────────┘
                       ↓                  ↑
                       ↓                  ↑ 执行可行性反馈
                       ↓                  ↑ (per-stage action entropy)
                  VLM Planner          VLA
                  (revise plan)    (forward-pass only)
                       ↓
                  revised plan
                       ↓
                  (loop until converged or budget exhausted)
```

两个 critic 评估**不同维度**，互补不重复：
- **PointWorld critic**：评估 plan 在物理世界跑出来会怎样（process 约束 + goal 约束）
- **VLA critic**：评估 plan 的每个 stage 在 VLA 训练分布里有多熟悉（置信度 / OOD）

### 11.6.2 Process 约束 vs Goal 约束

承接 §3 predicate dictionary：

| 类别 | 对应 predicate | PointWorld 评估方式 |
|---|---|---|
| **Process 约束** | per-step `constraints` 中 role=safety / role=progress；以及 `temporal_constraints` | rollout 的**每一步**做 `predicate.cost_on_pointcloud()` → 累计 violation score |
| **Goal 约束** | plan top-level `goal` predicates；以及每个 step 的 `termination` predicates | rollout **终态**做 goal predicate evaluate → satisfied / 距 satisfied 还差多少 |

**两类必须同时满足**——只满足 process（VLA 全程小心走路）但不满足 goal（任务没完成）等于失败。**收敛判据严格 AND**。

### 11.6.3 Critique 格式

Critic 输出必须结构化、可定位、可执行：

```json
{
  "iteration": 1,
  "verdict": "needs_revision",
  "global_summary": "Plan reaches goal with probability 0.62. 2 process violations detected. 1 stage has low VLA confidence.",

  "issues": [
    {
      "stage_idx": 3,
      "stage_name": "place_on_stack",
      "issue_type": "predicted_constraint_violation",
      "violated_predicate": {"pred": "upright", "args": ["bowl_1"]},
      "violation_severity": 0.7,
      "evidence": "PointWorld rollout predicts bowl_1 tilts 25° during placement (threshold 15°). Root cause: transport stage didn't pre-align bowl orientation.",
      "suggested_revision_dimension": "modify_transport_stage_orientation"
    },
    {
      "stage_idx": 5,
      "stage_name": "grasp_pot_handle",
      "issue_type": "low_vla_confidence",
      "metric": {"vla_action_entropy": 2.8, "threshold": 1.5},
      "evidence": "VLA policy is high-entropy over this action; likely scene-OOD or ambiguous affordance description.",
      "suggested_revision_dimension": "refine_affordance_region_text"
    },
    {
      "issue_type": "goal_unreachable",
      "evidence": "Goal predicate `on(bowl_3, bowl_1)` predicted unsatisfied because plan only places 2 bowls. Missing stage.",
      "suggested_revision_dimension": "add_stage"
    }
  ],

  "convergence_metrics": {
    "process_violation_score": 1.2,
    "goal_satisfaction_prob": 0.62,
    "min_vla_confidence": 0.32,
    "all_satisfied_threshold": {"process": 0.3, "goal": 0.8, "vla_conf": 0.5}
  },

  "budget_remaining": 2
}
```

**`suggested_revision_dimension` 的设计意图**：critic 对 VLM 做**方向性**引导，不是具体改写。VLM 自己决定 "how"，critic 只告诉"where + why"。

### 11.6.4 Convergence Criteria 与 Budget

```python
def converged(critique):
    cm = critique.convergence_metrics
    return (cm.process_violation_score < cm.thresholds.process
            and cm.goal_satisfaction_prob > cm.thresholds.goal
            and cm.min_vla_confidence > cm.thresholds.vla_conf)

def refine_loop(initial_plan, max_iters=3):
    plan = initial_plan
    history = []
    for iter in range(max_iters):
        # 双 critic 并行评估
        pw_result = pointworld.simulate_plan(plan)     # ~5–10s
        vla_result = vla.evaluate_plan(plan)            # ~1–2s
        critique = synthesize(pw_result, vla_result)
        history.append((plan, critique))
        if converged(critique):
            return plan, "converged", history
        plan = vlm.revise(plan, critique)               # ~500ms
    # Budget 耗尽：选迭代过程中"最优"plan
    best = min(history, key=lambda x: refinement_score(x[1]))
    return best[0], "budget_exhausted", history
```

**预算**：
- **Pre-execution**：`max_iters=3`，总时长 < 30s
- **During-execution（§11.6.5）**：`max_iters=1`，~1–2s

### 11.6.5 跳过策略（性价比管理）

Refinement 不免费——30s pre-execution 延迟对简单任务是浪费。VLM 在初始 plan 输出 `refinement_recommendation`（见 §4.3.1）：

| recommendation | 含义 | 场景 |
|---|---|---|
| `skip` | 跳过 refinement，直接执行 | 单步任务、简单 pick-place、无 contact-rich dynamics |
| `pointworld_only` | 只跑 PointWorld critic，不跑 VLA critic | 多步任务、动力学依赖，但 VLA 训练分布内 |
| `full` | PointWorld + VLA 双 critic 全开 | contact-rich / 双臂耦合 / 高风险（端锅、倒水）|

**三档按需消耗** refinement budget，简单任务 0 延迟。

### 11.6.6 During-Execution Refinement（轻量版）

每个 stage 完成时（或 L3 supervisor 触发时），跑一次单轮 refinement：

```python
def during_execution_refine(remaining_plan, current_scene, history):
    pw_result = pointworld.simulate_plan(remaining_plan, scene=current_scene)  # ~2s
    # VLA critic 可选；多数 case 跳过省时间
    critique = synthesize(pw_result, vla_result=None)
    if converged(critique):
        return remaining_plan, "no_change"
    revised = vlm.revise(remaining_plan, critique, target_stages=critique.affected_stages)
    return revised, "refined"
```

**与 L3 supervisor 的关系**：
- supervisor 的 `decision: "refine"`（§8.3）触发本机制
- supervisor 的 `decision: "full_replan"` 跳过本机制，回 VLM-Planner 从零重生成
- supervisor 用 `refine_target_stages` 字段指定 refine 范围

### 11.6.7 VLA-as-Critic 的实现

VLA 不只是执行器，也是 **executability critic**。问题：让 VLA 评估而不执行？

**方式 A：Forward-pass-only**
- 喂给 VLA "当前 scene + plan stage 描述"，让它出 action distribution
- **不执行**，只看 distribution 的 entropy / 最大概率
- 高 entropy = 不知道做什么 = 低置信
- 单 stage 评估 ~50ms
- **第一版用 A**

**方式 B：VLA + sim rollout**
- 让 VLA 在 sim（用 PointWorld 当 sim）里跑完一遍 stage
- 看是否触发约束违反
- 单 stage 评估 ~500ms–1s
- 更准但贵，留给后续

**Calibration 问题**：现成 VLA（OpenVLA / π0）的 confidence 校准很差，单 forward pass 的 entropy 噪声大。Mitigation：
- (a) Fine-tune VLA 加个 confidence head
- (b) 用 ensemble VLA 做 disagreement-based uncertainty
- (c) 第一版 supervisor 不依赖 VLA confidence 作为 hard gate，只作 soft signal

### 11.6.8 Critique Synthesizer（翻译层）

Critic raw output → 文本 critique 这一步丢失信息。Synthesizer 是 IP 集中地——必须做**根因分析**而非现象报告：

```python
class CritiqueSynthesizer:
    def synthesize(self, pw_result, vla_result):
        issues = []

        # Process violations
        for violation in pw_result.violations:
            issue = {
                "stage_idx": self._trace_to_originating_stage(violation, pw_result.trajectory),
                "issue_type": "predicted_constraint_violation",
                "violated_predicate": violation.predicate,
                "violation_severity": violation.severity,
                "evidence": self._explain_root_cause(violation, pw_result.trajectory),
                "suggested_revision_dimension": self._suggest_revision(violation),
            }
            issues.append(issue)

        # Goal unreachability
        if not pw_result.goal_satisfied:
            issues.append({
                "issue_type": "goal_unreachable",
                "evidence": self._diff_predicted_vs_goal(pw_result.final_state, pw_result.goal),
                "suggested_revision_dimension": self._suggest_for_goal(pw_result),
            })

        # VLA low confidence
        if vla_result:
            for stage_idx, entropy in enumerate(vla_result.entropies):
                if entropy > VLA_ENTROPY_THRESHOLD:
                    issues.append({...})

        return Critique(issues=issues, metrics=self._compute_metrics(...))
```

**根因分析**的关键是**反向溯源 trajectory**：violation 是在哪个时刻发生的？那个时刻的 action 由 plan 的哪个 stage 决定？为什么那个 stage 的 constraints 没 catch？

### 11.6.9 风险与 Mitigation

| 风险 | Mitigation |
|---|---|
| **Mode collapse** —— VLM 退化到 VLA "舒适区"，舍 goal 求 process | Convergence 必须包含 goal_satisfaction_prob；critique weighting：goal 不满足 > process 违反 > VLA 低置信 |
| **Critic 系统性错误**（PointWorld OOD / VLA 校准差） → VLM 被误导 | PointWorld 先做 OOD score，高 OOD 时 critic 报 `low_critic_confidence`；VLM 看到此标记**减少改动**而非大改 |
| **Critique information bottleneck**（VLM 不知道改哪 stage） | Synthesizer 做根因分析；明确 `suggested_revision_dimension` |
| **Runaway iteration**（3 次都不收敛、振荡）| 检测 oscillation（plan 在两状态间反复跳）→ early stop；检测 diminishing returns → early stop；始终保留 initial plan 作为兜底 |
| **Pre-execution latency 把简单任务拖死** | `refinement_recommendation: skip` 跳过 |

### 11.6.10 实现路径

| Phase | 交付 | 时间 |
|---|---|---|
| P1 | PointWorld 集成 + Stage B/C MPC（§7）跑通 | 4–6 周 |
| P2 | Critique Synthesizer v1：PointWorld violation → 结构化 critique | 2 周 |
| P3 | VLM revise prompt + LoRA tune（让 VLM 学会消费 critique） | 2 周（含数据生成）|
| P4 | Pre-execution refinement pilot：3 个 task 验证收敛性 | 2 周 |
| P5 | VLA-as-critic 加入 | 2 周 |
| P6 | During-execution refinement 集成到 L3 supervisor | 2 周 |

总计 ~3–4 个月。Critical path：P1（PointWorld 必须先工作）→ P2（critique 质量决定 refinement 上限）。

### 11.6.11 训练数据缺口

VLM 需要被训练"会消费 critique"——现有 V2 plan 数据全是 "任务 → plan" 对，**没有 "任务 + 失败 critique → revised plan" 对**。

| 改造项 | 方法 | 成本 |
|---|---|---|
| 收集 (task + critique → revised plan) 数据 | 用 sim + PointWorld 自动生成 violation → 让 gpt-5-mini 写 revised plan | 1–2 周，半自动 |
| 数据量目标 | 1k–5k 条 critique-revise pair | — |
| 训练目标 | 在现有 V2 LoRA 基础上加 critique-revise 任务，多任务 fine-tune | 与 P3 合并 |

这是 P3 的隐藏成本，必须提前规划。

### 11.6.12 与 L3 Supervisor 的分工总结

| 维度 | L3 Supervisor | Pre-Execution Refinement | During-Execution Refinement |
|---|---|---|---|
| 触发时机 | 执行中事件驱动 | 执行**前**一次性 | L3 触发 (decision=refine) |
| Critic | 当前 scene + 历史 N step | PointWorld + VLA 双 critic | PointWorld（VLA 可选）|
| Iteration budget | N/A（单次决策）| ≤ 3 | ≤ 1 |
| 修改范围 | 任意决策（continue/refine/full_replan/abort）| 整个 plan 任意 stage | 仅 `refine_target_stages` |
| 单次开销 | 200–500ms | 7–12s × ≤3 iter | ~1–2s |

**升级链**：Pre-execution refinement < During-execution refinement < Full replan < Abort

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
14. **PointWorld 训练数据**：DROID 单臂 + Aloha 双臂 + sim 数据够吗？双臂 PointWorld 是否退回 Stage A 兜底直到数据充足？这影响 Stage C 在端锅 / 倒水类双臂任务上的可行性，是 P1 phase 的关键风险。
15. **Critique Synthesizer 的根因分析能力**：单纯 violation 报告 vs trajectory backtrace，质量差距多大？是否需要专门训练一个 RCA 模型，还是用 GPT-like LLM 做翻译就够？
16. **VLA confidence 校准**：现成 VLA（OpenVLA / π0）entropy 噪声大，是否值得为 critic 用途专门 fine-tune confidence head？或用 ensemble disagreement 做 uncertainty？
17. **Pre-execution refinement vs L2.5 重叠边界**：两者都可消费 PointWorld 预测——划分原则是"plan-level (refinement) vs step-level (L2.5)"，但 PointWorld preview query 究竟在哪一层评估更经济？
18. **Mode collapse 检测**：refinement loop 反复改 plan 让 VLA 高置信但 goal 不满足时，convergence_metrics 的 weighting（goal > process > VLA_conf）是否足够防御？需要 ablation 验证。
19. **PointWorld + VLA 数据共生失败模式**：如果两者训在同一数据集，会不会共享盲区？需要 ablation 用不同数据子集训各自模型，对比 catch rate。
20. **Mesh hash 校验机制**：Grounder 和 PointWorld 共享 URDF/mesh，部署时如何强制校验？哪一方负责 invalidate？
21. **VLM 学会消费 critique 的训练数据**：1k–5k 条 (task + critique → revised plan) pair 从哪来？sim 自动生成 vs 人工标注的成本/质量比？

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
  - 新增 Embodiment Grounder（解决 VLM 运动学盲区 + 双臂；§5.6 落地具体栈 cuRobo + WorkspaceMap + ArmAssigner + HandoverPlanner）
  - 新增 VLM-Supervisor 旁路（L3 战略层异常检测）
  - 新增 Temporal Predicates（handover 时序约束）
  - 拆开 Sequencing vs Synchronization 约束
  - 新增 Deferred References + Scene Blackboard（plan 层 closed-loop）
  - 新增 L2.5 Semantic Resolver（runtime VLM 持续参与，靠 cache/skip/fallback 不阻塞）
  - 新增 Binder 函数集合（项目第二窄腰）
  - **新增 Hybrid MPC A/B/C with PointWorld**（§7，lazy evaluation of expensive predictions；复活 v1 砍掉的 Predictive Shielding paper claim）
  - **新增 Pre-Execution Refinement Loop**（§11.6，VLM + PointWorld + VLA 三方互馈，≤ 3 iter 收敛）
  - **新增 Critique Synthesizer**（§11.6.8，根因分析翻译层，PointWorld violations → 结构化 critique）
  - **新增 During-Execution Refinement**（§11.6.5，supervisor decision=refine 触发，~1–2s 轻量版）

研究 claim 收紧：
  - P1: VLM-trained affordance region + LangSAM > zero-shot keypoint
  - P2 (完整版): **Hybrid MPC (A+B+C) + PointWorld + VLM-derived predicate cost** 在 contact-rich 任务（端锅 / 倒水 / 推堆叠物）上 > constraint projector only / PointWorld+task reward only / plain VLA
  - P3 (新): **三方互馈 refinement loop** 在 ≤ 3 iter 内收敛到满足 process + goal + VLA executability 的 plan
  - P4: 留作 future work（VLA + PointWorld mental sim, Dreamer-style）

L2.5 + Refinement 引入后的可证伪 claim：
  - 在散落 / 长尾任务上，L2.5 (VLM-primary binder) > rule-only binder
  - L2.5 的 cache + skip + fallback 让 VLM-in-loop 平均开销 < 300ms/step
  - Pre-Execution Refinement 减少 runtime cascading failure 率 > X%（vs 单向 pipeline baseline）
  - Mode-adaptive MPC (A/B/C) 在简单任务上延迟 ≈ Stage A only，在复杂任务上成功率 ≈ Stage C always-on
```

**最核心的设计纪律**：

> 五层 stack + 两个 gates（pre-execution refinement + per-step L2.5）+ 一条旁路 supervisor（L3 + during-execution refinement）；**四个** frequency band；**两份**冻结字典（predicate dict + binder set）；一份共享的 Scene Blackboard；一份共享的 URDF/mesh assets（Grounder 与 PointWorld 共用）。
>
> VLM 不知道身体；MPC 三档共存（不强制预测未来）；Supervisor 不修改动作；L2.5 不修改 plan 结构；Pre-Execution Refinement 不在执行中触发；VLA 不验证安全。
>
> 每个模块只做自己擅长的事；VLM 的 world knowledge 在 **plan 阶段（refinement）+ runtime（L2.5）+ critic 阶段（supervisor）** 三个时机经济地参与，而不是阻塞或缺席。**lazy evaluation of expensive predictions** 是贯穿 MPC 三档选档、L2.5 cache/skip/fallback、refinement budget 三处的统一设计哲学。
