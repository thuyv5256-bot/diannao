# -*- coding: utf-8 -*-
"""小满 UI Design System v2 —— 唯一 design tokens 与组件类来源。

视觉组件体系来自 VoltAgent/awesome-design-md · notion/DESIGN.md（Notion 产品级视觉语言），
信息架构与业务语义属于小满。所有页面统一引用本模块的 class 与 CSS 变量。
"""

THEME_CSS = """
:root {
  --xm-canvas:#ffffff; --xm-surface:#f6f5f4; --xm-surface-soft:#fafaf9;
  --xm-hairline:#e5e3df; --xm-hairline-soft:#ede9e4; --xm-hairline-strong:#c8c4be;
  --xm-ink:#1a1a1a; --xm-charcoal:#37352f; --xm-slate:#5d5b54;
  --xm-steel:#787671; --xm-stone:#a4a097; --xm-muted:#bbb8b1;
  --xm-primary:#5645d4; --xm-primary-pressed:#4534b3; --xm-on-primary:#ffffff;
  --xm-link:#0075de;
  --xm-success:#1aae39; --xm-warning:#dd5b00; --xm-error:#e03131;
  --xm-success-soft:#d9f3e1; --xm-warning-soft:#ffe8d4; --xm-error-soft:#fde0ec; --xm-info-soft:#dcecfa;
  --xm-radius-xs:4px; --xm-radius-sm:6px; --xm-radius-md:8px; --xm-radius-lg:12px; --xm-radius-full:9999px;
  --xm-space-xxs:4px; --xm-space-xs:8px; --xm-space-sm:12px; --xm-space-md:16px;
  --xm-space-lg:20px; --xm-space-xl:24px; --xm-space-xxl:32px; --xm-space-xxxl:40px;
  --xm-font: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
             "Microsoft YaHei", "Noto Sans SC", system-ui, sans-serif;
}

/* 画布与内容容器 */
.gradio-container { background: var(--xm-canvas) !important; }
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
  padding-bottom:8px; border-bottom:1px solid var(--xm-hairline-soft); }
.xm-hint { font-size:13px; color:var(--xm-slate); margin:-4px 0 10px; }
.xm-brief { display:flex; gap:10px; align-items:flex-start; padding:10px 14px; background:var(--xm-canvas);
  border:1px solid var(--xm-hairline); border-radius:var(--xm-radius-md); margin-bottom:6px; }
.xm-brief .xm-badge { flex:0 0 auto; }
.xm-brief-t { font-size:15px; font-weight:600; color:var(--xm-ink); }
.xm-brief-sub { font-size:13px; color:var(--xm-slate); margin-top:1px; }

/* 按钮（统一 40px 高，md 圆角；矩形非胶囊） */
.xm-btn { display:inline-flex; align-items:center; gap:6px; height:40px; padding:0 18px;
  font-size:14px; font-weight:500; border-radius:var(--xm-radius-md); cursor:pointer;
  border:1px solid transparent; background:transparent; color:var(--xm-ink); }
.xm-btn-primary { background:var(--xm-primary); color:var(--xm-on-primary); }
.xm-btn-primary:hover { background:var(--xm-primary-pressed); }
.xm-btn-secondary { background:transparent; color:var(--xm-ink); border:1px solid var(--xm-hairline-strong); }
.xm-btn-ghost { background:transparent; color:var(--xm-ink); height:34px; padding:0 12px; border-radius:var(--xm-radius-sm); }
.xm-btn-link { color:var(--xm-link); padding:0; height:auto; font-size:14px; font-weight:500; }
.xm-btn:disabled { background:var(--xm-hairline); color:var(--xm-muted); }

/* 输入（统一 44px 高，聚焦 2px primary） */
input.xm-input, textarea.xm-input { background:var(--xm-canvas) !important; color:var(--xm-ink) !important;
  border:1px solid var(--xm-hairline-strong) !important; border-radius:var(--xm-radius-md) !important;
  min-height:44px !important; font-size:15px !important; }
input.xm-input:focus, textarea.xm-input:focus { border:2px solid var(--xm-primary) !important; outline:none !important; }

/* 卡片（无阴影，hairline 边框，lg 圆角） */
.xm-card { background:var(--xm-canvas); border:1px solid var(--xm-hairline);
  border-radius:var(--xm-radius-lg); padding:var(--xm-space-lg); margin-bottom:var(--xm-space-md); }
.xm-card-tint { background:var(--xm-surface); }

/* 徽标（胶囊：full 圆角、13px/600） */
.xm-badge { display:inline-block; font-size:13px; font-weight:600; line-height:1;
  padding:4px 10px; border-radius:var(--xm-radius-full); }
.xm-badge-green { background:var(--xm-success-soft); color:var(--xm-success); }
.xm-badge-orange { background:var(--xm-warning-soft); color:var(--xm-warning); }
.xm-badge-red { background:var(--xm-error-soft); color:var(--xm-error); }
.xm-badge-neutral { background:var(--xm-surface-soft); color:var(--xm-steel); }

/* 数据表（Notion comparison-table 风格） */
.xm-table { width:100%; border-collapse:collapse; background:var(--xm-canvas);
  border:1px solid var(--xm-hairline); border-radius:var(--xm-radius-md); overflow:hidden; }
.xm-table th { text-align:left; font-size:13px; font-weight:600; color:var(--xm-steel);
  background:var(--xm-surface); padding:10px 16px; border-bottom:1px solid var(--xm-hairline); }
.xm-table td { font-size:14px; color:var(--xm-ink); padding:14px 20px;
  border-bottom:1px solid var(--xm-hairline-soft); vertical-align:top; }
.xm-table tr:last-child td { border-bottom:none; }
.xm-name { font-size:15px; font-weight:600; color:var(--xm-ink); }
.xm-num { font-size:16px; font-weight:600; color:var(--xm-ink); }
.xm-amount { font-size:30px; font-weight:600; color:var(--xm-ink); margin:6px 0; }
.xm-dim { color:var(--xm-slate); }

/* 折叠与链接 */
.xm-acc summary { font-size:16px; font-weight:500; color:var(--xm-ink); cursor:pointer; list-style:none; }
.xm-acc summary::-webkit-details-marker { display:none; }
.xm-link { color:var(--xm-link); text-decoration:none; }
.xm-note { font-size:14px; color:var(--xm-slate); line-height:1.7; }

/* 顶部导航：segmented-tab 语义（激活=ink + 2px 底线） */
[role="tab"] { color:var(--xm-steel) !important; font-size:14px !important; font-weight:500 !important; padding:12px 16px !important; }
[role="tab"][aria-selected="true"] { color:var(--xm-ink) !important; box-shadow: inset 0 -2px 0 0 var(--xm-ink); }

/* 响应式 */
@media (max-width: 1023px) { .xm-home, .xm-page { max-width:100%; } }
@media (max-width: 767px) {
  .xm-h1 { font-size:24px; }
  .xm-table { display:block; overflow-x:auto; }
}
"""
