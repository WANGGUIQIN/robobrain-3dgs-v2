#!/usr/bin/env python3
"""Generate v2 framework architecture figure as SVG (paper main figure style).

v2-streaming: replaces Pre-Execution Refinement Loop with Quick Check + Streaming Refiner
parallel to Inner Loop. Startup latency ~1-2s instead of ~30s.
"""

W, H = 1800, 2100

class C:
    PLAN_F='#E3F2FD'; PLAN_S='#1565C0'
    REF_F='#F3E5F5'; REF_S='#6A1B9A'
    EMB_F='#E8F5E9'; EMB_S='#2E7D32'
    L25_F='#FFF3E0'; L25_S='#E65100'
    LOOP_F='#FFFDE7'; LOOP_S='#F9A825'
    SUP_F='#FFEBEE'; SUP_S='#B71C1C'
    MPC_A='#FFF59D'; MPC_AS='#F9A825'
    MPC_B='#FFCC80'; MPC_BS='#EF6C00'
    MPC_C='#FFAB91'; MPC_CS='#D84315'
    INP_F='#ECEFF1'; INP_S='#37474F'
    QC_F='#FFF8E1'; QC_S='#FF8F00'
    DARK='#212121'; GRAY='#666'; LIGHT='#999'

FONT = "'Noto Sans CJK SC','PingFang SC','Microsoft YaHei','Hiragino Sans GB','SimHei','WenQuanYi Zen Hei',sans-serif"

LEFT = 70
MAIN_W = W - 2 * LEFT
CENTER = W // 2

S = []

def rect(x, y, w, h, fill, stroke, rx=10, sw=2, shadow=True, opacity=1):
    f = ' filter="url(#sh)"' if shadow else ''
    op = f' opacity="{opacity}"' if opacity < 1 else ''
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{f}{op}/>'

def t(x, y, text, cls='bt', anc='middle'):
    return f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anc}">{text}</text>'

def arr(x1, y1, x2, y2, color='#333', sw=2.2, dashed=False, marker='ar'):
    da = ' stroke-dasharray="6 4"' if dashed else ''
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}" marker-end="url(#{marker})"{da}/>'

def path_arr(d, color='#333', sw=2.2, dashed=False, marker='ar'):
    da = ' stroke-dasharray="6 4"' if dashed else ''
    return f'<path d="{d}" stroke="{color}" stroke-width="{sw}" fill="none" marker-end="url(#{marker})"{da}/>'

def lbl(x, y, text, cls='lb', anc='middle'):
    return f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anc}">{text}</text>'

# ======== Title ========
S.append(t(CENTER, 50, 'VLM-VLA-MPC 机器人操作框架 (v2 · streaming refinement)', cls='ti'))
S.append(t(CENTER, 80, '执行与精化并行 · 启动延迟 ≤ 2s · Quick Check + Streaming Refiner + Stage A 兜底 · Lazy evaluation of expensive predictions', cls='sub'))

