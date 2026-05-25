#!/usr/bin/env node
/**
 * VLM-VLA-MPC Robot Manipulation Framework v2 — PPT generator
 * Generates: framework_v2_deck.pptx
 */

const pptxgen = require("pptxgenjs");
const pres = new pptxgen();

pres.layout = "LAYOUT_WIDE";  // 13.3 x 7.5
pres.author = "RoboBrain Framework v2";
pres.title = "VLM-VLA-MPC Robot Manipulation Framework v2";

// ============ palette ============
const C = {
  navy:    "1E2761",
  navyDk:  "12183D",
  ice:     "CADCFC",
  iceDk:   "9FB6E8",
  cyan:    "60D2FF",
  white:   "FFFFFF",
  charcoal:"36454F",
  coral:   "F96167",
  amber:   "FFB740",
  green:   "5BC487",
  purple:  "9B7EDE",
  gray:    "8E9AAF",
  grayLt:  "E5E8F0",
  codeBg:  "1A1F3A",
  codeFg:  "E0E6F0",
};

const FONT_H = "Cambria";
const FONT_B = "Calibri";
const FONT_M = "Consolas";

const W = 13.3, H = 7.5;

// ============ helpers ============
function addTitleBar(slide, title, kicker) {
  // top kicker
  if (kicker) {
    slide.addText(kicker, {
      x: 0.5, y: 0.3, w: 12.3, h: 0.3,
      fontFace: FONT_B, fontSize: 11, color: C.cyan, bold: true,
      charSpacing: 4, margin: 0,
    });
  }
  // title
  slide.addText(title, {
    x: 0.5, y: kicker ? 0.6 : 0.4, w: 12.3, h: 0.7,
    fontFace: FONT_H, fontSize: 30, color: C.navy, bold: true,
    margin: 0, valign: "top",
  });
}

function addFooter(slide, pageNum, totalPages) {
  // bottom band
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: H - 0.32, w: W, h: 0.32,
    fill: { color: C.navy }, line: { color: C.navy, width: 0 },
  });
  slide.addText("RoboBrain v2 — VLM·VLA·MPC Framework", {
    x: 0.5, y: H - 0.32, w: 8, h: 0.32,
    fontFace: FONT_B, fontSize: 9, color: C.ice, valign: "middle", margin: 0,
  });
  slide.addText(`${pageNum} / ${totalPages}`, {
    x: W - 1.5, y: H - 0.32, w: 1, h: 0.32,
    fontFace: FONT_B, fontSize: 9, color: C.ice, valign: "middle", align: "right", margin: 0,
  });
}

function codeBlock(slide, code, x, y, w, h, opts = {}) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color: C.codeBg }, line: { color: C.navyDk, width: 0 },
  });
  slide.addText(code, {
    x: x + 0.15, y: y + 0.1, w: w - 0.3, h: h - 0.2,
    fontFace: FONT_M, fontSize: opts.fontSize || 10, color: C.codeFg,
    valign: "top", margin: 0, paraSpaceAfter: 0,
  });
}

function colorChip(slide, label, color, x, y, w = 1.4, h = 0.32) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color }, line: { color, width: 0 },
  });
  slide.addText(label, {
    x, y, w, h,
    fontFace: FONT_B, fontSize: 10, color: C.white, bold: true,
    align: "center", valign: "middle", margin: 0,
  });
}

function pill(slide, label, color, x, y, w, h = 0.3) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.05,
    fill: { color }, line: { color, width: 0 },
  });
  slide.addText(label, {
    x, y, w, h,
    fontFace: FONT_B, fontSize: 9, color: C.white, bold: true,
    align: "center", valign: "middle", margin: 0,
  });
}

// =========================================================
// SLIDE 1 — TITLE
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.navyDk };

  // huge accent on left
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 0.35, h: H,
    fill: { color: C.cyan }, line: { color: C.cyan, width: 0 },
  });

  s.addText("RoboBrain · 3DGS · 2026", {
    x: 1.0, y: 1.3, w: 11, h: 0.4,
    fontFace: FONT_B, fontSize: 13, color: C.cyan, bold: true,
    charSpacing: 6, margin: 0,
  });

  s.addText("VLM · VLA · MPC", {
    x: 1.0, y: 1.8, w: 11, h: 0.9,
    fontFace: FONT_H, fontSize: 56, color: C.white, bold: true, margin: 0,
  });

  s.addText("机器人操作框架 v2", {
    x: 1.0, y: 2.75, w: 11, h: 0.7,
    fontFace: FONT_H, fontSize: 36, color: C.ice, margin: 0,
  });

  s.addText("从 5 层架构到 流式精化 与 渐进约束特化", {
    x: 1.0, y: 3.6, w: 11, h: 0.5,
    fontFace: FONT_B, fontSize: 20, color: C.iceDk, italic: true, margin: 0,
  });

  // bottom info card
  s.addShape(pres.shapes.RECTANGLE, {
    x: 1.0, y: 5.4, w: 11.3, h: 1.4,
    fill: { color: C.navy }, line: { color: C.cyan, width: 1 },
  });

  s.addText([
    { text: "覆盖范围   ", options: { fontSize: 11, color: C.cyan, bold: true, charSpacing: 3 } },
    { text: "五层架构 · Predicate Dictionary · L2.5 语义解析 · Hybrid MPC A/B/C · VLM-Supervisor · Streaming Refinement · Progressive Constraint", options: { fontSize: 13, color: C.white } },
  ], { x: 1.3, y: 5.55, w: 10.7, h: 0.6, fontFace: FONT_B, margin: 0, valign: "top" });

  s.addText([
    { text: "目标任务   ", options: { fontSize: 11, color: C.cyan, bold: true, charSpacing: 3 } },
    { text: "叠三个碗 · 双臂端锅 · 含 handover 的 bi-manual 协作  ·  RGB-D 输入", options: { fontSize: 13, color: C.ice } },
  ], { x: 1.3, y: 6.15, w: 10.7, h: 0.5, fontFace: FONT_B, margin: 0, valign: "top" });
}

// =========================================================
// SLIDE 2 — MOTIVATION: why v2
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "为什么需要 v2", "Motivation");

  // problem column
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 1.55, w: 6.0, h: 5.4,
    fill: { color: C.grayLt }, line: { color: C.grayLt, width: 0 },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 1.55, w: 0.1, h: 5.4,
    fill: { color: C.coral }, line: { color: C.coral, width: 0 },
  });
  s.addText("v1 outline 暴露的三个事实", {
    x: 0.75, y: 1.65, w: 5.7, h: 0.4,
    fontFace: FONT_H, fontSize: 18, color: C.navy, bold: true, margin: 0,
  });

  const probs = [
    ["数据是 RGB-D，不是纯 RGB", "深度信息没被任何模块系统使用，affordance grounding 沿用 2D pipeline 浪费输入"],
    ["目标含双臂协作 / handover", "VLM 不懂 IK / 不知道 arm assignment / 不会生成 handover 模板，plan 在双臂场景必然失败"],
    ["VLM 既是 planner 又是 supervisor", "v1 把 VLM 当一次性 plan 生成器，但执行中的 drift 检测、约束违反判定也需要 VLM 的语义判断"],
  ];
  probs.forEach((p, i) => {
    const y0 = 2.15 + i * 1.55;
    s.addShape(pres.shapes.OVAL, {
      x: 0.85, y: y0 + 0.08, w: 0.35, h: 0.35,
      fill: { color: C.coral }, line: { color: C.coral, width: 0 },
    });
    s.addText(`${i + 1}`, {
      x: 0.85, y: y0 + 0.08, w: 0.35, h: 0.35,
      fontFace: FONT_B, fontSize: 13, color: C.white, bold: true,
      align: "center", valign: "middle", margin: 0,
    });
    s.addText(p[0], {
      x: 1.35, y: y0, w: 5.0, h: 0.4,
      fontFace: FONT_H, fontSize: 14, color: C.navy, bold: true, margin: 0,
    });
    s.addText(p[1], {
      x: 1.35, y: y0 + 0.45, w: 5.0, h: 0.95,
      fontFace: FONT_B, fontSize: 11, color: C.charcoal, margin: 0, valign: "top",
    });
  });

  // arrow
  s.addShape(pres.shapes.RIGHT_TRIANGLE, {
    x: 6.7, y: 3.9, w: 0.5, h: 0.7,
    fill: { color: C.navy }, line: { color: C.navy, width: 0 },
    rotate: 90,
  });

  // solution column
  s.addShape(pres.shapes.RECTANGLE, {
    x: 7.3, y: 1.55, w: 5.5, h: 5.4,
    fill: { color: C.navy }, line: { color: C.navy, width: 0 },
  });
  s.addText("v2 的回应", {
    x: 7.55, y: 1.65, w: 5.2, h: 0.4,
    fontFace: FONT_H, fontSize: 18, color: C.cyan, bold: true, margin: 0,
  });

  const sols = [
    ["五层 + 旁路 架构", "插入 Embodiment Grounder（IK / arm assign / handover）+ 旁路 VLM-Supervisor"],
    ["Predicate Dictionary 窄腰", "~18 个 predicate，VLM 训练 / MPC 实现 / Supervisor 判断三者共用"],
    ["Sequencing vs Synchronization", "拆开两类约束——handover 是同步关键，不是顺序自由"],
    ["MPC 限定为 constraint projector", "不强行做 forward dynamics，PointWorld 旁路按需调用"],
  ];
  sols.forEach((p, i) => {
    const y0 = 2.15 + i * 1.15;
    s.addText("◆", {
      x: 7.55, y: y0, w: 0.25, h: 0.35,
      fontFace: FONT_H, fontSize: 16, color: C.cyan, margin: 0, valign: "top",
    });
    s.addText(p[0], {
      x: 7.85, y: y0, w: 4.7, h: 0.35,
      fontFace: FONT_H, fontSize: 13, color: C.white, bold: true, margin: 0,
    });
    s.addText(p[1], {
      x: 7.85, y: y0 + 0.38, w: 4.7, h: 0.7,
      fontFace: FONT_B, fontSize: 10.5, color: C.ice, margin: 0, valign: "top",
    });
  });

  addFooter(s, 2, 24);
}

