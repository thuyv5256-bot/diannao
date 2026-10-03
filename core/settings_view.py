# -*- coding: utf-8 -*-
"""小满 · 「设置」页（左侧边栏的新栏目，UI v2）

两块内容：
  1. 外观 · 应用主题 —— **主题选择器就是 gr.Radio 本体**，用 CSS 渲染成卡片网格
     （主题名 + 标签/说明/来源 + 主题色板 + 「当前」角标）。点卡片 = 点对应的 radio 选项，
     状态只有 Radio 一份 —— 不再有"好看的卡片点不动"的第二份展示层（见 ARD T-UI-10）。
     4 套主题移植自 CodeForge（野兽风浅/深、森友会、纹样·宣纸），另加"小满默认"与"跟随系统"。
  2. 数据与运行环境 —— 真实读取（记忆库规模 / 数据日期范围 / 当前主题 / 数据源文件），不写死。

本模块只渲染，不落盘；主题持久化由 app.py 调 core.settings_store 完成。
所有文案与数字都来自真实模块，读不到时如实显示"读不到"，不编造。
"""

import html as _html

from . import dataset, memory, settings_store, themes
from .config import APP_NAME, APP_SUBTITLE


def theme_choices():
    """Radio 的选项：[(主题名, 主题 id), ...]，顺序即卡片顺序（CSS 用 :nth-of-type 对位）。"""
    return [(th["name"], th["id"]) for th in themes.list_themes()]


def _css_text(text) -> str:
    """把文案安全地放进 CSS 字符串（转义反斜杠与引号；换行由调用方换成 \\A ）。"""
    return str(text).replace("\\", "\\\\").replace('"', '\\"')


def _swatch_gradient(theme_id: str) -> str:
    """把该主题的 2~3 个色板色拼成"并排色块"渐变，一行就能看出主题气质。"""
    cols = themes.swatches(theme_id)
    if not cols:  # 兜底也从主题 token 取，本模块不允许出现写死颜色（tests/test_ui_consistency.py 会拦）
        p = themes.palette(theme_id)
        cols = [p["canvas"], p["ink"]]
    parts = []
    x = 0
    for i, c in enumerate(cols):
        parts.append("%s %dpx %dpx" % (c, x, x + 26))
        if i < len(cols) - 1:
            parts.append("transparent %dpx %dpx" % (x + 26, x + 32))
        x += 32
    return "linear-gradient(90deg, %s)" % ", ".join(parts)


def _swatch_width(theme_id: str) -> int:
    n = max(1, len(themes.swatches(theme_id)))
    return n * 26 + (n - 1) * 6


def theme_card_css() -> str:
    """按主题逐个生成卡片样式（顺序与 theme_choices 一致，所以 nth-of-type 能对上）。"""
    rows = []
    for i, th in enumerate(themes.list_themes(), start=1):
        meta = "%s\n%s\n来源：%s" % (th["tag"], th["desc"], th["source"])
        rows.append(
            "#st-theme-radio .wrap > label:nth-of-type(%d) "
            "{ background-image: %s; background-size: %dpx 26px; }"
            % (i, _swatch_gradient(th["id"]), _swatch_width(th["id"])))
        rows.append(
            '#st-theme-radio .wrap > label:nth-of-type(%d)::after { content: "%s"; }'
            % (i, _css_text(meta).replace("\n", "\\A ")))
    return "\n".join(rows)


SETTINGS_CSS = """
/* 主题选择器：Radio 本体渲染成卡片（点卡片就是选主题，状态只有一份） */
#st-theme-radio { border:0 !important; padding:0 !important; min-width:0 !important; }
#st-theme-radio .info-text { font-size:12px; color:var(--xm-steel); margin:2px 0 10px; }
#st-theme-radio .wrap { display:grid !important;
  grid-template-columns:repeat(auto-fill, minmax(238px, 1fr)); gap:var(--xm-space-md) !important; }
#st-theme-radio .wrap > label { position:relative; display:block; padding:16px 18px 50px;
  background-color:var(--xm-canvas); background-repeat:no-repeat;
  background-position:18px calc(100% - 16px);
  border:var(--xm-border-w) solid var(--xm-card-border); border-radius:var(--xm-radius-lg);
  box-shadow:var(--xm-card-shadow); cursor:pointer; transition:border-color .15s ease; }
#st-theme-radio .wrap > label:hover { border-color:var(--xm-primary); }
#st-theme-radio .wrap > label.selected { border-color:var(--xm-primary); }
/* 原生圆点视觉隐藏但保留在 tab 顺序里（键盘可用） */
#st-theme-radio .wrap > label > input { position:absolute; opacity:0; width:1px; height:1px; margin:0; }
#st-theme-radio .wrap > label:focus-within { outline:2px solid var(--xm-primary); outline-offset:2px; }
#st-theme-radio .wrap > label > span { font-size:15px; font-weight:600; color:var(--xm-ink); }
#st-theme-radio .wrap > label::after { display:block; margin-top:6px; font-size:13px;
  color:var(--xm-slate); line-height:1.7; white-space:pre-line; }
#st-theme-radio .wrap > label.selected > span::after { content:"当前"; position:absolute;
  top:12px; right:12px; font-size:12px; font-weight:600; color:var(--xm-canvas);
  background:var(--xm-primary); border-radius:var(--xm-radius-full); padding:2px 10px; }
/* 页内小节分隔 / 状态条 */
.st-block { margin-top:var(--xm-space-xl); }
.st-radio-row { margin:var(--xm-space-sm) 0 var(--xm-space-xs); }
""" + theme_card_css()


