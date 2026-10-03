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

.xm-home, .xm-page { max-width: 1280px; margin: 0 auto; color: var(--xm-ink); }
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
  background:var(--xm-surface); padding:10px 16px; border-bottom:var(--xm-border-w) solid var(--xm-hairline); }
.xm-table td { font-size:14px; color:var(--xm-ink); padding:14px 20px;
  border-bottom:1px solid var(--xm-hairline-soft); vertical-align:top; }
.xm-table tr:last-child td { border-bottom:none; }
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

/* ═══ 设置页 ════════════════════════════════════════════════════════ */
.st-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(238px, 1fr));
  gap: var(--xm-space-md); margin: var(--xm-space-sm) 0 var(--xm-space-lg); }
.st-card { position:relative; background:var(--xm-canvas); border: var(--xm-border-w) solid var(--xm-card-border);
  border-radius:var(--xm-radius-lg); padding:14px 16px 16px; box-shadow: var(--xm-card-shadow); }
.st-card.is-active { border-color: var(--xm-primary); }
.st-card-h { display:flex; align-items:center; gap:8px; margin-bottom:2px; }
.st-card-name { font-size:15px; font-weight:600; color:var(--xm-ink); }
.st-card-tag { font-size:12px; font-weight:600; color:var(--xm-steel);
  background:var(--xm-surface-soft); border-radius:var(--xm-radius-full); padding:2px 8px; }
.st-card-desc { font-size:13px; color:var(--xm-slate); line-height:1.7; margin:6px 0 10px; min-height:44px; }
.st-card-src { font-size:12px; color:var(--xm-steel); line-height:1.6; }
.st-swatches { display:flex; gap:6px; margin:10px 0 8px; }
.st-swatch { width:26px; height:26px; border-radius:var(--xm-radius-sm);
  border:1px solid var(--xm-hairline-strong); }
.st-cur { position:absolute; top:12px; right:12px; font-size:12px; font-weight:600;
  color:var(--xm-on-primary); background:var(--xm-primary);
  border-radius:var(--xm-radius-full); padding:3px 9px; }
.st-kv { display:flex; flex-wrap:wrap; gap: var(--xm-space-xl); margin-top:4px; }
.st-kv-item { display:flex; flex-direction:column; gap:2px; min-width:150px; }
.st-kv-k { font-size:12px; color:var(--xm-steel); }
.st-kv-v { font-size:15px; font-weight:600; color:var(--xm-ink); }

/* ═══ 兼容旧内联样式的硬编码色（Tab1 完整迁移见 ARD T-UI-01）═════════ */
h3 { color: var(--xm-ink) !important; }
.dn-risk-panel { background: var(--xm-canvas) !important;
  border-color: var(--xm-hairline) !important; border-left-color: var(--xm-warning) !important; }
.dn-risk-head { color: var(--xm-ink) !important; }
.dn-risk-sub { color: var(--xm-slate) !important; }
.risk-note { background: var(--xm-warning-soft) !important;
  border-left-color: var(--xm-warning) !important; color: var(--xm-charcoal) !important; }

/* ═══ 响应式 ════════════════════════════════════════════════════════ */
@media (max-width: 1023px) { .xm-home, .xm-page { max-width:100%; } }
@media (max-width: 767px) {
  .xm-h1 { font-size:24px; }
  .xm-table { display:block; overflow-x:auto; }
}
"""

# 兼容旧引用：组件 + 间距（不含颜色，颜色一律来自 themes）
THEME_CSS = SPACING_CSS + COMPONENT_CSS


def css_for(theme_id=None, *page_css: str) -> str:
    """组装完整样式表：主题变量（可换） + 间距 + 组件 + 各页面自有样式。"""
    return themes.theme_css(theme_id) + THEME_CSS + "".join(page_css or ())