# ======== User Instruction ========
y = 115
iw, ih = 280, 50
S.append(rect(CENTER - iw//2, y, iw, ih, C.INP_F, C.INP_S, rx=25))
S.append(t(CENTER, y + 31, '用户指令 (自然语言任务描述)', cls='bh'))
S.append(arr(CENTER, y + ih, CENTER, y + ih + 35))

# ======== Section 1: VLM-Planner ========
y = 215
h = 120
S.append(rect(LEFT, y, MAIN_W, h, C.PLAN_F, C.PLAN_S))
S.append(t(CENTER, y + 28, 'VLM-Planner (RoboBrain LoRA · embodiment-agnostic · §4)', cls='sh'))
lines = [
    '• 输出 plan v0：&lt;think&gt;推理 + Goal predicate + Scene 描述',
    '• 每个 stage：?deferred refs + binders + constraints (来自 predicate dictionary)',
    '• MPC 选档：mpc_mode hint (A/B/C) + pointworld_focus_objects',
    '• 顶层：lookahead (0/1/2/3) — 控制 Streaming Refiner 提前精化的 stage 数',
]
for i, line in enumerate(lines):
    S.append(t(LEFT + 30, y + 52 + i * 18, line, cls='bl', anc='start'))
S.append(lbl(LEFT + MAIN_W + 20, y + h//2, 'L0 plan 阶段\n单次', cls='ft', anc='start'))

S.append(arr(CENTER, y + h, CENTER, y + h + 35))
S.append(lbl(CENTER + 60, y + h + 22, 'plan v0', cls='lb', anc='start'))

# ======== Section 2: Quick Pre-Execution Check (small, ~1-2s) ========
y = 370
h = 110
S.append(rect(LEFT, y, MAIN_W, h, C.QC_F, C.QC_S, sw=2))
S.append(t(CENTER, y + 28, 'Quick Pre-Execution Check (§11.6.1) · 启动延迟 ≤ 2s', cls='sh'))
S.append(t(CENTER, y + 51, '只检查 stage 1 + plan 中 mpc_mode=C 的 high-risk stage · PointWorld 单步预测确认无 catastrophic violation', cls='sub'))
qc_lines = [
    '• 跳过远端 stage 评估 (PointWorld 误差随 horizon 累积，远端预测不可信)',
    '• 通过 → 立即开始执行；不通过 → 单轮 VLM revise stage 1 后再开 (~3s 总延迟)',
]
for i, line in enumerate(qc_lines):
    S.append(t(LEFT + 30, y + 76 + i * 17, line, cls='bl', anc='start'))
S.append(lbl(LEFT + MAIN_W + 20, y + h//2, '~1–2s\n单次', cls='ft', anc='start'))

S.append(arr(CENTER, y + h, CENTER, y + h + 30))

# ======== Section 3: Embodiment Grounder ========
y = 510
h = 170
S.append(rect(LEFT, y, MAIN_W, h, C.EMB_F, C.EMB_S))
S.append(t(CENTER, y + 30, 'Embodiment Grounder (§5.6) — 经典 robotics, 无 learning', cls='sh'))
S.append(t(CENTER, y + 53, '把 embodiment-agnostic plan 翻译成 embodiment-grounded plan: arm assignment + handover + co-manipulation 检测', cls='sub'))

items = [
    ('cuRobo IK', 'GPU batched IK\n+ SDF collision\n1–5 ms'),
    ('WorkspaceMap', '离线预计算\nvoxel 可达性\n~1μs lookup'),
    ('ArmAssigner', '启发式打分\n(manip/dist/idle)\n+ L2.5 fallback'),
    ('HandoverPlanner', '模板化 sub-plan\n时序约束注入\nbefore/simultaneous'),
    ('CoManip Detector', 'contact_spec 规则\n触发双臂耦合\n约束模式'),
]
iw = (MAIN_W - 60 - 40) // 5
for i, (ti2, body) in enumerate(items):
    ix = LEFT + 30 + i * (iw + 10)
    iy = y + 75
    ih2 = 85
    S.append(rect(ix, iy, iw, ih2, '#fff', C.EMB_S, rx=6, sw=1.5, shadow=False))
    S.append(t(ix + iw//2, iy + 22, ti2, cls='bh'))
    for j, line in enumerate(body.split('\n')):
        S.append(t(ix + iw//2, iy + 42 + j*15, line, cls='bs'))

S.append(lbl(LEFT + MAIN_W + 20, y + h//2, 'L0 plan 阶段', cls='ft', anc='start'))
S.append(arr(CENTER, y + h, CENTER, y + h + 35))
S.append(lbl(CENTER + 60, y + h + 22, 'embodiment-grounded plan (?refs 未解析)', cls='lb', anc='start'))

# ======== Section 4: L2.5 Semantic Resolution ========
y = 720
h = 220
S.append(rect(LEFT, y, MAIN_W, h, C.L25_F, C.L25_S))
S.append(t(CENTER, y + 30, 'L2.5 语义解析层 (§11.5) — 每个 step 入口/退出', cls='sh'))
S.append(t(CENTER, y + 53, 'VLM 在 runtime 持续贡献 world knowledge，但靠 cache/skip/fallback 不阻塞 main loop', cls='sub'))

sub_items = [
    ('VLM-Binder + VLM-Refiner', [
        '• vlm_semantic_query 解析 ?refs',
        '• runtime_constraint_query 加约束',
        '• affordance_refinement_query',
        '• PointWorld preview query (可选)',
    ]),
    ('Scene Blackboard', [
        '• 唯一权威 binding 表',
        '• object states (perception 维护)',
        '• execution history',
        '• 所有模块共享, single source of truth',
    ]),
    ('Affordance Grounding', [
        '• LangSAM (text → mask)',
        '• depth lift (mask → 3D point)',
        '• 简化: 删除 v1 八级 filter',
        '• RGB-D 数据原生支持',
    ]),
]
sw_ = (MAIN_W - 60 - 40) // 3
for i, (ti2, lines) in enumerate(sub_items):
    sx = LEFT + 30 + i * (sw_ + 20)
    sy_ = y + 75
    sh = 120
    S.append(rect(sx, sy_, sw_, sh, '#fff', C.L25_S, rx=6, sw=1.5, shadow=False))
    S.append(t(sx + sw_//2, sy_ + 22, ti2, cls='bh'))
    for j, line in enumerate(lines):
        S.append(t(sx + 15, sy_ + 45 + j * 16, line, cls='bl', anc='start'))

S.append(t(CENTER, y + h - 14, 'L2.5 Controller: cache (query_hash, scene_hash) + budget ~500ms/step + skip_if_scene_unchanged + fallback rule', cls='ant'))
S.append(lbl(LEFT + MAIN_W + 20, y + h//2, 'L2.5\n0.5–2 Hz', cls='ft', anc='start'))

S.append(arr(CENTER, y + h, CENTER, y + h + 35))
S.append(lbl(CENTER + 60, y + h + 22, 'resolved step (concrete targets + constraints)', cls='lb', anc='start'))

# ======== Section 5: Two-column INNER LOOP || STREAMING REFINER ========
y = 990
h = 580
# Two columns:
# Left: Inner Loop (width ~960)
# Right: Streaming Refiner (width ~640)
GAP = 20
LOOP_W = 1000
REF_W = MAIN_W - LOOP_W - GAP  # 1660 - 1000 - 20 = 640

# --- Inner Loop (left column) ---
loop_x = LEFT
S.append(rect(loop_x, y, LOOP_W, h, C.LOOP_F, C.LOOP_S))
S.append(t(loop_x + LOOP_W//2, y + 30, 'Inner Loop (L1 反应 + L2 战术 · §7) · 10–30 Hz', cls='sh'))
S.append(t(loop_x + LOOP_W//2, y + 53, '执行主路径 · Stage A always-on 作为单步安全兜底', cls='sub'))

# Perception → VLA chain (vertical inside)
cy = y + 80
percp_w = 380
S.append(rect(loop_x + LOOP_W//2 - percp_w//2, cy, percp_w, 50, '#fff', C.LOOP_S, rx=6, sw=1.5, shadow=False))
S.append(t(loop_x + LOOP_W//2, cy + 22, 'Perception', cls='bh'))
S.append(t(loop_x + LOOP_W//2, cy + 40, 'obs_t (RGB-D) → point_cloud_t', cls='bs'))

# Arrow ↓
S.append(arr(loop_x + LOOP_W//2, cy + 50, loop_x + LOOP_W//2, cy + 75))
S.append(lbl(loop_x + LOOP_W//2 + 60, cy + 65, 'pc_t', cls='lb', anc='start'))

# VLA
S.append(rect(loop_x + LOOP_W//2 - percp_w//2, cy + 75, percp_w, 50, '#fff', C.LOOP_S, rx=6, sw=1.5, shadow=False))
S.append(t(loop_x + LOOP_W//2, cy + 97, 'VLA (动作执行器)', cls='bh'))
S.append(t(loop_x + LOOP_W//2, cy + 115, 'pc + plan + kpts → a_t', cls='bs'))

# Arrow ↓
S.append(arr(loop_x + LOOP_W//2, cy + 125, loop_x + LOOP_W//2, cy + 155))
S.append(lbl(loop_x + LOOP_W//2 + 60, cy + 145, 'a_t', cls='lb', anc='start'))

# MPC Selector
mpc_y = cy + 155
mpc_h = 200
S.append(rect(loop_x + 30, mpc_y, LOOP_W - 60, mpc_h, '#fff', C.LOOP_S, rx=8, sw=2, shadow=False))
S.append(t(loop_x + LOOP_W//2, mpc_y + 24, 'MPC Selector (§7) · 按 stage 的 mpc_mode 选档', cls='bh'))

stages = [
    ('Stage A', '约束投影', '(默认)', 'FK + rigid attach\n确定性', '&lt; 5 ms', C.MPC_A, C.MPC_AS),
    ('Stage B', 'PointWorld 单步', '(接触)', 'pc_t → pc_{t+1}\nsingle-step pred', '30–80 ms', C.MPC_B, C.MPC_BS),
    ('Stage C', 'PW CEM/MPPI', '(contact-rich)', 'H-step × K rollout\n累计 cost', '200–500 ms', C.MPC_C, C.MPC_CS),
]
stg_w = (LOOP_W - 80) // 3
for i, (sn, st, sw_t, body, lat, sf, ss) in enumerate(stages):
    sx = loop_x + 40 + i * (stg_w + 5)
    sy_ = mpc_y + 50
    sh_t = mpc_h - 65
    S.append(rect(sx, sy_, stg_w, sh_t, sf, ss, rx=6, sw=2, shadow=False))
    S.append(t(sx + stg_w//2, sy_ + 22, sn, cls='bh'))
    S.append(t(sx + stg_w//2, sy_ + 40, st, cls='bl'))
    S.append(t(sx + stg_w//2, sy_ + 56, sw_t, cls='bs'))
    for j, line in enumerate(body.split('\n')):
        S.append(t(sx + stg_w//2, sy_ + 78 + j * 16, line, cls='bs'))
    S.append(t(sx + stg_w//2, sy_ + sh_t - 14, lat, cls='lat'))

# Down: a_t*
post_y = mpc_y + mpc_h + 25
S.append(arr(loop_x + LOOP_W//2, mpc_y + mpc_h, loop_x + LOOP_W//2, post_y, sw=2.5))
S.append(lbl(loop_x + LOOP_W//2 + 20, mpc_y + mpc_h + 15, 'a_t*', cls='lb', anc='start'))

# Stage A sanity
sany_w = LOOP_W - 100
sany_h = 38
S.append(rect(loop_x + 50, post_y, sany_w, sany_h, '#FFF9C4', C.MPC_AS, rx=6, sw=1.5, shadow=False))
S.append(t(loop_x + LOOP_W//2, post_y + 25, 'Stage A sanity check (always on · 几何/IK/collision 兜底)', cls='bh'))

# Down arrow
exec_y = post_y + sany_h + 18
S.append(arr(loop_x + LOOP_W//2, post_y + sany_h, loop_x + LOOP_W//2, exec_y, sw=2.5))

# robot.execute
exec_w, exec_h = 400, 40
S.append(rect(loop_x + LOOP_W//2 - exec_w//2, exec_y, exec_w, exec_h, C.INP_F, C.INP_S, rx=20, sw=1.5, shadow=False))
S.append(t(loop_x + LOOP_W//2, exec_y + 26, 'robot.execute(a_t*)', cls='bh'))

S.append(lbl(loop_x + 30, y + h - 14, 'L1 + L2 · 10–30 Hz', cls='ft', anc='start'))

# --- Streaming Refiner (right column) ---
ref_x = LEFT + LOOP_W + GAP
S.append(rect(ref_x, y, REF_W, h, C.REF_F, C.REF_S, sw=2.5))
S.append(t(ref_x + REF_W//2, y + 30, 'Streaming Refiner (§11.6)', cls='sh'))
S.append(t(ref_x + REF_W//2, y + 53, '与执行并行 · 后台维护 lookahead 窗口', cls='sub'))

# 流程说明区
refbox_y = y + 80
refbox_h = 230
S.append(rect(ref_x + 20, refbox_y, REF_W - 40, refbox_h, '#fff', C.REF_S, rx=8, sw=1.5, shadow=False))
S.append(t(ref_x + REF_W//2, refbox_y + 25, '对未来 lookahead 个 stage：', cls='bh'))
ref_steps = [
    '① 从 Scene Blackboard 读当前状态',
    '② PointWorld H-step rollout (本 stage)',
    '③ VLA forward-pass 评 confidence',
    '④ Critique Synthesizer 根因分析',
    '⑤ 如违反 → VLM revise 这一 stage',
    '⑥ 写回 plan + blackboard，标记 refined',
]
for i, line in enumerate(ref_steps):
    S.append(t(ref_x + 40, refbox_y + 55 + i * 24, line, cls='bl', anc='start'))

# 单 stage 精化成本
S.append(t(ref_x + REF_W//2, refbox_y + refbox_h - 18, '单 stage 精化 ~2–3s · Stage 平均执行 2–10s', cls='ant'))

# Lookahead 设定
la_y = refbox_y + refbox_h + 15
la_h = 60
S.append(rect(ref_x + 20, la_y, REF_W - 40, la_h, '#FFF8E1', C.REF_S, rx=6, sw=1.5, shadow=False))
S.append(t(ref_x + REF_W//2, la_y + 22, 'Lookahead window (默认 = mpc_mode):', cls='bh'))
S.append(t(ref_x + REF_W//2, la_y + 42, 'Stage A → lookahead=0   Stage B → 1   Stage C → 2', cls='bl'))

# Fallback when can't keep up
fb_y = la_y + la_h + 15
fb_h = 80
S.append(rect(ref_x + 20, fb_y, REF_W - 40, fb_h, '#FFEBEE', C.SUP_S, rx=6, sw=1.5, shadow=False))
S.append(t(ref_x + REF_W//2, fb_y + 22, '精化跟不上 → Fallback:', cls='bh'))
S.append(t(ref_x + 40, fb_y + 42, '• Stage A only 执行未精化 stage', cls='bl', anc='start'))
S.append(t(ref_x + 40, fb_y + 60, '• 标记 degraded mode, 通知 L3 supervisor', cls='bl', anc='start'))

# Arrows showing parallel coupling between Inner Loop and Refiner
# Bidirectional: Refiner reads blackboard, writes refined plan
# Draw 3 arrows between the boxes

# Refiner reads from blackboard (left ← right direction)
ar_y1 = y + 100
S.append(path_arr(f'M {ref_x} {ar_y1} L {ref_x - GAP + 5} {ar_y1}', color=C.REF_S, sw=2, dashed=True, marker='ar_ref'))
S.append(lbl((loop_x + LOOP_W + ref_x) // 2, ar_y1 - 6, '读 state', cls='lb'))

# Refiner writes refined plan back (left → right? no, right → left direction)
ar_y2 = y + 250
S.append(path_arr(f'M {ref_x} {ar_y2} L {loop_x + LOOP_W - 5} {ar_y2}', color=C.REF_S, sw=2, dashed=True, marker='ar_ref'))
S.append(lbl((loop_x + LOOP_W + ref_x) // 2, ar_y2 - 6, '写 refined\nstage k+1', cls='lb'))

S.append(lbl(ref_x + REF_W - 20, y + h - 14, '与 Inner Loop 并行', cls='ft', anc='end'))

# Inner Loop bottom-right: PointWorld Diagnostic small
diag_x = loop_x + LOOP_W - 280 - 20
diag_y = exec_y + exec_h + 8
diag_w = 280
diag_h = 60
S.append(rect(diag_x, diag_y, diag_w, diag_h, C.SUP_F, C.SUP_S, rx=6, sw=1.5, shadow=False))
S.append(t(diag_x + diag_w//2, diag_y + 20, 'PointWorld Diagnostic', cls='bh'))
S.append(t(diag_x + diag_w//2, diag_y + 38, '每 N step 比对 predicted vs observed', cls='bs'))
S.append(t(diag_x + diag_w//2, diag_y + 52, 'chamfer > θ → 通知 Supervisor 降档', cls='bs'))

# Down out of Inner Loop area
S.append(arr(loop_x + LOOP_W//2, y + h, loop_x + LOOP_W//2, y + h + 40, sw=2.5))
S.append(lbl(loop_x + LOOP_W//2 + 50, y + h + 25, 'stage 完成 / 异常 / drift', cls='lb', anc='start'))

# ======== Section 6: L3 Supervisor ========
y = 1610
h = 210
S.append(rect(LEFT, y, MAIN_W, h, C.SUP_F, C.SUP_S, sw=2.5))
S.append(t(CENTER, y + 30, 'VLM-Supervisor (L3, §8) · 旁路 · 事件驱动', cls='sh'))
S.append(t(CENTER, y + 53, '战略层异常检测 · 不修改单步动作 · 不解析单个 binding · 只改 plan 结构或终止任务', cls='sub'))

dec_items = [
    ('continue', '继续当前 stage'),
    ('advance_stage', '推进下一 stage'),
    ('downgrade_mpc_mode', 'MPC 降档\n(PointWorld 不可靠)'),
    ('force_refine_now', '强制 Streaming Refiner\n立即处理某 stage'),
    ('full_replan', '回 VLM-Planner\n重生成 (带 failure ctx)'),
    ('abort', '终止任务\n(不可逆失败)'),
]
opt_w = (MAIN_W - 100 - 50) // 3
opt_h = 56
for i, (dec, desc) in enumerate(dec_items):
    row = i // 3
    col = i % 3
    sx = LEFT + 50 + col * (opt_w + 25)
    sy_ = y + 80 + row * (opt_h + 8)
    S.append(rect(sx, sy_, opt_w, opt_h, '#fff', C.SUP_S, rx=5, sw=1.5, shadow=False))
    S.append(t(sx + opt_w//2, sy_ + 22, dec, cls='bh'))
    for j, line in enumerate(desc.split('\n')):
        S.append(t(sx + opt_w//2, sy_ + 40 + j * 13, line, cls='bs'))

S.append(lbl(LEFT + MAIN_W + 20, y + h//2, 'L3\n事件驱动\n0.2–1 Hz', cls='ft', anc='start'))

# Feedback path from Supervisor to upper plan layers (curved)
fb_d = f'M {LEFT + MAIN_W - 30} {y} ' \
       f'L {LEFT + MAIN_W + 50} {y} ' \
       f'L {LEFT + MAIN_W + 50} 240 ' \
       f'L {LEFT + MAIN_W + 5} 240'
S.append(path_arr(fb_d, color=C.SUP_S, sw=2, dashed=True, marker='ar_sup'))
S.append(lbl(LEFT + MAIN_W + 60, (y + 240) // 2, 'full_replan / force_refine', cls='lb', anc='start'))
S.append(lbl(LEFT + MAIN_W + 60, (y + 240) // 2 + 18, '反馈到上游', cls='lb', anc='start'))

# ======== Bottom annotation ========
y = y + h + 25
S.append(rect(LEFT, y, MAIN_W, 80, '#FAFAFA', C.GRAY, sw=1, rx=8, shadow=False))
S.append(t(CENTER, y + 25, '设计纪律 · Five Disciplines + Streaming Refinement 原则', cls='bh'))
S.append(t(CENTER, y + 48, 'D1 Constraint contract not action script · D2 Outcome-based supervision · D3 VLM embodiment-agnostic · D4 Predicate dict 窄腰 · D5 频率分层', cls='ant'))
S.append(t(CENTER, y + 68, '+ 精化与执行并行 · Stage A 始终兜底 · 永不阻塞 main loop · 永不依赖 PointWorld 远期预测', cls='ant'))

# ======== Assemble ========
styles = f'''<style>
text {{ font-family: {FONT}; fill: {C.DARK}; }}
.ti {{ font-size: 30px; font-weight: bold; }}
.sub {{ font-size: 14px; fill: {C.GRAY}; }}
.sh {{ font-size: 18px; font-weight: bold; }}
.bh {{ font-size: 14px; font-weight: bold; }}
.bt {{ font-size: 13px; }}
.bl {{ font-size: 12px; }}
.bs {{ font-size: 11px; fill: {C.GRAY}; }}
.ant {{ font-size: 12px; fill: {C.GRAY}; font-style: italic; }}
.ft {{ font-size: 12px; fill: {C.GRAY}; }}
.lb {{ font-size: 12px; fill: {C.GRAY}; }}
.lat {{ font-size: 11px; font-weight: bold; fill: {C.DARK}; }}
</style>'''

defs = f'''<defs>
<marker id="ar" markerWidth="12" markerHeight="12" refX="11" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,8 L11,4 z" fill="#333"/></marker>
<marker id="ar_ref" markerWidth="12" markerHeight="12" refX="11" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,8 L11,4 z" fill="{C.REF_S}"/></marker>
<marker id="ar_sup" markerWidth="12" markerHeight="12" refX="11" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,8 L11,4 z" fill="{C.SUP_S}"/></marker>
<filter id="sh" x="-5%" y="-5%" width="115%" height="115%"><feDropShadow dx="2" dy="3" stdDeviation="2.5" flood-opacity="0.18"/></filter>
</defs>'''

svg = f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">\n{styles}\n{defs}\n<rect x="0" y="0" width="{W}" height="{H}" fill="#FFFFFF"/>\n'
svg += '\n'.join(S)
svg += '\n</svg>\n'

with open('framework_v2_main_figure.svg', 'w', encoding='utf-8') as f:
    f.write(svg)

print(f"Wrote framework_v2_main_figure.svg: {W}x{H}, {len(S)} elements")