def _e(v) -> str:
    return _html.escape(str(v), quote=True)


def render_head() -> str:
    return ('<div class="xm-page">'
            '<div class="xm-h1">设置</div>'
            '<div class="xm-sm" style="margin-top:6px">'
            '外观主题、以及当前这台机器上跑的真实环境信息。</div>'
            '</div>')


def render_theme_section_head() -> str:
    return ('<div class="xm-sec"><div class="xm-sec-title">外观 · 应用主题</div>'
            '<div class="xm-hint">点卡片或上面的选项都能换主题，立即生效；选择会被记住，'
            '下次打开还是它。主题只改颜色、字体、圆角与描边强度，不影响任何计算结果。</div></div>')


def render_theme_grid(current=None) -> str:
    """整块主题区（小节标题 + 状态条）；交互控件是 app.py 里的 gr.Radio#st-theme-radio。"""
    return render_theme_section_head() + render_status(current)


def render_status(current=None) -> str:
    cur = themes.get(current if current is not None else settings_store.current_theme())
    return ('<div class="xm-brief st-radio-row">'
            '<span class="xm-badge xm-badge-neutral">当前</span>'
            '<div><div class="xm-brief-t">%s</div>'
            '<div class="xm-brief-sub">%s</div></div></div>' % (
                _e(cur["name"]), _e(cur["source"])))


def render_env_panel(current=None) -> str:
    """真实运行环境：读不到就如实说读不到。"""
    items = []
    try:
        st = memory.memory_stats()
        days = memory.available_days()
        span = ('%s ~ %s' % (days[0], days[-1])) if days else '（无数据）'
        items += [
            ('记忆库商品数', '%d 个（民生 %d）' % (st.get('商品数', 0), st.get('民生商品数', 0))),
            ('历史销量记录', '%s 条 / %s 天' % (st.get('销量记录条数', 0), st.get('累计覆盖天数', 0))),
            ('数据日期范围', span),
            ('进化事件数', '%d 条' % st.get('进化事件数', 0)),
        ]
    except Exception as exc:  # noqa: BLE001 —— 环境信息读不到不影响页面
        items.append(('记忆库', '读不到（%s）' % type(exc).__name__))

    cur = themes.get(current if current is not None else settings_store.current_theme())
    items += [
        ('应用', '%s · %s' % (APP_NAME, APP_SUBTITLE)),
        ('当前主题', '%s（%s）' % (cur['name'], cur['tag'])),
        ('可选主题', '%d 套：%s' % (len(themes.THEME_IDS),
                                    '、'.join(t['name'] for t in themes.list_themes()))),
        ('数据源', '%s + %s' % (dataset.PRODUCTS_CSV.name, dataset.SALES_CSV.name)),
    ]
    cells = ''.join('<div class="xm-kv"><span class="xm-kv-k">%s</span>'
                    '<span class="xm-kv-v">%s</span></div>' % (_e(k), _e(v))
                    for k, v in items)
    return ('<div class="st-block"><div class="xm-sec-title">数据与运行环境</div>'
            '<div class="xm-card"><div class="xm-kv-row">%s</div>'
            '<div class="xm-cap" style="margin-top:12px">'
            '以上均为当前机器上的真实读数；数据来源是社区小店数字经营仿真数据（非真实门店采集数据）。'
            '</div></div></div>' % cells)


def render_page(current=None) -> str:
    return render_head() + render_theme_grid(current) + render_env_panel(current)


# 供 app.py 直接引用（首屏与回调都走同一个渲染函数，避免两处样式漂移）
PAGE_HEAD = render_head
SECTION_HEAD = render_theme_section_head
