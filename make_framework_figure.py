#!/usr/bin/env python3
"""Generate v2 framework architecture figure as SVG (paper main figure style)."""

W, H = 1600, 2480

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
    DARK='#212121'; GRAY='#666'; LIGHT='#999'

FONT = "'Noto Sans CJK SC','PingFang SC','Microsoft YaHei','Hiragino Sans GB','SimHei','WenQuanYi Zen Hei',sans-serif"

LEFT = 70
MAIN_W = W - 2 * LEFT
CENTER = W // 2

S = []  # SVG elements

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
S.append(t(CENTER, 50, 'VLM-VLA-MPC 机器人操作框架 (v2)', cls='ti'))
S.append(t(CENTER, 80, '五层 Stack + 两道 Gate + 一条旁路 · 两份冻结字典 (predicate dict + binder set) · Lazy evaluation of expensive predictions', cls='sub'))

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
    '• 顶层：refinement_recommendation (skip / pointworld_only / full)',
]
for i, line in enumerate(lines):
    S.append(t(LEFT + 30, y + 52 + i * 18, line, cls='bl', anc='start'))
S.append(lbl(LEFT + MAIN_W + 20, y + h//2, 'L0 (plan 阶段, 单次)', cls='ft', anc='start'))

S.append(arr(CENTER, y + h, CENTER, y + h + 35))
S.append(lbl(CENTER + 60, y + h + 22, 'plan v0', cls='lb', anc='start'))

# ======== Section 2: Pre-Execution Refinement Loop ========
y = 370
h = 500
S.append(rect(LEFT, y, MAIN_W, h, C.REF_F, C.REF_S, sw=2.5))
S.append(t(CENTER, y + 30, '执行前 Refinement Loop (§11.6) — VLM × PointWorld × VLA 三方互馈', cls='sh'))
S.append(t(CENTER, y + 53, 'N ≤ 3 iterations · ≤ 30s budget · 收敛判据 (process + goal + VLA conf) 严格 AND', cls='sub'))

# PointWorld + VLA critics
cy = y + 85
cw, ch = 540, 145
cx1 = LEFT + 80
cx2 = LEFT + MAIN_W - 80 - cw
# PointWorld
S.append(rect(cx1, cy, cw, ch, '#fff', C.REF_S, rx=8, sw=1.5, shadow=False))
S.append(t(cx1 + cw//2, cy + 26, 'PointWorld Critic (物理可行性)', cls='bh'))
pw_lines = [
    '• 全 plan H-step rollout → predicted trajectory',
    '• Process 违反：rollout 每步做 predicate.cost_on_pointcloud',
    '• Goal 满足度：rollout 终态 vs goal predicate',
    '• 输出 violation report + goal_satisfaction_prob',
    '• OOD 标记：高 chamfer 误差时降低 critic 置信',
]
for i, line in enumerate(pw_lines):
    S.append(t(cx1 + 20, cy + 50 + i * 18, line, cls='bl', anc='start'))
# VLA
S.append(rect(cx2, cy, cw, ch, '#fff', C.REF_S, rx=8, sw=1.5, shadow=False))
S.append(t(cx2 + cw//2, cy + 26, 'VLA Critic (执行可行性)', cls='bh'))
vla_lines = [
    '• Forward-pass only：仅前向推理，不执行',
    '• 每个 stage：action distribution entropy',
    '• 高 entropy → 训练分布外 / 低置信',
    '• Calibration：ensemble disagreement (可选)',
    '• 第一版 soft signal，不做 hard gating',
]
for i, line in enumerate(vla_lines):
    S.append(t(cx2 + 20, cy + 50 + i * 18, line, cls='bl', anc='start'))

# Arrows to Synthesizer
sy = cy + ch + 35
S.append(arr(cx1 + cw//2, cy + ch, CENTER - 200, sy, color=C.REF_S, sw=2))
S.append(arr(cx2 + cw//2, cy + ch, CENTER + 200, sy, color=C.REF_S, sw=2))

# Critique Synthesizer
syn_w = 900
syn_h = 75
sx = CENTER - syn_w // 2
S.append(rect(sx, sy, syn_w, syn_h, '#fff', C.REF_S, rx=8, sw=1.5, shadow=False))
S.append(t(sx + syn_w//2, sy + 28, 'Critique Synthesizer (§11.6.8) · 根因分析翻译层', cls='bh'))
S.append(t(sx + syn_w//2, sy + 52, '结构化 critique = [issue (stage_idx, predicate, severity, evidence)] + suggested_revision_dimension + convergence_metrics', cls='bl'))

# Arrow → converged
cony = sy + syn_h + 28
S.append(arr(CENTER, sy + syn_h, CENTER, cony, color=C.REF_S, sw=2))

# Converged box
con_w, con_h = 600, 65
cnx = CENTER - con_w // 2
S.append(rect(cnx, cony, con_w, con_h, '#fff', C.REF_S, rx=32, sw=1.5, shadow=False))
S.append(t(cnx + con_w//2, cony + 28, '收敛？(process 违反 ≤ θ_p AND goal ≥ θ_g AND VLA conf ≥ θ_v)', cls='bh'))
S.append(t(cnx + con_w//2, cony + 50, '或 budget 耗尽 (max_iters=3)', cls='bl'))

# Loop-back arrow
plan_box_left = LEFT
plan_box_bot = 215 + 120
loop_d = f'M {cnx + con_w} {cony + con_h//2} ' \
         f'L {LEFT + MAIN_W + 15} {cony + con_h//2} ' \
         f'L {LEFT + MAIN_W + 15} {plan_box_bot + 25} ' \
         f'L {LEFT + MAIN_W + 5} {plan_box_bot + 25}'
S.append(path_arr(loop_d, color=C.REF_S, sw=2, dashed=True, marker='ar_ref'))
S.append(lbl(LEFT + MAIN_W + 25, cony + con_h//2 - 8, 'no → VLM revise', cls='lb', anc='start'))
S.append(lbl(LEFT + MAIN_W + 25, cony + con_h//2 + 10, '(plan, critique)', cls='lb', anc='start'))

# Skip strategy annotation
S.append(t(LEFT + 90, y + h - 14, 'refinement_recommendation 跳过策略: skip (简单任务) · pointworld_only (中等) · full (高风险/双臂)', cls='ant', anc='start'))

# Exit arrow
S.append(arr(CENTER, cony + con_h, CENTER, y + h + 35, color=C.REF_S, sw=2.5))
S.append(lbl(CENTER + 60, cony + con_h + 25, 'yes / budget done → refined plan', cls='lb', anc='start'))

# ======== Section 3: Embodiment Grounder ========
y = y + h + 50  # = 920
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

S.append(lbl(LEFT + MAIN_W + 20, y + h//2, 'L0 (plan 阶段)', cls='ft', anc='start'))
S.append(arr(CENTER, y + h, CENTER, y + h + 35))
S.append(lbl(CENTER + 60, y + h + 22, 'embodiment-grounded plan (?refs 未解析)', cls='lb', anc='start'))

# ======== Section 4: L2.5 Semantic Resolution ========
y = y + h + 50  # = 920 + 170 + 50 = 1140
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
        '• 所有模块共享, 单一 source of truth',
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

# ======== Section 5: Inner Loop ========
y = y + h + 50  # 1140 + 220 + 50 = 1410
h = 540
S.append(rect(LEFT, y, MAIN_W, h, C.LOOP_F, C.LOOP_S))
S.append(t(CENTER, y + 30, 'Inner Loop (L1 反应 + L2 战术, §7) — 10–30 Hz (Stage C 时降至 2–5 Hz)', cls='sh'))

# Perception → VLA → MPC chain
chain_y = y + 65
# Perception
percp_x = LEFT + 30
percp_w = 220
percp_h = 50
S.append(rect(percp_x, chain_y, percp_w, percp_h, '#fff', C.LOOP_S, rx=6, sw=1.5, shadow=False))
S.append(t(percp_x + percp_w//2, chain_y + 22, 'Perception', cls='bh'))
S.append(t(percp_x + percp_w//2, chain_y + 40, 'obs_t (RGB-D) → point_cloud_t', cls='bs'))
# Arrow → VLA
vla_x = percp_x + percp_w + 30
vla_w = 230
S.append(arr(percp_x + percp_w, chain_y + percp_h//2, vla_x, chain_y + percp_h//2))
# VLA
S.append(rect(vla_x, chain_y, vla_w, percp_h, '#fff', C.LOOP_S, rx=6, sw=1.5, shadow=False))
S.append(t(vla_x + vla_w//2, chain_y + 22, 'VLA (动作执行器)', cls='bh'))
S.append(t(vla_x + vla_w//2, chain_y + 40, 'point_cloud + plan → a_t', cls='bs'))
# Arrow → MPC Selector
S.append(arr(vla_x + vla_w, chain_y + percp_h//2, vla_x + vla_w + 30, chain_y + percp_h//2))
S.append(lbl(vla_x + vla_w + 18, chain_y + percp_h//2 - 10, 'a_t', cls='lb'))

# MPC Selector big box
mpc_x = vla_x + vla_w + 40
mpc_w = LEFT + MAIN_W - 30 - mpc_x
mpc_y = chain_y - 5
mpc_h = 240
S.append(rect(mpc_x, mpc_y, mpc_w, mpc_h, '#fff', C.LOOP_S, rx=8, sw=2, shadow=False))
S.append(t(mpc_x + mpc_w//2, mpc_y + 24, 'MPC Selector (§7) · 按 stage 的 mpc_mode 选档', cls='bh'))

# Three stages
stages = [
    ('Stage A', '约束投影 (默认)', 'kinematic_forward\nFK + rigid attach\n确定性, 无学习', '&lt; 5 ms', C.MPC_A, C.MPC_AS),
    ('Stage B', 'PointWorld 单步', '接触瞬间 / 关键事件\npc_t → pc_{t+1}\nsingle-step pred', '30–80 ms', C.MPC_B, C.MPC_BS),
    ('Stage C', 'PointWorld CEM/MPPI', 'contact-rich / 双臂耦合\nH-step rollout × K 候选\n累计 predicate cost', '200–500 ms', C.MPC_C, C.MPC_CS),
]
stg_w = (mpc_w - 50) // 3
for i, (sn, st, body, lat, sf, ss) in enumerate(stages):
    sx = mpc_x + 15 + i * (stg_w + 5)
    sy_ = mpc_y + 50
    sh = mpc_h - 65
    S.append(rect(sx, sy_, stg_w, sh, sf, ss, rx=6, sw=2, shadow=False))
    S.append(t(sx + stg_w//2, sy_ + 22, sn, cls='bh'))
    S.append(t(sx + stg_w//2, sy_ + 40, st, cls='bl'))
    for j, line in enumerate(body.split('\n')):
        S.append(t(sx + stg_w//2, sy_ + 62 + j * 16, line, cls='bs'))
    # Latency tag
    S.append(t(sx + stg_w//2, sy_ + sh - 14, lat, cls='lat'))

# Down from MPC: a_t*
out_y = mpc_y + mpc_h + 30
S.append(arr(mpc_x + mpc_w//2, mpc_y + mpc_h, mpc_x + mpc_w//2, out_y, sw=2.5))
S.append(lbl(mpc_x + mpc_w//2 + 20, mpc_y + mpc_h + 18, 'a_t*', cls='lb', anc='start'))

# Stage A sanity check
sany_x = LEFT + 60
sany_w = MAIN_W - 120
sany_h = 50
S.append(rect(sany_x, out_y, sany_w, sany_h, '#FFF9C4', C.MPC_AS, rx=6, sw=1.5, shadow=False))
S.append(t(sany_x + sany_w//2, out_y + 32, 'Stage A sanity check (always on · 兜底) · 几何 collision + IK + workspace 再过一遍', cls='bh'))

# Down to execute
exec_y = out_y + sany_h + 25
S.append(arr(sany_x + sany_w//2, out_y + sany_h, sany_x + sany_w//2, exec_y))

# robot.execute
exec_w, exec_h = 500, 50
exec_x = CENTER - exec_w // 2
S.append(rect(exec_x, exec_y, exec_w, exec_h, C.INP_F, C.INP_S, rx=25, sw=1.5, shadow=False))
S.append(t(exec_x + exec_w//2, exec_y + 31, 'robot.execute(a_t*)', cls='bh'))

# PointWorld Diagnostic on the left side
diag_x = LEFT + 30
diag_y = exec_y - 90
diag_w = 290
diag_h = 110
S.append(rect(diag_x, diag_y, diag_w, diag_h, C.SUP_F, C.SUP_S, rx=6, sw=1.5, shadow=False))
S.append(t(diag_x + diag_w//2, diag_y + 22, 'PointWorld Diagnostic', cls='bh'))
diag_lines = [
    '• 每 N step 比对：',
    '  predicted_pc vs observed_pc',
    '• chamfer 误差 > θ → ',
    '  通知 Supervisor 降档',
    '• OOD 自动 fallback Stage A',
]
for i, line in enumerate(diag_lines):
    S.append(t(diag_x + 15, diag_y + 42 + i * 14, line, cls='bs', anc='start'))

S.append(lbl(LEFT + MAIN_W + 20, y + h//2, 'L1 + L2\n10–30 Hz', cls='ft', anc='start'))

# Down out of Inner Loop
S.append(arr(CENTER, y + h, CENTER, y + h + 40, sw=2.5))
S.append(lbl(CENTER + 50, y + h + 25, 'stage complete / anomaly / PointWorld drift', cls='lb', anc='start'))

# ======== Section 6: Supervisor + During-Execution Refinement ========
y = y + h + 60  # 1410 + 540 + 60 = 2010
h = 200
S.append(rect(LEFT, y, MAIN_W, h, C.SUP_F, C.SUP_S, sw=2.5))
S.append(t(CENTER, y + 30, 'VLM-Supervisor (L3, §8) + During-Execution Refinement (§11.6.5) · 旁路 · 事件驱动', cls='sh'))
S.append(t(CENTER, y + 53, '权限战略层: 不修改单步动作, 不解析单个 binding · 只改 plan 结构或触发 refinement', cls='sub'))

# 6 decision options
dec_items = [
    ('continue', '继续当前 stage'),
    ('advance_stage', '推进下一 stage'),
    ('downgrade_mpc_mode', '降档 MPC\n(PointWorld 不可靠)'),
    ('refine', 'During-Exec Refinement\n(≤1 iter, ~1–2s)'),
    ('full_replan', '回 VLM-Planner\n重生成 (带 failure ctx)'),
    ('abort', '终止任务\n(不可逆失败)'),
]
opt_w = (MAIN_W - 80 - 30) // 3
opt_h = 50
for i, (dec, desc) in enumerate(dec_items):
    row = i // 3
    col = i % 3
    sx = LEFT + 40 + col * (opt_w + 15)
    sy_ = y + 80 + row * (opt_h + 8)
    S.append(rect(sx, sy_, opt_w, opt_h, '#fff', C.SUP_S, rx=5, sw=1.5, shadow=False))
    S.append(t(sx + opt_w//2, sy_ + 18, dec, cls='bh'))
    for j, line in enumerate(desc.split('\n')):
        S.append(t(sx + opt_w//2, sy_ + 35 + j * 13, line, cls='bs'))

S.append(lbl(LEFT + MAIN_W + 20, y + h//2, 'L3\n事件驱动\n0.2–1 Hz', cls='ft', anc='start'))

# Feedback path from Supervisor up to top (refine/replan)
fb_d = f'M {LEFT + MAIN_W - 30} {y} ' \
       f'L {LEFT + MAIN_W + 50} {y} ' \
       f'L {LEFT + MAIN_W + 50} 240 ' \
       f'L {LEFT + MAIN_W + 5} 240'
S.append(path_arr(fb_d, color=C.SUP_S, sw=2, dashed=True, marker='ar_sup'))
S.append(lbl(LEFT + MAIN_W + 60, (y + 240) // 2, 'refine / full_replan', cls='lb', anc='start'))
S.append(lbl(LEFT + MAIN_W + 60, (y + 240) // 2 + 18, '反馈到上游', cls='lb', anc='start'))

# ======== Bottom annotation ========
y = y + h + 30
S.append(rect(LEFT, y, MAIN_W, 70, '#FAFAFA', C.GRAY, sw=1, rx=8, shadow=False))
S.append(t(CENTER, y + 25, '设计纪律 · Five Disciplines', cls='bh'))
S.append(t(CENTER, y + 48, 'D1 Constraint contract not action script · D2 Outcome-based supervision · D3 VLM embodiment-agnostic · D4 Predicate dict 窄腰 · D5 频率分层 (L1 反应 / L2 战术 / L2.5 语义 / L3 战略)', cls='ant'))

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