// =========================================================
// SLIDE 3 — Architecture overview (5-layer)
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "五层 + 1 旁路 架构总览", "Architecture");

  // main stack (4 stacked layers in center)
  const layers = [
    { name: "L0 · VLM-Planner",       hint: "embodiment-agnostic; predicate-only output",  c: C.navy },
    { name: "L1 · Embodiment Grounder", hint: "IK · WorkspaceMap · ArmAssigner · Handover · CoManip", c: C.purple },
    { name: "L2 · Affordance Grounding", hint: "LangSAM + depth lift（简化 pipeline）",            c: C.green  },
    { name: "L3 · VLA Executor",         hint: "黑盒先验路径，不要求 constraint-conditioned",       c: C.amber  },
    { name: "L4 · Hybrid MPC A/B/C",     hint: "Stage A 约束 projector · Stage B/C PointWorld",     c: C.coral  },
  ];

  const baseX = 1.0, baseY = 1.55, lw = 7.5, lh = 0.85;
  layers.forEach((L, i) => {
    const y = baseY + i * (lh + 0.08);
    s.addShape(pres.shapes.RECTANGLE, {
      x: baseX, y, w: lw, h: lh,
      fill: { color: L.c }, line: { color: L.c, width: 0 },
    });
    s.addText(L.name, {
      x: baseX + 0.2, y: y + 0.08, w: lw - 0.4, h: 0.4,
      fontFace: FONT_H, fontSize: 16, color: C.white, bold: true, margin: 0,
    });
    s.addText(L.hint, {
      x: baseX + 0.2, y: y + 0.45, w: lw - 0.4, h: 0.35,
      fontFace: FONT_M, fontSize: 10.5, color: C.ice, margin: 0,
    });
  });

  // arrows between layers
  for (let i = 0; i < layers.length - 1; i++) {
    const y = baseY + (i + 1) * (lh + 0.08) - 0.06;
    s.addShape(pres.shapes.DOWN_ARROW, {
      x: baseX + lw / 2 - 0.15, y: y - 0.05, w: 0.3, h: 0.18,
      fill: { color: C.charcoal }, line: { color: C.charcoal, width: 0 },
    });
  }

  // L2.5 callout (between L2 and L3)
  s.addShape(pres.shapes.RECTANGLE, {
    x: 8.7, y: baseY + 2.07, w: 4.1, h: 0.7,
    fill: { color: C.iceDk }, line: { color: C.navy, width: 1 },
  });
  s.addText("L2.5 · Semantic Resolver", {
    x: 8.8, y: baseY + 2.1, w: 3.9, h: 0.3,
    fontFace: FONT_H, fontSize: 12, color: C.navy, bold: true, margin: 0,
  });
  s.addText("Deferred refs · VLM-Binder · Blackboard", {
    x: 8.8, y: baseY + 2.4, w: 3.9, h: 0.3,
    fontFace: FONT_M, fontSize: 9, color: C.navyDk, margin: 0,
  });

  // VLM-Supervisor bypass on right
  s.addShape(pres.shapes.RECTANGLE, {
    x: 8.7, y: baseY, w: 4.1, h: 1.85,
    fill: { color: C.coral }, line: { color: C.coral, width: 0 },
  });
  s.addText("VLM-Supervisor （旁路）", {
    x: 8.85, y: baseY + 0.1, w: 3.9, h: 0.35,
    fontFace: FONT_H, fontSize: 13, color: C.white, bold: true, margin: 0,
  });
  s.addText("• 事件驱动 · 战略层", {
    x: 8.85, y: baseY + 0.5, w: 3.9, h: 0.3,
    fontFace: FONT_B, fontSize: 10, color: C.white, margin: 0,
  });
  s.addText("• 6 个决策: continue / advance /", {
    x: 8.85, y: baseY + 0.8, w: 3.9, h: 0.3,
    fontFace: FONT_B, fontSize: 10, color: C.white, margin: 0,
  });
  s.addText("  downgrade / force_refine /", {
    x: 8.85, y: baseY + 1.05, w: 3.9, h: 0.3,
    fontFace: FONT_B, fontSize: 10, color: C.white, margin: 0,
  });
  s.addText("  full_replan / abort", {
    x: 8.85, y: baseY + 1.3, w: 3.9, h: 0.3,
    fontFace: FONT_B, fontSize: 10, color: C.white, margin: 0,
  });
  s.addText("• 不改单步动作", {
    x: 8.85, y: baseY + 1.55, w: 3.9, h: 0.3,
    fontFace: FONT_B, fontSize: 10, color: C.white, italic: true, margin: 0,
  });

  // bottom: Streaming Refiner card
  s.addShape(pres.shapes.RECTANGLE, {
    x: 8.7, y: baseY + 3.0, w: 4.1, h: 1.8,
    fill: { color: C.purple }, line: { color: C.purple, width: 0 },
  });
  s.addText("Streaming Refiner （并行）", {
    x: 8.85, y: baseY + 3.1, w: 3.9, h: 0.35,
    fontFace: FONT_H, fontSize: 13, color: C.white, bold: true, margin: 0,
  });
  s.addText("• 与 Inner Loop 并行的后台 worker", {
    x: 8.85, y: baseY + 3.5, w: 3.9, h: 0.3,
    fontFace: FONT_B, fontSize: 10, color: C.white, margin: 0,
  });
  s.addText("• 维持 lookahead 窗口（≤ 2）", {
    x: 8.85, y: baseY + 3.8, w: 3.9, h: 0.3,
    fontFace: FONT_B, fontSize: 10, color: C.white, margin: 0,
  });
  s.addText("• 单 stage 单 pass，不迭代", {
    x: 8.85, y: baseY + 4.1, w: 3.9, h: 0.3,
    fontFace: FONT_B, fontSize: 10, color: C.white, margin: 0,
  });
  s.addText("• 见 §11.6 streaming 设计", {
    x: 8.85, y: baseY + 4.4, w: 3.9, h: 0.3,
    fontFace: FONT_B, fontSize: 10, color: C.ice, italic: true, margin: 0,
  });

  addFooter(s, 3, 24);
}

// =========================================================
// SLIDE 4 — Eight Design Disciplines D1-D8
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "八条设计纪律", "D1 – D8");

  const D = [
    ["D1", "约束契约非动作脚本", "Plan 是 outcome 集合，不是 imperative 命令序列", C.navy],
    ["D2", "outcome-based 监督",  "Supervisor 评估目标 / 约束，不评估 step 顺序", C.navy],
    ["D3", "VLM embodiment-agnostic", "VLM 不输出 arm / IK / handover，留给 Grounder", C.navy],
    ["D4", "Predicate Dictionary 窄腰", "VLM / MPC / Supervisor 三方共用同一份谓词字典", C.navy],
    ["D5", "频段分层",        "L1 / L2 / L2.5 / L3 在不同频率运行，权限随频率反比", C.navy],
    ["D6", "精化与执行并行 (新)", "Refiner 永远在后台，不阻塞 main loop", C.purple],
    ["D7", "永不依赖 PointWorld 远期预测 (新)", "lookahead ≤ 2 stage 是硬上限", C.purple],
    ["D8", "Stage A 始终兜底 (新)", "任何精化路径失败，Stage A 都能让系统跑下去", C.purple],
  ];

  D.forEach((d, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 0.5 + col * 6.3;
    const y = 1.55 + row * 1.35;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 6.0, h: 1.2,
      fill: { color: C.white }, line: { color: C.grayLt, width: 1 },
    });
    // accent bar
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 0.08, h: 1.2,
      fill: { color: d[3] }, line: { color: d[3], width: 0 },
    });
    // D-number
    s.addText(d[0], {
      x: x + 0.25, y: y + 0.15, w: 0.7, h: 0.4,
      fontFace: FONT_H, fontSize: 22, color: d[3], bold: true, margin: 0,
    });
    s.addText(d[1], {
      x: x + 0.95, y: y + 0.15, w: 4.9, h: 0.4,
      fontFace: FONT_H, fontSize: 14, color: C.navy, bold: true, margin: 0, valign: "middle",
    });
    s.addText(d[2], {
      x: x + 0.95, y: y + 0.6, w: 4.9, h: 0.55,
      fontFace: FONT_B, fontSize: 11, color: C.charcoal, margin: 0, valign: "top",
    });
  });

  s.addText("D6 – D8 是 streaming refinement pivot 时新增的纪律", {
    x: 0.5, y: 6.85, w: 12.3, h: 0.3,
    fontFace: FONT_B, fontSize: 11, color: C.purple, italic: true, align: "center", margin: 0,
  });

  addFooter(s, 4, 24);
}

// =========================================================
// SLIDE 5 — Predicate Dictionary
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "Predicate Dictionary · 项目窄腰", "The Narrow Waist");

  // tagline
  s.addText("~18 个 predicate · 6 大类 · 每个 predicate 三方共用同一定义",  {
    x: 0.5, y: 1.45, w: 12.3, h: 0.35,
    fontFace: FONT_B, fontSize: 13, color: C.charcoal, italic: true, margin: 0,
  });

  // 6 categories grid
  const cats = [
    ["Spatial",   ["above", "on_top_of", "inside", "near", "far"],         C.navy],
    ["Contact",   ["touching", "grasped", "released", "supported"],         C.purple],
    ["Pose",      ["upright", "tilted", "aligned"],                         C.cyan],
    ["Direction", ["facing", "moving_toward"],                              C.green],
    ["Safety",    ["clear_of", "max_force"],                                C.coral],
    ["Temporal",  ["before", "after", "during", "synchronized_with"],       C.amber],
  ];

  cats.forEach((c, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = 0.5 + col * 4.3;
    const y = 2.0 + row * 1.8;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 4.0, h: 1.6,
      fill: { color: C.grayLt }, line: { color: c[2], width: 2 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 4.0, h: 0.45,
      fill: { color: c[2] }, line: { color: c[2], width: 0 },
    });
    s.addText(c[0], {
      x: x + 0.15, y, w: 3.7, h: 0.45,
      fontFace: FONT_H, fontSize: 14, color: C.white, bold: true, valign: "middle", margin: 0,
    });
    const list = c[1].map((p, idx) => ({
      text: p,
      options: { fontFace: FONT_M, fontSize: 11, color: C.navy, breakLine: idx < c[1].length - 1 },
    }));
    s.addText(list, { x: x + 0.2, y: y + 0.55, w: 3.7, h: 0.95, margin: 0, valign: "top" });
  });

  // bottom: triple-binding callout
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 5.85, w: 12.3, h: 1.15,
    fill: { color: C.navy }, line: { color: C.navy, width: 0 },
  });
  s.addText("Triple binding: 每个 predicate 必须实现", {
    x: 0.8, y: 5.95, w: 12, h: 0.3,
    fontFace: FONT_H, fontSize: 13, color: C.cyan, bold: true, margin: 0,
  });

  const triples = [
    ["evaluate(scene) → bool",       "供 Supervisor 在线判断约束是否被违反",        C.cyan],
    ["cost(scene) → float",          "供 MPC Stage A 把违反程度转化为梯度",          C.green],
    ["cost_on_pointcloud(pcd)",      "供 Stage B/C 在 PointWorld 预测点云上评估",   C.amber],
  ];
  triples.forEach((t, i) => {
    const x = 0.8 + i * 4.1;
    colorChip(s, t[0], t[2], x, 6.3, 3.8, 0.3);
    s.addText(t[1], {
      x, y: 6.65, w: 3.8, h: 0.35,
      fontFace: FONT_B, fontSize: 10, color: C.white, margin: 0,
    });
  });

  addFooter(s, 5, 24);
}

