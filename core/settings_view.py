# -*- coding: utf-8 -*-
"""小满 · 「设置」页（左侧边栏的新栏目，UI v2）

两块内容：
  1. 外观 · 应用主题 —— 主题卡片网格；其中 4 套移植自 CodeForge（野兽风浅/深、森友会、纹样·宣纸），
     另加"小满默认"与"跟随系统"。见 core/themes.py 顶部的移植说明。
  2. 数据与运行环境 —— 真实读取（记忆库规模 / 数据日期范围 / 当前主题 / 数据源文件），不写死。

本模块只渲染，不落盘；主题持久化由 app.py 调 core.settings_store 完成。
所有文案与数字都来自真实模块，读不到时如实显示"读不到"，不编造。
"""

import html as _html

from . import dataset, memory, settings_store, themes
from .config import APP_NAME, APP_SUBTITLE

SETTINGS_CSS = """
/* 主题选择器（Gradio Radio 的外观，尽量贴近卡片语言） */
#st-theme-radio .wrap { gap:8px !important; }
#st-theme-radio label { background:var(--xm-canvas); border:var(--xm-border-w) solid var(--xm-card-border);
  border-radius:var(--xm-radius-full) !important; padding:6px 14px !important;
  color:var(--xm-charcoal) !important; box-shadow:var(--xm-card-shadow); }
#st-theme-radio label.selected, #st-theme-radio label:has(input:checked) {
  border-color:var(--xm-primary) !important; color:var(--xm-primary) !important; }
#st-theme-radio input { display:none !important; }
/* 页内小节分隔 */
.st-block { margin-top:var(--xm-space-xl); }
.st-radio-row { margin:var(--xm-space-sm) 0 var(--xm-space-xs); }
"""


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
            '<div class="xm-hint">选一个主题立即生效；选择会被记住，下次打开还是它。'
            '主题只改颜色、字体、圆角与描边强度，不影响任何计算结果。</div></div>')


def render_theme_cards(current=None) -> str:
    """主题卡片网格（换主题后重新渲染的就是这一块）；当前主题高亮并打「当前」标。"""
    cur = themes.normalize(current if current is not None else settings_store.current_theme())
    cards = []
    for th in themes.list_themes():
        active = (th["id"] == cur)
        sw = ''.join('<span class="st-swatch" style="background:%s"></span>' % _e(c)
                     for c in themes.swatches(th["id"]))
        cards.append(
            '<div class="st-card%s">%s'
            '<div class="st-card-h"><span class="st-card-name">%s</span>'
            '<span class="st-card-tag">%s</span></div>'
            '<div class="st-card-desc">%s</div>'
            '<div class="st-swatches">%s</div>'
            '<div class="st-card-src">来源：%s</div>'
            '</div>' % (
                ' is-active' if active else '',
                '<span class="st-cur">当前</span>' if active else '',
                _e(th["name"]), _e(th["tag"]), _e(th["desc"]), sw, _e(th["source"])))
    return '<div class="st-grid">%s</div>' % ''.join(cards)


def render_theme_grid(current=None) -> str:
    """整块主题区（小节标题 + 卡片网格），供整页渲染与测试使用。"""
    return render_theme_section_head() + render_theme_cards(current)


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
