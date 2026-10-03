# -*- coding: utf-8 -*-
"""小满 UI Design System v2 —— 组件类与间距 token 的唯一来源。

分工：
  · 颜色 / 字体 / 圆角 / 描边强度 / 阴影  →  `core/themes.py`（主题系统，含移植自 CodeForge 的 5 套主题）
  · 组件类（.xm-*）与间距（--xm-space-*）  →  本文件
页面只允许消费 `--xm-*` 变量与 `.xm-*` 类，禁止写死颜色（见 CLAUDE.md UI 铁律）。

本次新增：应用外壳从"顶部 Tab"改为"左侧边栏导航"，导航配色由主题的
`--xm-sidebar-*` 一组 token 驱动（对应 CodeForge 的 --nav-bg / --nav-act）。
"""

from . import themes

# ── 间距 token：结构性，不随主题变化 ───────────────────────────────────
SPACING_CSS = """
:root {
  --xm-space-xxs:4px; --xm-space-xs:8px; --xm-space-sm:12px; --xm-space-md:16px;
  --xm-space-lg:20px; --xm-space-xl:24px; --xm-space-xxl:32px; --xm-space-xxxl:40px;
}
"""

# ── 组件类 ────────────────────────────────────────────────────────────
COMPONENT_CSS = """
/* ═══ 应用外壳 ═══════════════════════════════════════════════════════ */
html, body { background: var(--xm-shell-bg); }
.gradio-container { background: var(--xm-shell-bg) !important; }
body, .gradio-container, button, input, textarea, select,
.xm-home, .xm-page { font-family: var(--xm-font) !important; }

.xm-home, .xm-page { max-width: none; margin: 0; color: var(--xm-ink); }
.xm-h1 { font-size:28px; font-weight:600; line-height:1.25; color:var(--xm-ink); margin:0; }
.xm-h2 { font-size:22px; font-weight:600; line-height:1.30; color:var(--xm-ink); margin:0; }
.xm-h3 { font-size:18px; font-weight:600; line-height:1.40; color:var(--xm-ink); margin:0; }
.xm-body { font-size:16px; line-height:1.55; color:var(--xm-charcoal); }
.xm-sm { font-size:14px; line-height:1.50; color:var(--xm-slate); }
.xm-cap { font-size:12px; line-height:1.40; color:var(--xm-steel); }
.xm-sec { margin-top:14px; }
.xm-flow { gap:6px !important; }
.xm-flow > .block, .xm-flow > .form { margin-bottom:0 !important; }
.xm-sec-title { font-size:18px; font-weight:600; color:var(--xm-ink); margin:0 0 10px;
  padding-bottom:8px; border-bottom:var(--xm-border-w) solid var(--xm-hairline-soft); }
.xm-hint { font-size:13px; color:var(--xm-slate); margin:-4px 0 10px; }
.xm-brief { display:flex; gap:10px; align-items:flex-start; padding:10px 14px; background:var(--xm-canvas);
  border:var(--xm-border-w) solid var(--xm-hairline); border-radius:var(--xm-radius-md); margin-bottom:6px; }
.xm-brief .xm-badge { flex:0 0 auto; }
.xm-brief-t { font-size:15px; font-weight:600; color:var(--xm-ink); }
.xm-brief-sub { font-size:13px; color:var(--xm-slate); margin-top:1px; }

/* ═══ 左侧边栏导航 ══════════════════════════════════════════════════
   Gradio 6 的 gr.Tabs 会把放不下的标签折叠成「More tabs」下拉，所以不再改造它的横排导航：
     ① 隐藏 gr.Tabs 自带的 .tab-wrapper（导航条），只保留内容面板；
     ② 左侧栏里的 gr.Radio#xm-nav 做真正的导航，选中 → gr.Tabs(selected=…)。
   既拿到完全可控的竖排菜单，又保留 gr.Tabs 的面板切换能力（含跨页跳转绑定）。 */
#main-nav > .tab-wrapper { display:none !important; }
#main-nav.tabs { display:block !important; }
#main-nav > .tabitem { padding:0 !important; border:none !important; background:transparent !important; }

/* 外壳：左栏 236px + 右栏自适应 */
#xm-shell { align-items:flex-start !important; gap: var(--xm-space-xl) !important; }
#xm-side { flex:0 0 236px; max-width:236px; position:sticky; top:8px; gap:6px !important;
  background: var(--xm-sidebar-bg);
  border: var(--xm-border-w) solid var(--xm-sidebar-border);
  border-radius: var(--xm-radius-lg);
  box-shadow: var(--xm-card-shadow); padding:12px 10px; }
#xm-main { min-width:0 !important; }
.xm-side-brand { padding:0 6px 10px; margin-bottom:6px;
  border-bottom:1px solid var(--xm-sidebar-border); }
.xm-side-name { font-size:15px; font-weight:600; color:var(--xm-sidebar-fg); }
.xm-side-sub { font-size:12px; color:var(--xm-sidebar-muted); margin-top:3px; }

/* 竖排导航（Radio 外观改造成菜单） */
#xm-nav .wrap { flex-direction:column !important; gap:2px !important; width:100%; }
#xm-nav label { display:flex !important; align-items:center; width:100% !important;
  height:38px !important; min-height:38px !important; padding:0 12px !important;
  margin:0 !important; border:none !important; background:transparent !important;
  border-radius:var(--xm-radius-md) !important; cursor:pointer;
  color: var(--xm-sidebar-muted) !important; font-size:14px !important; font-weight:500 !important; }
#xm-nav label:hover { background: var(--xm-sidebar-active-bg) !important;
  color: var(--xm-sidebar-fg) !important; }
#xm-nav label.selected, #xm-nav label:has(input:checked) {
  background: var(--xm-sidebar-active-bg) !important;
  color: var(--xm-sidebar-active-fg) !important; font-weight:600 !important; }
#xm-nav input { display:none !important; }
#xm-nav span { color: inherit !important; font-size:14px !important; }

/* 分组小标题与「设置」沉底：NAV_CHOICES 顺序固定，用 nth-of-type 对位（纯 CSS，无第二份控件） */
#xm-side { display:flex; flex-direction:column; height:calc(100vh - 32px); }
#xm-nav { display:flex; flex-direction:column; flex:1 1 auto; border:0 !important; margin:0 !important;
  padding:0 !important; min-width:0 !important; }
#xm-nav .wrap { flex:1 1 auto; }
#xm-nav .wrap > label { position:relative; }
#xm-nav .wrap > label:nth-of-type(1) { margin-top:20px !important; }
#xm-nav .wrap > label:nth-of-type(4) { margin-top:24px !important; }
#xm-nav .wrap > label:nth-of-type(7) { margin-top:24px !important; }
#xm-nav .wrap > label:nth-of-type(1)::before { content:"经营"; }
#xm-nav .wrap > label:nth-of-type(4)::before { content:"复盘"; }
#xm-nav .wrap > label:nth-of-type(7)::before { content:"说明"; }
#xm-nav .wrap > label:nth-of-type(1)::before, #xm-nav .wrap > label:nth-of-type(4)::before,
#xm-nav .wrap > label:nth-of-type(7)::before { position:absolute; top:-16px; left:12px; font-size:11px;
  font-weight:600; letter-spacing:.08em; color:var(--xm-sidebar-muted); opacity:.8; }
#xm-nav .wrap > label:nth-of-type(8) { margin-top:auto !important;
  border-top:1px solid var(--xm-sidebar-border) !important; border-radius:0 !important; }
#xm-nav .wrap > label:nth-of-type(8)::before { content:"系统 + 设置"; position:absolute; top:-16px; left:12px;
  font-size:11px; font-weight:600; letter-spacing:.08em; color:var(--xm-sidebar-muted); opacity:.8; }
@media (max-width: 900px), (max-height: 760px) { #xm-side { height:auto; } }

@media (max-width: 900px) {
  #xm-shell { flex-direction:column !important; }
  #xm-side { position:static; flex:none; max-width:none; width:100%; }
  #xm-nav .wrap { flex-direction:row !important; flex-wrap:wrap; }
  #xm-nav label { width:auto !important; }
}

/* ═══ 按钮（统一 40px 高，md 圆角；矩形非胶囊）═══════════════════════ */
.xm-btn { display:inline-flex; align-items:center; gap:6px; height:40px; padding:0 18px;
  font-size:14px; font-weight:500; border-radius:var(--xm-radius-md); cursor:pointer;
  border:1px solid transparent; background:transparent; color:var(--xm-ink); }
.xm-btn-primary { background:var(--xm-primary); color:var(--xm-on-primary); }
.xm-btn-primary:hover { background:var(--xm-primary-pressed); }
.xm-btn-secondary { background:transparent; color:var(--xm-ink); border:1px solid var(--xm-hairline-strong); }
.xm-btn-ghost { background:transparent; color:var(--xm-ink); height:34px; padding:0 12px; border-radius:var(--xm-radius-sm); }
.xm-btn-link { color:var(--xm-link); padding:0; height:auto; font-size:14px; font-weight:500; }
.xm-btn:disabled { background:var(--xm-hairline); color:var(--xm-muted); }

/* ═══ 输入（统一 44px 高，聚焦 2px primary）═══════════════════════════ */
input.xm-input, textarea.xm-input { background:var(--xm-canvas) !important; color:var(--xm-ink) !important;
  border:1px solid var(--xm-hairline-strong) !important; border-radius:var(--xm-radius-md) !important;
  min-height:44px !important; font-size:15px !important; }
input.xm-input:focus, textarea.xm-input:focus { border:2px solid var(--xm-primary) !important; outline:none !important; }

/* ═══ 行内布局 / 提示块（v2 取代旧的 dn-row 与 note/good）══════════════ */
.xm-row { --layout-gap: var(--xm-space-lg) !important; gap: var(--xm-space-lg) !important; }
.xm-callout { background: var(--xm-warning-soft); border-left: 4px solid var(--xm-warning);
  padding: 14px 18px; border-radius: var(--xm-radius-md); font-size: 14px;
  color: var(--xm-charcoal); line-height: 1.85; }
.xm-callout-ok { background: var(--xm-success-soft); border-left-color: var(--xm-success); }
.xm-callout-info { background: var(--xm-info-soft); border-left-color: var(--xm-primary); }
.xm-callout b { color: var(--xm-ink); }

/* ═══ 卡片（边框与阴影强度由主题决定）═════════════════════════════════ */
.xm-card { background:var(--xm-canvas); border: var(--xm-border-w) solid var(--xm-card-border);
  border-radius:var(--xm-radius-lg); padding:var(--xm-space-lg); margin-bottom:var(--xm-space-md);
  box-shadow: var(--xm-card-shadow); }
.xm-card-tint { background:var(--xm-surface); }

/* ═══ 徽标（胶囊：full 圆角、13px/600）═══════════════════════════════ */
.xm-badge { display:inline-block; font-size:13px; font-weight:600; line-height:1;
  padding:4px 10px; border-radius:var(--xm-radius-full); }
.xm-badge-green { background:var(--xm-success-soft); color:var(--xm-success); }
.xm-badge-orange { background:var(--xm-warning-soft); color:var(--xm-warning); }
.xm-badge-red { background:var(--xm-error-soft); color:var(--xm-error); }
.xm-badge-neutral { background:var(--xm-surface-soft); color:var(--xm-steel); }

/* ═══ 数据表 ════════════════════════════════════════════════════════ */
.xm-table { width:100%; border-collapse:collapse; background:var(--xm-canvas);
  border: var(--xm-border-w) solid var(--xm-card-border); border-radius:var(--xm-radius-md); overflow:hidden; }
.xm-table th { text-align:left; font-size:13px; font-weight:600; color:var(--xm-steel);
  background:var(--xm-surface); padding:8px 12px; border-bottom:var(--xm-border-w) solid var(--xm-hairline);
  white-space:nowrap; }
.xm-table td { font-size:14px; color:var(--xm-ink); padding:10px 14px;
  border-bottom:1px solid var(--xm-hairline-soft); vertical-align:middle; }
.xm-table tr:last-child td { border-bottom:none; }
.xm-table tbody tr:hover { background:var(--xm-surface-soft); }
.xm-table th.xm-num, .xm-table td.xm-num { text-align:right; font-variant-numeric:tabular-nums; }
.xm-table td.xm-num { white-space:nowrap; }
.xm-table th { position:sticky; top:0; z-index:1; }
/* 中文逐字竖排是最丑的排版事故：短文本与数字一律不换行（T-UI-12） */
.xm-nowrap { white-space:nowrap; }
.xm-table .xm-badge { white-space:nowrap; }
.xm-acc summary, .xm-fold > summary .xm-fold-meta { white-space:nowrap; }
.xm-badge { white-space:nowrap; }
.xm-name { font-size:15px; font-weight:600; color:var(--xm-ink); }
.xm-num { font-size:16px; font-weight:600; color:var(--xm-ink); }
.xm-amount { font-size:30px; font-weight:600; color:var(--xm-ink); margin:6px 0; }
.xm-dim { color:var(--xm-slate); }

/* ═══ 折叠与链接 ════════════════════════════════════════════════════ */
.xm-acc summary { font-size:16px; font-weight:500; color:var(--xm-ink); cursor:pointer; list-style:none; }
.xm-acc summary::-webkit-details-marker { display:none; }
.xm-link { color:var(--xm-link); text-decoration:none; }
.xm-note { font-size:14px; color:var(--xm-slate); line-height:1.7; }

/* 只用于承载 <style> 的隐藏容器（样式仍生效，不占版面） */
.xm-hidden { display:none !important; height:0 !important; padding:0 !important; margin:0 !important; }

/* ═══ 通用键值行 / 轻量条形 / 徽标行（设置页、实验页、仿真指标共用）═════ */
.xm-kv-row { display:flex; flex-wrap:wrap; gap: var(--xm-space-xl); }
.xm-kv { display:flex; flex-direction:column; gap:2px; min-width:150px; }
.xm-kv-k { font-size:12px; color: var(--xm-steel); }
.xm-kv-v { font-size:20px; font-weight:600; color: var(--xm-ink); }
.xm-kv-sub { font-size:12px; color: var(--xm-steel); margin-top:2px; }
.xm-bar-row { display:flex; align-items:center; gap: var(--xm-space-md); margin:6px 0; }
.xm-bar-label { flex:0 0 150px; font-size:13px; color: var(--xm-slate); }
.xm-bar-track { flex:1; height:20px; background: var(--xm-surface);
  border-radius: var(--xm-radius-xs); overflow:hidden; }
.xm-bar-fill { height:20px; background: var(--xm-primary); border-radius: var(--xm-radius-xs); }
.xm-bar-val { flex:0 0 76px; text-align:right; font-size:13px; font-weight:600; color: var(--xm-ink); }
.xm-chips { display:flex; flex-wrap:wrap; gap:8px; margin: var(--xm-space-sm) 0 4px; }

/* ═══ 页面头部 / 工具条（标题左、操作右）══════════════════════════ */
.xm-page-head { display:flex; align-items:flex-end; justify-content:space-between; gap:var(--xm-space-lg);
  flex-wrap:wrap; margin-bottom:var(--xm-space-lg); }
.xm-page-sub { font-size:13px; color:var(--xm-slate); margin-top:4px; }
.xm-head-actions { display:flex; align-items:center; gap:var(--xm-space-sm); }
.xm-toolbar { display:flex; align-items:center; justify-content:space-between; gap:var(--xm-space-md);
  flex-wrap:wrap; margin-bottom:var(--xm-space-sm); }
.xm-toolbar-actions { display:flex; align-items:center; gap:var(--xm-space-xs); }
.xm-sec-head { display:flex; align-items:baseline; justify-content:space-between; gap:10px; }

/* ═══ Gradio 原生控件外观对齐（去掉默认灰块与彩色标签胶囊）═══════════ */
/* 输入类控件保留自己的边框与底色（block 背景被透明化后需要显式给回来） */
html:root .gradio-container input[type="text"], html:root .gradio-container input[type="number"],
html:root .gradio-container textarea {
  background: var(--xm-canvas) !important; border: 1px solid var(--xm-hairline-strong) !important;
  border-radius: var(--xm-radius-md) !important; padding: 8px 12px !important;
  font-size: 14px !important; color: var(--xm-ink) !important; }
/* 下拉框 / 数字框外层也去掉灰底 */
html:root .gradio-container .wrap-inner, html:root .gradio-container .secondary-wrap,
html:root .gradio-container .input-container { background: transparent !important; border: 0 !important; }
.gradio-container .block > label > span, .gradio-container span[data-testid="block-info"] {
  background: transparent !important; color: var(--xm-slate) !important; font-size: 13px !important;
  font-weight: 500 !important; padding: 0 0 4px !important; border: 0 !important; }
.gradio-container .form, .gradio-container .panel, .gradio-container .styler,
.gradio-container .gr-group:not(.xm-card) { background: transparent !important; border: 0 !important;
  box-shadow: none !important; padding: 0 !important; }

/* ═══ KPI 条（首屏 3~5 张；数值用等宽数字对齐）═════════════════════ */
.xm-kpi-row { display:grid; grid-template-columns:repeat(auto-fit, minmax(190px, 1fr));
  gap:var(--xm-space-md); margin-bottom:var(--xm-space-lg); }
.xm-kpi { background:var(--xm-canvas); border:var(--xm-border-w) solid var(--xm-card-border);
  border-radius:var(--xm-radius-lg); padding:16px 18px; box-shadow:var(--xm-card-shadow); }
.xm-kpi-k { font-size:12px; color:var(--xm-steel); }
.xm-kpi-v { font-size:28px; font-weight:600; line-height:1.2; color:var(--xm-ink); margin-top:6px;
  font-variant-numeric:tabular-nums; }
.xm-kpi-v-sm { font-size:20px; }
.xm-kpi-sub { font-size:12px; color:var(--xm-slate); margin-top:6px; line-height:1.5; }
.xm-kpi-delta { display:inline-block; font-size:12px; font-weight:600; border-radius:var(--xm-radius-full);
  padding:2px 8px; margin-top:6px; }
.xm-kpi-delta-up { background:var(--xm-success-soft); color:var(--xm-success); }
.xm-kpi-delta-down { background:var(--xm-error-soft); color:var(--xm-error); }
.xm-kpi-delta-flat { background:var(--xm-surface-soft); color:var(--xm-steel); }

/* ═══ 工作台分栏：主区 2fr + 侧栏 1fr（窄屏自动堆叠）════════════════ */
.xm-split { display:grid !important; grid-template-columns:minmax(0, 2fr) minmax(300px, 1fr);
  gap:var(--xm-space-lg); align-items:start; }
.xm-main-col > *:last-child, .xm-rail > *:last-child { margin-bottom:0 !important; }
.xm-risk-checks, .xm-risk-checks > .gr-group, .xm-risk-checks .gr-group {
  display:grid !important; grid-template-columns:1fr; gap:6px;
  align-items:start; min-width:0; }
.xm-risk-checks label span, .xm-risk-checks label { white-space:normal; font-size:13px !important; }

/* ═══ 折叠区（长表格默认收起，避免一屏几千像素）════════════════════ */
.xm-fold { border:var(--xm-border-w) solid var(--xm-card-border); border-radius:var(--xm-radius-lg);
  background:var(--xm-canvas); box-shadow:var(--xm-card-shadow); margin-bottom:var(--xm-space-md); overflow:hidden; }
.xm-fold > summary { list-style:none; cursor:pointer; padding:14px 18px; font-size:15px; font-weight:600;
  color:var(--xm-ink); display:flex; align-items:center; justify-content:space-between; gap:10px; }
.xm-fold > summary::-webkit-details-marker { display:none; }
.xm-fold > summary::after { content:"展开"; font-size:12px; font-weight:500; color:var(--xm-primary); }
.xm-fold[open] > summary::after { content:"收起"; }
.xm-fold > summary .xm-fold-meta { font-size:12px; font-weight:400; color:var(--xm-steel); }
.xm-fold-body { padding:0 18px 16px; }
.xm-fold-body .xm-table { margin-top:2px; }

/* ═══ 响应式 ════════════════════════════════════════════════════════ */
@media (max-width: 1280px) {
  /* 中等屏：分栏会让表格挤成窄列 → 改为上下排，侧栏两块并排 */
  .xm-split { grid-template-columns:minmax(0, 1fr); }
  .xm-rail { display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr));
    gap:var(--xm-space-lg); align-items:start; }
}
@media (max-width: 1023px) { .xm-kpi-row { grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); } }
@media (max-width: 767px) {
  .xm-h1 { font-size:24px; }
  .xm-kpi-v { font-size:24px; }
  .xm-table { display:block; overflow-x:auto; }
  .xm-page-head { align-items:flex-start; }
}
"""

# 兼容旧引用：组件 + 间距（不含颜色，颜色一律来自 themes）
THEME_CSS = SPACING_CSS + COMPONENT_CSS


def css_for(theme_id=None, *page_css: str) -> str:
    """组装完整样式表：主题变量（可换） + 间距 + 组件 + 各页面自有样式。"""
    return themes.theme_css(theme_id) + THEME_CSS + "".join(page_css or ())