// =========================================================
// SLIDE 6 — VLM-Planner output schema
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "VLM-Planner 输出 schema", "The Plan Contract");

  // left: schema
  const schema = `{
  "task": "stack 3 bowls",
  "goal": [
    {"pred": "stacked", "args": ["bowl_a","bowl_b","bowl_c"]}
  ],
  "global_constraints": [
    {"pred": "upright", "args": ["each:bowl"]},
    {"pred": "max_force", "args": ["gripper", 8.0]}
  ],
  "lookahead": 1,
  "steps": [
    {
      "stage_idx": 1,
      "name": "approach_first_bowl",
      "action": "grasp",
      "target": "bowl_a",
      "affordance_region": "rim_top",
      "preconds":  [{"pred": "reachable", "args": ["bowl_a"]}],
      "postconds": [{"pred": "grasped",   "args": ["bowl_a"]}],
      "constraints": [
        {"pred": "approach_speed_max", "args": [0.1]}
      ],
      "mpc_mode": "B",
      "binding_mode": "eager"
    }
    // ... more stages
  ]
}`;
  codeBlock(s, schema, 0.5, 1.5, 7.4, 5.5, { fontSize: 10 });

  // right: field explanations
  const fields = [
    ["goal",              "终态 predicate 集合（id-aware 或 existential）",  C.green],
    ["global_constraints","always-on 约束，每个 stage 都必须满足",            C.cyan],
    ["lookahead",         "Streaming refiner 窗口大小 0 / 1 / 2 / 3",          C.purple],
    ["affordance_region", "VLM 描述 affordance 区域（不出 UV 坐标）",         C.amber],
    ["preconds / postconds","stage 入口 / 出口的 predicate 约束",              C.navy],
    ["mpc_mode",          "A 默认 / B 接触 / C 多体耦合 — 控制 PointWorld 启用", C.coral],
    ["binding_mode",      "eager (plan-time 绑) / lazy (runtime 绑 — 渐进约束)", C.purple],
  ];

  s.addText("字段角色", {
    x: 8.1, y: 1.5, w: 4.8, h: 0.4,
    fontFace: FONT_H, fontSize: 16, color: C.navy, bold: true, margin: 0,
  });

  fields.forEach((f, i) => {
    const y = 1.95 + i * 0.7;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 8.1, y, w: 0.08, h: 0.6,
      fill: { color: f[2] }, line: { color: f[2], width: 0 },
    });
    s.addText(f[0], {
      x: 8.25, y, w: 4.7, h: 0.3,
      fontFace: FONT_M, fontSize: 12, color: f[2], bold: true, margin: 0,
    });
    s.addText(f[1], {
      x: 8.25, y: y + 0.28, w: 4.7, h: 0.35,
      fontFace: FONT_B, fontSize: 10, color: C.charcoal, margin: 0,
    });
  });

  addFooter(s, 6, 24);
}

// =========================================================
// SLIDE 7 — Template: 叠三个碗
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "VLM 输出 Template · 叠三个碗", "Example 1");

  const tpl = `{
  "task": "把三个碗叠在一起",
  "goal": [{"pred": "stacked", "args": ["bowl_1","bowl_2","bowl_3"]}],
  "global_constraints": [
    {"pred": "upright", "args": ["each:bowl"]},
    {"pred": "max_force", "args": ["gripper", 8.0]}
  ],
  "lookahead": 1,
  "binding_mode_hint": "lazy",
  "steps": [
    { "stage_idx": 1, "action": "grasp", "target": "bowl_a",
      "affordance_region": "rim_top",
      "postconds": [{"pred":"grasped","args":["bowl_a"]}],
      "mpc_mode": "B" },

    { "stage_idx": 2, "action": "place", "target": "bowl_a",
      "place_on": "bowl_b",
      "affordance_region": "bowl_b/top_center",
      "preconds":  [{"pred":"grasped","args":["bowl_a"]}],
      "postconds": [{"pred":"on_top_of","args":["bowl_a","bowl_b"]},
                    {"pred":"released","args":["bowl_a"]},
                    {"pred":"upright","args":["bowl_a"]}],
      "mpc_mode": "C" },

    { "stage_idx": 3, "action": "grasp", "target": "bowl_c",
      "affordance_region": "rim_top",
      "postconds": [{"pred":"grasped","args":["bowl_c"]}],
      "mpc_mode": "B" },

    { "stage_idx": 4, "action": "place", "target": "bowl_c",
      "place_on": "bowl_a",
      "affordance_region": "bowl_a/top_center",
      "postconds": [{"pred":"stacked","args":["bowl_1","bowl_2","bowl_3"]}],
      "mpc_mode": "C" }
  ]
}`;
  codeBlock(s, tpl, 0.5, 1.5, 8.0, 5.5, { fontSize: 9 });

  // right side commentary
  const comments = [
    ["顺序自由",   "1→2→3 与 3→2→1 都对，goal predicate 不指定先后", C.green],
    ["affordance 是区域，不是 UV 坐标", "rim_top / top_center 由 grounding 模块负责定位", C.cyan],
    ["mpc_mode 分级",  "grasp = B（接触瞬间）, place = C（接触富集）", C.amber],
    ["问题暗藏",   "若 VLM 必须 commit bowl_a/b/c identity，则陷入组合爆炸 — 看第 18 张", C.coral],
  ];

  s.addText("关键观察", {
    x: 8.7, y: 1.5, w: 4.2, h: 0.4,
    fontFace: FONT_H, fontSize: 16, color: C.navy, bold: true, margin: 0,
  });

  comments.forEach((c, i) => {
    const y = 2.0 + i * 1.2;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 8.7, y, w: 4.2, h: 1.1,
      fill: { color: C.grayLt }, line: { color: c[2], width: 1.5 },
    });
    s.addText(c[0], {
      x: 8.85, y: y + 0.1, w: 4.0, h: 0.35,
      fontFace: FONT_H, fontSize: 12, color: c[2], bold: true, margin: 0,
    });
    s.addText(c[1], {
      x: 8.85, y: y + 0.45, w: 4.0, h: 0.6,
      fontFace: FONT_B, fontSize: 10, color: C.charcoal, margin: 0, valign: "top",
    });
  });

  addFooter(s, 7, 24);
}

// =========================================================
// SLIDE 8 — Template: 双臂端锅
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "VLM 输出 Template · 双臂端锅", "Example 2 · Bi-manual");

  const tpl = `{
  "task": "双臂把锅端到桌子另一侧",
  "goal": [
    {"pred": "at_pose", "args": ["pot", "target_location"]},
    {"pred": "upright", "args": ["pot"]}
  ],
  "global_constraints": [
    {"pred": "upright",    "args": ["pot"]},
    {"pred": "max_tilt",   "args": ["pot", 15.0]},
    {"pred": "co_manipulation", "args": ["arm_left","arm_right","pot"]}
  ],
  "lookahead": 2,
  "steps": [
    { "stage_idx": 1, "action": "approach", "target": "pot/handle_left",
      "postconds": [{"pred":"near","args":["ee","pot/handle_left"]}] },

    { "stage_idx": 2, "action": "dual_grasp",
      "targets": ["pot/handle_left", "pot/handle_right"],
      "synchronization": "simultaneous_close",
      "postconds": [{"pred":"grasped","args":["pot/handle_left"]},
                    {"pred":"grasped","args":["pot/handle_right"]}],
      "mpc_mode": "C" },

    { "stage_idx": 3, "action": "co_lift",
      "target": "pot", "lift_height": 0.15,
      "constraints": [
        {"pred":"synchronized_with","args":["arm_left.z","arm_right.z","tol=0.01"]},
        {"pred":"upright","args":["pot"]}
      ],
      "mpc_mode": "C" },

    { "stage_idx": 4, "action": "co_transport",
      "target": "target_location",
      "constraints": [
        {"pred":"upright","args":["pot"]},
        {"pred":"clear_of","args":["pot","obstacles"]}
      ],
      "mpc_mode": "C" },

    { "stage_idx": 5, "action": "co_place_and_release",
      "synchronization": "simultaneous_release",
      "postconds": [{"pred":"at_pose","args":["pot","target_location"]}] }
  ]
}`;
  codeBlock(s, tpl, 0.5, 1.5, 8.2, 5.5, { fontSize: 8.5 });

  // right: explainer
  const points = [
    ["co_manipulation predicate", "global constraint，整个任务期间双臂物理耦合，由 CoManipulationDetector 维持", C.purple],
    ["synchronization 字段", "VLM 标识同步关键点；不是 sequencing", C.cyan],
    ["mpc_mode: C", "双臂多体耦合 → PointWorld + CEM/MPPI", C.coral],
    ["lookahead: 2", "对应 mpc_mode C 的默认", C.amber],
    ["VLM 不出 IK", "left/right arm 分配由 Embodiment Grounder 完成", C.green],
  ];

  s.addText("Bi-manual 设计点", {
    x: 8.9, y: 1.5, w: 4.0, h: 0.4,
    fontFace: FONT_H, fontSize: 15, color: C.navy, bold: true, margin: 0,
  });

  points.forEach((p, i) => {
    const y = 2.0 + i * 1.0;
    s.addShape(pres.shapes.OVAL, {
      x: 8.9, y: y + 0.05, w: 0.25, h: 0.25,
      fill: { color: p[2] }, line: { color: p[2], width: 0 },
    });
    s.addText(p[0], {
      x: 9.25, y, w: 3.7, h: 0.3,
      fontFace: FONT_H, fontSize: 11, color: p[2], bold: true, margin: 0,
    });
    s.addText(p[1], {
      x: 9.25, y: y + 0.3, w: 3.7, h: 0.65,
      fontFace: FONT_B, fontSize: 9.5, color: C.charcoal, margin: 0, valign: "top",
    });
  });

  addFooter(s, 8, 24);
}

// =========================================================
// SLIDE 9 — Embodiment Grounder
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "Embodiment Grounder · 5 个组件", "L1 · embodiment-aware translation");

  // central role tag
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 1.5, w: 12.3, h: 0.5,
    fill: { color: C.purple }, line: { color: C.purple, width: 0 },
  });
  s.addText("把 embodiment-agnostic 的 VLM plan 翻译成具体到机器人本体的 grounded plan", {
    x: 0.5, y: 1.5, w: 12.3, h: 0.5,
    fontFace: FONT_B, fontSize: 13, color: C.white, italic: true,
    align: "center", valign: "middle", margin: 0,
  });

  const comps = [
    ["IK + Collision",   "cuRobo (GPU-batched)\n备选: Pinocchio / TracIK",
     "为每个 stage 计算 reachable EE pose；过滤 collision",
     C.navy],
    ["WorkspaceMap",     "预计算 voxel reachability\n双臂分别 cache",
     "O(1) 查询 \"this point reachable by which arm\"",
     C.cyan],
    ["ArmAssigner",      "heuristic + L2.5 fallback\nVLM-Binder 做边缘 case",
     "为 grasp / approach stage 分配 left or right arm",
     C.green],
    ["HandoverPlanner",  "Template-based\n+ kinematic validate",
     "自动插入 handover 中间 stage；同步 release 与 grasp",
     C.amber],
    ["CoManipulationDetector", "checks goal + global constraints\n触发 dual-arm trajectory",
     "识别 co_manipulation predicate；构造对称双臂轨迹",
     C.coral],
  ];

  comps.forEach((c, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = 0.5 + col * 4.3;
    const y = 2.25 + row * 2.35;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 4.0, h: 2.15,
      fill: { color: C.white }, line: { color: c[3], width: 2 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 4.0, h: 0.5,
      fill: { color: c[3] }, line: { color: c[3], width: 0 },
    });
    s.addText(c[0], {
      x: x + 0.2, y, w: 3.6, h: 0.5,
      fontFace: FONT_H, fontSize: 14, color: C.white, bold: true,
      valign: "middle", margin: 0,
    });
    s.addText(c[1], {
      x: x + 0.2, y: y + 0.6, w: 3.6, h: 0.7,
      fontFace: FONT_M, fontSize: 10, color: C.navy, margin: 0, valign: "top",
    });
    s.addShape(pres.shapes.LINE, {
      x: x + 0.2, y: y + 1.35, w: 3.6, h: 0,
      line: { color: C.grayLt, width: 1 },
    });
    s.addText(c[2], {
      x: x + 0.2, y: y + 1.4, w: 3.6, h: 0.7,
      fontFace: FONT_B, fontSize: 10, color: C.charcoal, margin: 0, valign: "top",
    });
  });

  addFooter(s, 9, 24);
}

// =========================================================
// SLIDE 10 — L2.5 Semantic Resolver
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "L2.5 Semantic Resolver · Deferred References", "VLM 在 runtime 的运行时贡献");

  // left: scenario
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 1.5, w: 6.2, h: 2.5,
    fill: { color: C.grayLt }, line: { color: C.cyan, width: 2 },
  });
  s.addText("场景：碗散在桌上，VLM plan-time 不知道顺序", {
    x: 0.7, y: 1.6, w: 5.9, h: 0.4,
    fontFace: FONT_H, fontSize: 13, color: C.navy, bold: true, margin: 0,
  });
  codeBlock(s,
`{ "action": "grasp",
  "target": "?bowl_1",           // deferred
  "binder": "nearest_bowl_to(ee)" }
{ "action": "place",
  "target": "?bowl_1",
  "place_on": "?bowl_2",
  "binder_2": "any_other_bowl" }`,
    0.7, 2.1, 5.9, 1.8, { fontSize: 11 });

  // right: resolution pipeline
  s.addShape(pres.shapes.RECTANGLE, {
    x: 7.0, y: 1.5, w: 5.8, h: 2.5,
    fill: { color: C.navy }, line: { color: C.navy, width: 0 },
  });
  s.addText("Resolution Pipeline (runtime, 在 stage 即将执行前)", {
    x: 7.2, y: 1.6, w: 5.5, h: 0.35,
    fontFace: FONT_H, fontSize: 13, color: C.cyan, bold: true, margin: 0,
  });

  const steps = [
    ["1. Binder",  "调用 binder function (nearest_bowl_to(ee))"],
    ["2. Scene Blackboard", "查询 / 写入解析结果 (?bowl_1 = bowl_id_5)"],
    ["3. VLM-Refiner", "若 binder 失败 → VLM 兜底裁决（边缘 case）"],
    ["4. Propagate",  "传播到下游 stage (?bowl_2 ≠ ?bowl_1)"],
  ];

  steps.forEach((st, i) => {
    const y = 2.05 + i * 0.45;
    s.addText(st[0], {
      x: 7.2, y, w: 1.7, h: 0.35,
      fontFace: FONT_M, fontSize: 11, color: C.cyan, bold: true, margin: 0,
    });
    s.addText(st[1], {
      x: 8.9, y, w: 3.9, h: 0.35,
      fontFace: FONT_B, fontSize: 10, color: C.ice, margin: 0,
    });
  });

  // bottom: three contributions of VLM at runtime
  s.addText("VLM 在 L2.5 的三种 runtime 贡献", {
    x: 0.5, y: 4.25, w: 12.3, h: 0.35,
    fontFace: FONT_H, fontSize: 14, color: C.navy, bold: true, margin: 0,
  });

  const contribs = [
    ["Cache hit", "Binder 已能解决，无需 VLM",  C.green,  "~95% case"],
    ["Skip",       "可跳过的语义歧义（不重要的细节）",   C.amber,  "~3% case"],
    ["Fallback",   "Binder 失败 / OOD → VLM-Refiner 兜底", C.coral,  "~2% case"],
  ];

  contribs.forEach((c, i) => {
    const x = 0.5 + i * 4.27;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 4.7, w: 4.07, h: 2.05,
      fill: { color: C.white }, line: { color: c[2], width: 2 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 4.7, w: 4.07, h: 0.5,
      fill: { color: c[2] }, line: { color: c[2], width: 0 },
    });
    s.addText(c[0], {
      x: x + 0.2, y: 4.7, w: 2.3, h: 0.5,
      fontFace: FONT_H, fontSize: 14, color: C.white, bold: true, valign: "middle", margin: 0,
    });
    s.addText(c[3], {
      x: x + 2.5, y: 4.7, w: 1.4, h: 0.5,
      fontFace: FONT_M, fontSize: 11, color: C.white, valign: "middle", align: "right", margin: 0,
    });
    s.addText(c[1], {
      x: x + 0.2, y: 5.35, w: 3.7, h: 1.35,
      fontFace: FONT_B, fontSize: 11, color: C.charcoal, margin: 0, valign: "top",
    });
  });

  addFooter(s, 10, 24);
}

// =========================================================
// SLIDE 11 — Hybrid MPC A/B/C
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "Hybrid MPC · Stage A / B / C", "Lazy evaluation by mpc_mode hint");

  const stages = [
    {
      name: "Stage A · Always-on",
      desc: "Constraint Projector",
      lat: "< 5 ms",
      use: "默认 · 每个 timestep 都跑",
      body: ["• 把 predicate 转 cost\n• 单步 projection\n• 不调 PointWorld\n• 是 D8 兜底安全网"],
      c: C.green,
    },
    {
      name: "Stage B · On-demand",
      desc: "PointWorld single-step",
      lat: "30 – 80 ms",
      use: "VLM 标 mpc_mode=B 时（接触瞬间）",
      body: ["• PointWorld 预测下一步点云\n• 评估接触约束\n• 单步前向\n• 替代 Stage A 决策"],
      c: C.amber,
    },
    {
      name: "Stage C · Heavy",
      desc: "PointWorld CEM / MPPI",
      lat: "200 – 500 ms",
      use: "VLM 标 mpc_mode=C 时（接触富集）",
      body: ["• 多 step rollout + CEM 优化\n• 多体耦合（双臂 / contact-rich）\n• 频段最低，权限最大\n• 只在必要时启用"],
      c: C.coral,
    },
  ];

  stages.forEach((st, i) => {
    const x = 0.5 + i * 4.27;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.5, w: 4.07, h: 5.0,
      fill: { color: C.white }, line: { color: st.c, width: 2 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.5, w: 4.07, h: 0.85,
      fill: { color: st.c }, line: { color: st.c, width: 0 },
    });
    s.addText(st.name, {
      x: x + 0.2, y: 1.55, w: 3.7, h: 0.4,
      fontFace: FONT_H, fontSize: 14, color: C.white, bold: true, margin: 0,
    });
    s.addText(st.desc, {
      x: x + 0.2, y: 1.95, w: 3.7, h: 0.4,
      fontFace: FONT_M, fontSize: 11, color: C.white, italic: true, margin: 0,
    });

    // latency
    s.addText("延迟", {
      x: x + 0.2, y: 2.55, w: 1, h: 0.3,
      fontFace: FONT_B, fontSize: 10, color: C.gray, margin: 0,
    });
    s.addText(st.lat, {
      x: x + 0.2, y: 2.85, w: 3.7, h: 0.45,
      fontFace: FONT_M, fontSize: 22, color: st.c, bold: true, margin: 0,
    });

    // use
    s.addText("触发条件", {
      x: x + 0.2, y: 3.45, w: 3.7, h: 0.3,
      fontFace: FONT_B, fontSize: 10, color: C.gray, margin: 0,
    });
    s.addText(st.use, {
      x: x + 0.2, y: 3.75, w: 3.7, h: 0.5,
      fontFace: FONT_B, fontSize: 11, color: C.navy, margin: 0,
    });

    // separator
    s.addShape(pres.shapes.LINE, {
      x: x + 0.2, y: 4.4, w: 3.7, h: 0,
      line: { color: C.grayLt, width: 1 },
    });

    s.addText(st.body[0], {
      x: x + 0.2, y: 4.5, w: 3.7, h: 1.9,
      fontFace: FONT_B, fontSize: 11, color: C.charcoal, margin: 0, valign: "top",
    });
  });

  s.addText("VLM 用 mpc_mode 字段做 hint；Stage A 始终运行兜底（D8）", {
    x: 0.5, y: 6.7, w: 12.3, h: 0.3,
    fontFace: FONT_B, fontSize: 11, color: C.navy, italic: true, align: "center", margin: 0,
  });

  addFooter(s, 11, 24);
}

// =========================================================
// SLIDE 12 — VLM-Supervisor
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "VLM-Supervisor · 旁路战略层", "Event-driven · 6 decisions");

  s.addText("不修改单步动作，只走 stage / replan / refine 通道", {
    x: 0.5, y: 1.45, w: 12.3, h: 0.35,
    fontFace: FONT_B, fontSize: 13, color: C.charcoal, italic: true, margin: 0,
  });

  // Trigger column
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 1.95, w: 4.0, h: 5.0,
    fill: { color: C.grayLt }, line: { color: C.amber, width: 2 },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 1.95, w: 4.0, h: 0.5,
    fill: { color: C.amber }, line: { color: C.amber, width: 0 },
  });
  s.addText("Triggers", {
    x: 0.65, y: 1.95, w: 3.8, h: 0.5,
    fontFace: FONT_H, fontSize: 15, color: C.white, bold: true, valign: "middle", margin: 0,
  });

  const triggers = [
    "Predicate 突然不可满足",
    "PointWorld 预测严重偏离",
    "VLA action 多步漂移",
    "Refiner 跟不上节奏",
    "Sensor 异常或被遮挡",
    "Timeout（stage > 预期时长）",
  ];
  triggers.forEach((t, i) => {
    s.addText([
      { text: "▸ ", options: { color: C.amber, bold: true } },
      { text: t, options: { color: C.charcoal } },
    ], {
      x: 0.7, y: 2.6 + i * 0.65, w: 3.7, h: 0.55,
      fontFace: FONT_B, fontSize: 11, margin: 0, valign: "top",
    });
  });

  // arrow
  s.addShape(pres.shapes.RIGHT_TRIANGLE, {
    x: 4.6, y: 4.0, w: 0.45, h: 0.55,
    fill: { color: C.navy }, line: { color: C.navy, width: 0 },
    rotate: 90,
  });

  // Decisions column (6)
  const decs = [
    ["continue",            "无事发生，继续 inner loop",            C.green],
    ["advance_stage",       "提前进入下一 stage (postcond 已满足)",  C.green],
    ["downgrade_mpc_mode",  "C → B → A，降级到更便宜的 mode",        C.amber],
    ["force_refine_now",    "紧急通道，让 refiner 优先精化某 stage", C.purple],
    ["full_replan",         "回到 VLM-Planner 重新规划",             C.coral],
    ["abort",               "终止执行，等待人工介入",                 C.coral],
  ];

  s.addText("6 种决策", {
    x: 5.3, y: 1.95, w: 7.5, h: 0.5,
    fontFace: FONT_H, fontSize: 15, color: C.navy, bold: true, margin: 0,
  });

  decs.forEach((d, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 5.3 + col * 3.85;
    const y = 2.5 + row * 1.55;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 3.65, h: 1.4,
      fill: { color: C.white }, line: { color: d[2], width: 1.5 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 0.08, h: 1.4,
      fill: { color: d[2] }, line: { color: d[2], width: 0 },
    });
    s.addText(d[0], {
      x: x + 0.2, y: y + 0.1, w: 3.4, h: 0.45,
      fontFace: FONT_M, fontSize: 14, color: d[2], bold: true, margin: 0,
    });
    s.addText(d[1], {
      x: x + 0.2, y: y + 0.55, w: 3.4, h: 0.8,
      fontFace: FONT_B, fontSize: 10.5, color: C.charcoal, margin: 0, valign: "top",
    });
  });

  addFooter(s, 12, 24);
}

// =========================================================
// SLIDE 13 — Streaming Refinement: Why pivot
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "Streaming Refinement · 为什么反转 Pre-Execution", "The Pivot");

  s.addText("\"我觉得在执行前进行闭环判断延时太高了，希望能在执行过程中进行规划闭环\"", {
    x: 0.5, y: 1.45, w: 12.3, h: 0.4,
    fontFace: FONT_B, fontSize: 13, color: C.coral, italic: true,
    align: "center", margin: 0,
  });

  // compare table
  const rows = [
    ["维度",                "Pre-Execution Refinement",     "Streaming Refinement"],
    ["启动延迟",            "~30 s",                         "~1–2 s (Quick Check)"],
    ["Refinement 次数",     "全 plan 多轮 (≤3)",            "每 stage 1 轮 (并行)"],
    ["PointWorld 范围",     "全 plan rollout (含远端不可信)", "单 stage rollout (近端可靠)"],
    ["利用执行结果做 prior", "否",                            "是 (基于 blackboard)"],
    ["Worst case",          "好 plan 也等 30s 才动",          "Refiner 跟不上 → degraded 但仍能跑"],
    ["Compute 模式",        "30s 突发 + 0",                  "持续 2–3 s/stage 后台"],
  ];

  const tx = 0.5, ty = 2.05;
  const colW = [3.0, 4.6, 4.7];
  const rowH = 0.55;

  rows.forEach((r, i) => {
    let x = tx;
    r.forEach((cell, j) => {
      const isHeader = i === 0;
      const isWinner = !isHeader && j === 2;
      const isLoser  = !isHeader && j === 1;
      const fill = isHeader ? C.navy : (isWinner ? "F0FFF0" : (isLoser ? "FFF0F0" : C.white));
      const txtColor = isHeader ? C.white : C.charcoal;
      s.addShape(pres.shapes.RECTANGLE, {
        x, y: ty + i * rowH, w: colW[j], h: rowH,
        fill: { color: fill }, line: { color: C.grayLt, width: 1 },
      });
      s.addText(cell, {
        x: x + 0.15, y: ty + i * rowH, w: colW[j] - 0.3, h: rowH,
        fontFace: isHeader ? FONT_H : (j === 0 ? FONT_H : FONT_B),
        fontSize: isHeader ? 12 : 11,
        color: txtColor, bold: isHeader || j === 0,
        valign: "middle", margin: 0,
      });
      x += colW[j];
    });
  });

  // bottom callout
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 6.0, w: 12.3, h: 1.0,
    fill: { color: C.navy }, line: { color: C.navy, width: 0 },
  });
  s.addText("核心 insight", {
    x: 0.7, y: 6.1, w: 12, h: 0.35,
    fontFace: FONT_H, fontSize: 13, color: C.cyan, bold: true, margin: 0,
  });
  s.addText("Execution 本身就是 world model 的免费 calibration — 每 stage 完成后，blackboard 的 ground-truth state 比 PointWorld 5 步预测准 100 倍。Pre-execution 模式放弃了这个免费的信号源。", {
    x: 0.7, y: 6.45, w: 12, h: 0.5,
    fontFace: FONT_B, fontSize: 12, color: C.ice, margin: 0, valign: "top",
  });

  addFooter(s, 13, 24);
}

// =========================================================
// SLIDE 14 — Streaming Refinement: Architecture
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "Streaming Refinement · 时间轴架构", "Two parallel timelines");

  // execution timeline
  s.addText("Execution Timeline", {
    x: 0.5, y: 1.5, w: 6, h: 0.35,
    fontFace: FONT_H, fontSize: 13, color: C.amber, bold: true, margin: 0,
  });

  // execution boxes
  const exY = 1.95;
  const exItems = [
    { label: "Quick\nCheck", w: 1.0, c: C.amber, dur: "1–2s" },
    { label: "Stage 1", w: 2.0, c: C.navy, dur: "" },
    { label: "Stage 2", w: 2.0, c: C.navy, dur: "" },
    { label: "Stage 3", w: 2.0, c: C.navy, dur: "" },
    { label: "Stage 4", w: 2.0, c: C.navy, dur: "" },
    { label: "...",    w: 1.2, c: C.gray, dur: "" },
  ];
  let exX = 0.5;
  exItems.forEach(it => {
    s.addShape(pres.shapes.RECTANGLE, {
      x: exX, y: exY, w: it.w, h: 0.7,
      fill: { color: it.c }, line: { color: it.c, width: 0 },
    });
    s.addText(it.label, {
      x: exX, y: exY, w: it.w, h: 0.7,
      fontFace: FONT_B, fontSize: 11, color: C.white, bold: true,
      align: "center", valign: "middle", margin: 0,
    });
    exX += it.w + 0.05;
  });

  // refinement timeline
  s.addText("Refinement Timeline (并行)", {
    x: 0.5, y: 3.3, w: 6, h: 0.35,
    fontFace: FONT_H, fontSize: 13, color: C.purple, bold: true, margin: 0,
  });

  const refY = 3.75;
  // gap to align under stage 1
  const refX0 = 0.5 + 1.0 + 0.05;  // after Quick Check
  const refItems = [
    { label: "refine S2 (+S3)\nduring S1", w: 2.0, c: C.purple },
    { label: "refine S3 (+S4)\nduring S2", w: 2.0, c: C.purple },
    { label: "refine S4 (+S5)\nduring S3", w: 2.0, c: C.purple },
    { label: "refine S5 (+S6)\nduring S4", w: 2.0, c: C.purple },
    { label: "...", w: 1.2, c: C.gray },
  ];
  let refX = refX0;
  refItems.forEach(it => {
    s.addShape(pres.shapes.RECTANGLE, {
      x: refX, y: refY, w: it.w, h: 0.7,
      fill: { color: it.c }, line: { color: it.c, width: 0 },
    });
    s.addText(it.label, {
      x: refX, y: refY, w: it.w, h: 0.7,
      fontFace: FONT_B, fontSize: 9.5, color: C.white, bold: true,
      align: "center", valign: "middle", margin: 0,
    });
    refX += it.w + 0.05;
  });

  // dashed arrows from refinement to execution (写 refined stage)
  for (let i = 0; i < 4; i++) {
    const fromX = refX0 + i * 2.05 + 1.0;
    const toX   = 0.5 + 1.05 + (i + 1) * 2.05 + 1.0;
    s.addShape(pres.shapes.LINE, {
      x: fromX, y: refY, w: 0, h: -1.3,
      line: { color: C.purple, width: 1.5, dashType: "dash", endArrowType: "triangle" },
    });
  }

  // legend
  s.addText("↑ refiner 写入下一个 stage 的 refined 版本", {
    x: 0.5, y: 4.6, w: 12.3, h: 0.3,
    fontFace: FONT_B, fontSize: 10, color: C.purple, italic: true, margin: 0,
  });

  // bottom: lookahead window
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 5.1, w: 12.3, h: 1.85,
    fill: { color: C.grayLt }, line: { color: C.purple, width: 2 },
  });
  s.addText("Lookahead 窗口 (D7：硬上限 ≤ 2)", {
    x: 0.7, y: 5.2, w: 12, h: 0.4,
    fontFace: FONT_H, fontSize: 14, color: C.navy, bold: true, margin: 0,
  });

  const lookahead = [
    ["A", "0", "简单 stage，Stage A 单步可控",       C.green],
    ["B", "1", "接触动力学需要单 stage 前瞻",         C.amber],
    ["C", "2", "多体耦合需要更长前瞻",                 C.coral],
  ];
  lookahead.forEach((l, i) => {
    const x = 0.7 + i * 4.1;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 5.7, w: 3.9, h: 1.15,
      fill: { color: C.white }, line: { color: l[3], width: 1.5 },
    });
    s.addText(`mpc_mode ${l[0]} → lookahead ${l[1]}`, {
      x: x + 0.15, y: 5.78, w: 3.6, h: 0.4,
      fontFace: FONT_H, fontSize: 13, color: l[3], bold: true, margin: 0,
    });
    s.addText(l[2], {
      x: x + 0.15, y: 6.2, w: 3.6, h: 0.6,
      fontFace: FONT_B, fontSize: 10.5, color: C.charcoal, margin: 0, valign: "top",
    });
  });

  addFooter(s, 14, 24);
}

// =========================================================
// SLIDE 15 — Streaming Refiner code + fallback
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "Streaming Refiner · 核心代码 与 Fallback", "best-effort enhancement, not prerequisite");

  // left: refiner code
  const code = `class StreamingRefiner:
    def __init__(self, plan, blackboard, lookahead=2):
        self.plan = plan
        self.bb = blackboard
        self.lookahead = lookahead
        self.refined_until = 0

    def run_background(self):
        while not self.bb.execution_done:
            current = self.bb.current_stage_idx
            target = current + self.lookahead
            while self.refined_until < min(target, N-1):
                self._refine_one_stage(self.refined_until + 1)
                self.refined_until += 1
            time.sleep(0.05)

    def _refine_one_stage(self, idx):
        start = self.bb.snapshot()      # blackboard prior
        stg = self.plan.steps[idx]

        pw  = pointworld.rollout(start, stg)            # ~1-2s
        vla = vla.evaluate(start, stg) if lookahead>=2 else None
        crit = critique_synthesizer.synthesize(pw, vla)

        if crit.has_significant_issues():
            self.plan.steps[idx] = vlm.revise(stg, crit) # ~0.5s
        self.bb.mark_refined(idx)`;

  codeBlock(s, code, 0.5, 1.5, 7.5, 4.4, { fontSize: 10 });

  s.addText("单 stage 精化总成本 ~2–3 s", {
    x: 0.5, y: 6.0, w: 7.5, h: 0.3,
    fontFace: FONT_B, fontSize: 11, color: C.purple, italic: true, margin: 0,
  });
  s.addText("Stage 平均执行 2–10 s → 通常能跟上", {
    x: 0.5, y: 6.3, w: 7.5, h: 0.3,
    fontFace: FONT_B, fontSize: 11, color: C.charcoal, margin: 0,
  });

  // right: fallback
  s.addText("跟不上时的 Fallback 链", {
    x: 8.2, y: 1.5, w: 4.8, h: 0.4,
    fontFace: FONT_H, fontSize: 15, color: C.navy, bold: true, margin: 0,
  });

  const fb = [
    ["1. 已精化", "返回 refined stage", C.green, "最优路径"],
    ["2. 未精化但 quick check 通过", "返回原 VLM 版本 + Stage A 兜底\n通知 supervisor degraded mode", C.amber, "degraded"],
    ["3. 兜底也失败", "abort 或 request supervisor", C.coral, "兜底失败"],
  ];
  fb.forEach((f, i) => {
    const y = 2.0 + i * 1.4;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 8.2, y, w: 4.8, h: 1.3,
      fill: { color: C.white }, line: { color: f[2], width: 1.5 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x: 8.2, y, w: 0.08, h: 1.3,
      fill: { color: f[2] }, line: { color: f[2], width: 0 },
    });
    s.addText(f[0], {
      x: 8.35, y: y + 0.1, w: 3.0, h: 0.35,
      fontFace: FONT_H, fontSize: 12, color: f[2], bold: true, margin: 0,
    });
    s.addText(f[3], {
      x: 11.3, y: y + 0.1, w: 1.6, h: 0.35,
      fontFace: FONT_M, fontSize: 10, color: f[2], italic: true, align: "right", margin: 0,
    });
    s.addText(f[1], {
      x: 8.35, y: y + 0.5, w: 4.6, h: 0.75,
      fontFace: FONT_B, fontSize: 10.5, color: C.charcoal, margin: 0, valign: "top",
    });
  });

  // 设计纪律 callout
  s.addShape(pres.shapes.RECTANGLE, {
    x: 8.2, y: 6.3, w: 4.8, h: 0.55,
    fill: { color: C.navy }, line: { color: C.navy, width: 0 },
  });
  s.addText("精化是 best-effort, 不是 prerequisite (D8)", {
    x: 8.2, y: 6.3, w: 4.8, h: 0.55,
    fontFace: FONT_B, fontSize: 11, color: C.cyan, bold: true, italic: true,
    align: "center", valign: "middle", margin: 0,
  });

  addFooter(s, 15, 24);
}

// =========================================================
// SLIDE 16 — Frequency band overview
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "四频段分层 · 频率 vs 权限", "D5 · Frequency-Authority inversion");

  // left: rule statement
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 1.5, w: 12.3, h: 0.8,
    fill: { color: C.navy }, line: { color: C.navy, width: 0 },
  });
  s.addText("频率高 → 权限大但视野窄；频率低 → 视野宽但权限克制", {
    x: 0.5, y: 1.5, w: 12.3, h: 0.8,
    fontFace: FONT_H, fontSize: 16, color: C.cyan, bold: true,
    align: "center", valign: "middle", italic: true, margin: 0,
  });

  // 4 bands as horizontal bars
  const bands = [
    ["L1 · VLA 反应层",    "10–30 Hz",       "改单步 action",          C.amber,  0.95],
    ["L2 · MPC 战术层",    "10–30 Hz",       "改单步动作 / 拒绝动作",   C.coral,  0.80],
    ["L2.5 · Semantic Resolver", "0.5–2 Hz", "解析 deferred refs",     C.green,  0.45],
    ["L3 · VLM-Supervisor", "event-driven", "stage / replan / abort", C.purple, 0.15],
  ];

  const bx = 0.5, by = 2.6, bh = 0.95;
  bands.forEach((b, i) => {
    const y = by + i * (bh + 0.15);
    // bar
    const barW = 12.3 * b[4];
    s.addShape(pres.shapes.RECTANGLE, {
      x: bx, y, w: barW, h: bh,
      fill: { color: b[3] }, line: { color: b[3], width: 0 },
    });
    s.addText(b[0], {
      x: bx + 0.2, y: y + 0.1, w: barW - 0.4, h: 0.4,
      fontFace: FONT_H, fontSize: 14, color: C.white, bold: true, margin: 0,
    });
    s.addText(b[2], {
      x: bx + 0.2, y: y + 0.5, w: barW - 0.4, h: 0.4,
      fontFace: FONT_B, fontSize: 11, color: C.white, margin: 0,
    });
    // frequency label outside
    s.addText(b[1], {
      x: bx + barW + 0.2, y, w: 2.0, h: bh,
      fontFace: FONT_M, fontSize: 13, color: b[3], bold: true,
      valign: "middle", margin: 0,
    });
  });

  // bottom: takeaway
  s.addText("Refiner / PointWorld 是异步后台 worker，不占任何频段——它们是 helper，不是 layer", {
    x: 0.5, y: 6.85, w: 12.3, h: 0.3,
    fontFace: FONT_B, fontSize: 11, color: C.purple, italic: true, align: "center", margin: 0,
  });

  addFooter(s, 16, 24);
}

// =========================================================
// SLIDE 17 — Progressive Constraint: idea
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "渐进约束特化 · 新设计模式", "Progressive Constraint Specialization");

  // quote
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 1.5, w: 12.3, h: 0.75,
    fill: { color: C.purple }, line: { color: C.purple, width: 0 },
  });
  s.addText("\"初始 stage 宽约束（去抓某个碗就行）→ 以已完成的碗为基石 → 逐渐收紧约束（下一个碗要和这个碗交互）\"", {
    x: 0.7, y: 1.5, w: 11.9, h: 0.75,
    fontFace: FONT_B, fontSize: 12, color: C.white, italic: true,
    align: "center", valign: "middle", margin: 0,
  });

  // crystallization metaphor
  s.addText("从「晶体」到「溶液」", {
    x: 0.5, y: 2.5, w: 12.3, h: 0.4,
    fontFace: FONT_H, fontSize: 16, color: C.navy, bold: true,
    align: "center", margin: 0,
  });

  // two columns: before / after
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 3.05, w: 6.0, h: 3.7,
    fill: { color: C.grayLt }, line: { color: C.coral, width: 2 },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 3.05, w: 6.0, h: 0.45,
    fill: { color: C.coral }, line: { color: C.coral, width: 0 },
  });
  s.addText("传统 plan（v2 当前）", {
    x: 0.65, y: 3.05, w: 5.7, h: 0.45,
    fontFace: FONT_H, fontSize: 13, color: C.white, bold: true, valign: "middle", margin: 0,
  });

  const before = [
    ["VLM 输出",          "pick(bowl_3)"],
    ["Plan-time 必须解决", "哪个碗叫 bowl_3"],
    ["Identity 错的后果", "full replan"],
    ["6 种 stack 顺序",   "× N 种 bowl 分配 → 组合爆炸"],
  ];
  before.forEach((b, i) => {
    const y = 3.6 + i * 0.7;
    s.addText(b[0], {
      x: 0.7, y, w: 2.6, h: 0.3,
      fontFace: FONT_B, fontSize: 10, color: C.gray, bold: true, margin: 0,
    });
    s.addText(b[1], {
      x: 0.7, y: y + 0.3, w: 5.6, h: 0.35,
      fontFace: FONT_M, fontSize: 12, color: C.charcoal, margin: 0,
    });
  });

  s.addShape(pres.shapes.RECTANGLE, {
    x: 6.8, y: 3.05, w: 6.0, h: 3.7,
    fill: { color: C.grayLt }, line: { color: C.green, width: 2 },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 6.8, y: 3.05, w: 6.0, h: 0.45,
    fill: { color: C.green }, line: { color: C.green, width: 0 },
  });
  s.addText("渐进约束 plan", {
    x: 6.95, y: 3.05, w: 5.7, h: 0.45,
    fontFace: FONT_H, fontSize: 13, color: C.white, bold: true, valign: "middle", margin: 0,
  });

  const after = [
    ["VLM 输出",          "pick(any bowl ∈ scene)"],
    ["Plan-time 故意不解决", "留给 runtime / blackboard"],
    ["Identity 错的后果", "不存在 (VLM 不输出 identity)"],
    ["Plan 只有 1 种",    "runtime 自然 collapse"],
  ];
  after.forEach((b, i) => {
    const y = 3.6 + i * 0.7;
    s.addText(b[0], {
      x: 7.0, y, w: 2.8, h: 0.3,
      fontFace: FONT_B, fontSize: 10, color: C.gray, bold: true, margin: 0,
    });
    s.addText(b[1], {
      x: 7.0, y: y + 0.3, w: 5.6, h: 0.35,
      fontFace: FONT_M, fontSize: 12, color: C.charcoal, margin: 0,
    });
  });

  addFooter(s, 17, 24);
}

// =========================================================
// SLIDE 18 — Progressive Constraint: example
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "渐进约束 · stack-3-bowls 实例", "Walk-through");

  // 4 stages as vertical timeline
  const stages = [
    {
      idx: 1,
      title: "pick (any reachable bowl)",
      cons:  "reachable + stackable(class=bowl)",
      after: "?picked_1 ← bowl_id_5  (commit to blackboard)",
    },
    {
      idx: 2,
      title: "place (?picked_1 on any other bowl)",
      cons:  "on_top_of(?picked_1, ?second_bowl) + stable + ?second_bowl ≠ ?picked_1",
      after: "?second_bowl ← bowl_id_2",
    },
    {
      idx: 3,
      title: "pick (any remaining bowl)",
      cons:  "reachable + not_in_stack",
      after: "?picked_3 ← bowl_id_8",
    },
    {
      idx: 4,
      title: "place (?picked_3 on top of stack)",
      cons:  "on_top_of(?picked_3, ?picked_1) + stable",
      after: "GOAL satisfied: count_stacked(bowl) ≥ 3",
    },
  ];

  stages.forEach((st, i) => {
    const y = 1.6 + i * 1.35;
    // index circle
    s.addShape(pres.shapes.OVAL, {
      x: 0.5, y: y + 0.15, w: 0.65, h: 0.65,
      fill: { color: C.purple }, line: { color: C.purple, width: 0 },
    });
    s.addText(String(st.idx), {
      x: 0.5, y: y + 0.15, w: 0.65, h: 0.65,
      fontFace: FONT_H, fontSize: 20, color: C.white, bold: true,
      align: "center", valign: "middle", margin: 0,
    });

    // line connector
    if (i < stages.length - 1) {
      s.addShape(pres.shapes.LINE, {
        x: 0.825, y: y + 0.85, w: 0, h: 0.5,
        line: { color: C.purple, width: 2 },
      });
    }

    // body
    s.addShape(pres.shapes.RECTANGLE, {
      x: 1.4, y, w: 11.4, h: 1.2,
      fill: { color: C.white }, line: { color: C.purple, width: 1 },
    });
    s.addText(st.title, {
      x: 1.55, y: y + 0.05, w: 11.1, h: 0.35,
      fontFace: FONT_M, fontSize: 13, color: C.navy, bold: true, margin: 0,
    });
    s.addText([
      { text: "constraints  ", options: { color: C.gray, bold: true, fontSize: 9 } },
      { text: st.cons, options: { color: C.charcoal, fontSize: 11, fontFace: FONT_M } },
    ], {
      x: 1.55, y: y + 0.42, w: 11.1, h: 0.35,
      fontFace: FONT_B, margin: 0,
    });
    s.addText([
      { text: "after stage  ", options: { color: C.gray, bold: true, fontSize: 9 } },
      { text: st.after, options: { color: C.green, fontSize: 11, fontFace: FONT_M, bold: true } },
    ], {
      x: 1.55, y: y + 0.8, w: 11.1, h: 0.35,
      fontFace: FONT_B, margin: 0,
    });
  });

  addFooter(s, 18, 24);
}

// =========================================================
// SLIDE 19 — Binding mode + existential predicates
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "Binding Mode 与 Existential Predicates", "Schema extension");

  // left: binding mode
  s.addText("binding_mode 字段", {
    x: 0.5, y: 1.5, w: 6, h: 0.4,
    fontFace: FONT_H, fontSize: 16, color: C.navy, bold: true, margin: 0,
  });

  const modes = [
    ["eager",  "Plan-time 绑 identity",  "task 含 identity 关键约束\n(\"红碗叠在蓝碗上\")", C.amber],
    ["lazy",   "Runtime 由 blackboard 绑", "task identity 无关\n(\"叠三个碗\")",         C.green],
  ];
  modes.forEach((m, i) => {
    const y = 2.0 + i * 2.3;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.5, y, w: 6, h: 2.1,
      fill: { color: C.white }, line: { color: m[3], width: 2 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.5, y, w: 6, h: 0.55,
      fill: { color: m[3] }, line: { color: m[3], width: 0 },
    });
    s.addText(m[0], {
      x: 0.7, y, w: 5.6, h: 0.55,
      fontFace: FONT_M, fontSize: 16, color: C.white, bold: true, valign: "middle", margin: 0,
    });
    s.addText(m[1], {
      x: 0.7, y: y + 0.7, w: 5.6, h: 0.35,
      fontFace: FONT_H, fontSize: 13, color: C.navy, bold: true, margin: 0,
    });
    s.addText(m[2], {
      x: 0.7, y: y + 1.1, w: 5.6, h: 0.95,
      fontFace: FONT_B, fontSize: 11, color: C.charcoal, italic: true, margin: 0, valign: "top",
    });
  });

  // right: existential predicates
  s.addText("Existential Predicates (新增)", {
    x: 6.8, y: 1.5, w: 6, h: 0.4,
    fontFace: FONT_H, fontSize: 16, color: C.navy, bold: true, margin: 0,
  });

  s.addText("身份无关的 goal 需要 existential 量化", {
    x: 6.8, y: 1.9, w: 6, h: 0.3,
    fontFace: FONT_B, fontSize: 11, color: C.gray, italic: true, margin: 0,
  });

  codeBlock(s,
`# 旧 (identity-based)
{"pred": "stacked",
 "args": ["bowl_1","bowl_2","bowl_3"]}

# 新 (existential)
{"pred": "count_in_state",
 "args": ["class=bowl",
          "state=stacked",
          ">=", 3]}

{"pred": "exists_with_property",
 "args": ["class=bowl",
          "props=[stable,top_of_stack]"]}

{"pred": "all_of_class_in_state",
 "args": ["class=bowl",
          "state=in_stack"]}`,
  6.8, 2.25, 6.0, 4.4, { fontSize: 10 });

  s.addText("Predicate Dictionary 的真扩展（不是 cosmetic 改动）", {
    x: 6.8, y: 6.7, w: 6, h: 0.3,
    fontFace: FONT_B, fontSize: 10, color: C.coral, italic: true, margin: 0,
  });

  addFooter(s, 19, 24);
}

// =========================================================
// SLIDE 20 — How progressive constraint fits architecture
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "渐进约束如何接入现有 v2 架构", "Three-touch extension");

  s.addText("不需要架构改动，只需要三处协同扩展", {
    x: 0.5, y: 1.45, w: 12.3, h: 0.4,
    fontFace: FONT_B, fontSize: 13, color: C.purple, italic: true, margin: 0,
  });

  const ext = [
    [
      "1. VLM-Planner schema 扩展",
      "stage.target_selector: instance:bowl_3 | any:bowl | any_except:?picked_1\nstage.commit_on_complete: 写入哪个 blackboard 变量\nstage.binding_mode: eager | lazy",
      C.navy,
    ],
    [
      "2. L2.5 Semantic Resolver 扩展",
      "在 stage 即将执行前才 resolve 该 stage 的 deferred refs\n利用最新 blackboard binding（含上一 stage 实际结果）",
      C.cyan,
    ],
    [
      "3. Streaming Refiner 扩展",
      "优先 refine binding_mode=lazy 的 stage\n这反而让 lookahead=1 的纪律更自然——lazy stages 本来就不能 lookahead=2",
      C.purple,
    ],
    [
      "4. Predicate Dictionary 扩展",
      "新增 existential predicates: count_in_state, exists_with_property, all_of_class\n这些 predicate 是 identity-agnostic 的，与渐进约束设计天然配合",
      C.green,
    ],
  ];

  ext.forEach((e, i) => {
    const y = 1.95 + i * 1.25;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.5, y, w: 12.3, h: 1.15,
      fill: { color: C.white }, line: { color: e[2], width: 1.5 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.5, y, w: 0.1, h: 1.15,
      fill: { color: e[2] }, line: { color: e[2], width: 0 },
    });
    s.addText(e[0], {
      x: 0.75, y: y + 0.12, w: 11.9, h: 0.4,
      fontFace: FONT_H, fontSize: 14, color: e[2], bold: true, margin: 0,
    });
    s.addText(e[1], {
      x: 0.75, y: y + 0.5, w: 11.9, h: 0.6,
      fontFace: FONT_M, fontSize: 11, color: C.charcoal, margin: 0, valign: "top",
    });
  });

  addFooter(s, 20, 24);
}

// =========================================================
// SLIDE 21 — Tensions & risks
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "渐进约束设计的破绽", "Tensions to resolve");

  const risks = [
    [
      "破绽 1 · 局部最优 vs 全局最优",
      "VLM 在 stage 1 选「任何能抓的碗」——但某些碗会让后续 stage 变难（如这个碗太大无法 stack）",
      "Mitigation",
      "stage 1 约束加 stackable(self) (从 class 推断)；streaming refiner 在 refine stage 1 时就预先用 PointWorld 评估后续可行性",
    ],
    [
      "破绽 2 · 约束「软化」的边界",
      "宽到什么程度？pick(any bowl) 还是 pick(any object)？过宽 VLM 失去 task intent 表达力",
      "Mitigation",
      "类型约束保持锐利，identity 约束保持宽松。pick(class=bowl, instance=any) ✓；pick(class=any) ✗",
    ],
    [
      "破绽 3 · goal predicate 必须 identity-agnostic",
      "goal: stack(bowl_1, bowl_2, bowl_3) 需重写为 existential：count_stacked(bowl) ≥ 3",
      "Mitigation",
      "Predicate Dictionary 加 existential quantifier 类（见 slide 19）— 是真新增，不是 cosmetic",
    ],
    [
      "破绽 4 · identity-sensitive 任务",
      "「把红碗叠在蓝碗上」必须 pick(color=red)，渐进约束在 identity 关键任务上自然退化",
      "Mitigation",
      "binding_mode: lazy / eager 作为 task-conditioned 选项。VLM 在 plan time 根据 task 语义自动决定",
    ],
  ];

  risks.forEach((r, i) => {
    const y = 1.5 + i * 1.4;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.5, y, w: 12.3, h: 1.3,
      fill: { color: C.grayLt }, line: { color: C.coral, width: 1 },
    });
    s.addText(r[0], {
      x: 0.7, y: y + 0.08, w: 12, h: 0.35,
      fontFace: FONT_H, fontSize: 13, color: C.coral, bold: true, margin: 0,
    });
    s.addText(r[1], {
      x: 0.7, y: y + 0.42, w: 12, h: 0.35,
      fontFace: FONT_B, fontSize: 11, color: C.charcoal, margin: 0,
    });
    s.addText([
      { text: r[2] + " · ", options: { color: C.green, bold: true } },
      { text: r[3], options: { color: C.navy } },
    ], {
      x: 0.7, y: y + 0.85, w: 12, h: 0.4,
      fontFace: FONT_B, fontSize: 11, margin: 0, valign: "top",
    });
  });

  addFooter(s, 21, 24);
}

// =========================================================
// SLIDE 22 — MVP roadmap
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "MVP 实施路径 · ~3.5 个月", "Roadmap");

  const phases = [
    ["P1", "PointWorld 集成 + Stage B/C MPC",      "4–6 周", C.navy],
    ["P2", "Critique Synthesizer v1（单 stage）",   "2 周",   C.cyan],
    ["P3", "StreamingRefiner worker + Quick Check", "2 周",   C.purple],
    ["P4", "VLM revise prompt + LoRA tune",         "2 周",   C.green],
    ["P5", "Fallback + supervisor force_refine_now", "1 周",  C.amber],
    ["P6", "端到端 benchmark (4 档 ablation)",      "3 周",   C.coral],
  ];

  // gantt-like bars
  const widths = [6, 2, 2, 2, 1, 3];  // weeks
  const total = widths.reduce((a, b) => a + b, 0);
  const scaleX = 8.0 / total;  // 8" total bar width
  let runX = 4.5;

  // header
  s.addText("Phase", { x: 0.5, y: 1.55, w: 0.8, h: 0.35, fontFace: FONT_B, fontSize: 11, color: C.gray, bold: true, margin: 0 });
  s.addText("交付", { x: 1.3, y: 1.55, w: 2.7, h: 0.35, fontFace: FONT_B, fontSize: 11, color: C.gray, bold: true, margin: 0 });
  s.addText("Duration", { x: 4.05, y: 1.55, w: 0.45, h: 0.35, fontFace: FONT_B, fontSize: 11, color: C.gray, bold: true, margin: 0 });
  s.addText("Week 1", { x: 4.5, y: 1.55, w: 1, h: 0.35, fontFace: FONT_B, fontSize: 9, color: C.gray, margin: 0 });
  s.addText("Week 16", { x: 11.5, y: 1.55, w: 1, h: 0.35, fontFace: FONT_B, fontSize: 9, color: C.gray, margin: 0 });

  phases.forEach((p, i) => {
    const y = 2.05 + i * 0.7;
    // phase chip
    s.addShape(pres.shapes.OVAL, {
      x: 0.5, y: y + 0.05, w: 0.55, h: 0.5,
      fill: { color: p[3] }, line: { color: p[3], width: 0 },
    });
    s.addText(p[0], {
      x: 0.5, y: y + 0.05, w: 0.55, h: 0.5,
      fontFace: FONT_H, fontSize: 13, color: C.white, bold: true,
      align: "center", valign: "middle", margin: 0,
    });
    s.addText(p[1], {
      x: 1.3, y: y + 0.05, w: 2.7, h: 0.5,
      fontFace: FONT_B, fontSize: 11, color: C.charcoal, valign: "middle", margin: 0,
    });
    s.addText(p[2], {
      x: 4.0, y: y + 0.05, w: 0.5, h: 0.5,
      fontFace: FONT_M, fontSize: 10, color: p[3], bold: true,
      align: "right", valign: "middle", margin: 0,
    });

    // gantt bar
    const startWeek = (i === 0) ? 0 : widths.slice(0, i).reduce((a, b) => a + b, 0);
    const barX = 4.5 + startWeek * scaleX;
    const barW = widths[i] * scaleX;
    s.addShape(pres.shapes.RECTANGLE, {
      x: barX, y: y + 0.18, w: barW, h: 0.25,
      fill: { color: p[3] }, line: { color: p[3], width: 0 },
    });
  });

  // critical path callout
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 6.5, w: 12.3, h: 0.55,
    fill: { color: C.navy }, line: { color: C.navy, width: 0 },
  });
  s.addText([
    { text: "Critical path  ", options: { fontFace: FONT_H, fontSize: 12, color: C.cyan, bold: true } },
    { text: "P1 → P3 (refiner 必须先在 mock VLM 上跑通，验证 lookahead 维持率)", options: { fontFace: FONT_B, fontSize: 12, color: C.white } },
  ], {
    x: 0.5, y: 6.5, w: 12.3, h: 0.55, valign: "middle", align: "center", margin: 0,
  });

  addFooter(s, 22, 24);
}

// =========================================================
// SLIDE 23 — Paper claims + ablation
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.white };
  addTitleBar(s, "论文 Claim 与 Ablation 设计", "What we'll measure");

  // P1/P2/P3 claims
  const claims = [
    ["P1", "Predicate Dictionary 作为 narrow waist",
     "VLM 训练 / MPC 实现 / Supervisor 判断三者共用同一份字典，预测 sim 上 task SR ↑",
     C.navy],
    ["P2", "Streaming Refinement vs batch pre-execution",
     "Startup latency ≤ 2 s (vs ~30 s)，refinement-keeps-up rate > X% on tasks with avg stage > 3 s",
     C.purple],
    ["P3", "Hybrid MPC A/B/C 的 lazy evaluation",
     "Stage A always-on + B/C on-demand：mean per-step latency < 20 ms while contact-rich SR retained",
     C.coral],
  ];

  claims.forEach((c, i) => {
    const x = 0.5 + i * 4.27;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.5, w: 4.07, h: 2.5,
      fill: { color: C.white }, line: { color: c[3], width: 2 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.5, w: 4.07, h: 0.85,
      fill: { color: c[3] }, line: { color: c[3], width: 0 },
    });
    s.addText(c[0], {
      x: x + 0.2, y: 1.55, w: 1, h: 0.75,
      fontFace: FONT_H, fontSize: 28, color: C.white, bold: true,
      valign: "middle", margin: 0,
    });
    s.addText(c[1], {
      x: x + 1.3, y: 1.55, w: 2.6, h: 0.75,
      fontFace: FONT_H, fontSize: 12, color: C.white, bold: true,
      valign: "middle", margin: 0,
    });
    s.addText(c[2], {
      x: x + 0.2, y: 2.5, w: 3.7, h: 1.45,
      fontFace: FONT_B, fontSize: 11, color: C.charcoal, margin: 0, valign: "top",
    });
  });

  // ablation
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 4.3, w: 12.3, h: 2.6,
    fill: { color: C.grayLt }, line: { color: C.navy, width: 2 },
  });
  s.addText("Ablation 4 档（P2 重点）", {
    x: 0.7, y: 4.4, w: 12, h: 0.35,
    fontFace: FONT_H, fontSize: 14, color: C.navy, bold: true, margin: 0,
  });

  const abl = [
    ["A", "Streaming refinement (proposed)", "lookahead=2", C.green],
    ["B", "Pre-execution batch refinement",  "~30s startup", C.amber],
    ["C", "No refinement",                    "Stage A only", C.coral],
    ["D", "L3 supervisor only",                "event-driven", C.purple],
  ];

  abl.forEach((a, i) => {
    const x = 0.7 + i * 3.05;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 4.95, w: 2.85, h: 1.85,
      fill: { color: C.white }, line: { color: a[3], width: 1.5 },
    });
    s.addText(a[0], {
      x: x + 0.15, y: 5.05, w: 0.55, h: 0.5,
      fontFace: FONT_H, fontSize: 22, color: a[3], bold: true, margin: 0,
    });
    s.addText(a[1], {
      x: x + 0.15, y: 5.55, w: 2.55, h: 0.9,
      fontFace: FONT_B, fontSize: 11, color: C.charcoal, margin: 0, valign: "top",
    });
    s.addText(a[2], {
      x: x + 0.15, y: 6.4, w: 2.55, h: 0.35,
      fontFace: FONT_M, fontSize: 10, color: a[3], italic: true, margin: 0,
    });
  });

  addFooter(s, 23, 24);
}

// =========================================================
// SLIDE 24 — Summary / Next
// =========================================================
{
  let s = pres.addSlide();
  s.background = { color: C.navyDk };

  // accent
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 0.35, h: H,
    fill: { color: C.cyan }, line: { color: C.cyan, width: 0 },
  });

  s.addText("总结 与 下一步", {
    x: 0.8, y: 0.5, w: 12, h: 0.55,
    fontFace: FONT_B, fontSize: 13, color: C.cyan, bold: true, charSpacing: 4, margin: 0,
  });
  s.addText("Where we are · Where to go", {
    x: 0.8, y: 0.9, w: 12, h: 0.7,
    fontFace: FONT_H, fontSize: 32, color: C.white, bold: true, margin: 0,
  });

  // 3 columns
  const cols = [
    {
      title: "Where we are",
      bullets: [
        "v2 五层架构 (+ supervisor 旁路)",
        "Predicate Dictionary 窄腰",
        "Hybrid MPC A/B/C",
        "Streaming Refinement (D6–D8 纪律)",
        "渐进约束特化 (新设计模式)",
      ],
      c: C.cyan,
    },
    {
      title: "What's open",
      bullets: [
        "Q22 短 stage 处理策略",
        "Q23 Refiner OOM 时优先级",
        "Q24 force_refine_now preempt vs queue",
        "Q25 binding_mode 自动判定",
        "Existential predicate 选型",
      ],
      c: C.amber,
    },
    {
      title: "Next decision",
      bullets: [
        "决定 binding_mode 由 task-level 配置 or VLM 推理",
        "draft 三个 task plan (stack / pot / red-blue) 看 binding_mode 边界",
        "列 existential predicate 完整集",
        "决定是否把渐进约束写入 v2 §11.7",
      ],
      c: C.green,
    },
  ];

  cols.forEach((c, i) => {
    const x = 0.8 + i * 4.13;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.95, w: 3.9, h: 4.8,
      fill: { color: C.navy }, line: { color: c.c, width: 1.5 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.95, w: 3.9, h: 0.5,
      fill: { color: c.c }, line: { color: c.c, width: 0 },
    });
    s.addText(c.title, {
      x: x + 0.2, y: 1.95, w: 3.5, h: 0.5,
      fontFace: FONT_H, fontSize: 14, color: C.navyDk, bold: true,
      valign: "middle", margin: 0,
    });

    const bullets = c.bullets.map((b, idx) => ({
      text: b,
      options: {
        fontFace: FONT_B, fontSize: 11, color: C.white,
        bullet: { code: "25CF" }, breakLine: idx < c.bullets.length - 1,
        paraSpaceAfter: 8,
      },
    }));
    s.addText(bullets, {
      x: x + 0.2, y: 2.65, w: 3.5, h: 4.0, margin: 0, valign: "top",
    });
  });

  // bottom
  s.addText("文档 vlm_vla_mpc_robot_framework_outline_v2.md · 图 framework_v2_main_figure.svg · 仓库 WANGGUIQIN/robobrain-3dgs-v2", {
    x: 0.8, y: 6.95, w: 12, h: 0.4,
    fontFace: FONT_M, fontSize: 10, color: C.ice, italic: true, margin: 0,
  });
}

// =========================================================
// write file
// =========================================================
pres.writeFile({ fileName: "framework_v2_deck.pptx" }).then(fn => {
  console.log("Wrote:", fn);
});
