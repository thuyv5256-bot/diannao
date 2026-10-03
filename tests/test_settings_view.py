# -*- coding: utf-8 -*-
"""「设置」页渲染测试：主题选择器（Radio 卡片）/ 当前态 / 真实环境信息 / 转义 / 无 emoji。

T-UI-10 之后：主题选择器只有**一份控件** —— app.py 的 gr.Radio#st-theme-radio；
卡片外观由 settings_view 生成的 CSS 负责。所以这里测「选项清单 + 每套主题都有卡片规则」，
不再测已经不存在的装饰性卡片 HTML（旧的两份展示层正是点击失效的根因）。
"""

import re

from core import settings_view, themes


def test_theme_choices_cover_every_theme():
    """选项清单必须覆盖全部主题，顺序与 themes.THEME_IDS 一致（CSS 靠顺序对位）。"""
    choices = settings_view.theme_choices()
    assert [tid for _label, tid in choices] == list(themes.THEME_IDS)
    for th in themes.list_themes():
        assert (th["name"], th["id"]) in choices


def test_card_css_has_one_rule_set_per_theme():
    """每套主题都要有色板、说明/来源文案与「当前」角标所需的规则。"""
    css = settings_view.SETTINGS_CSS
    for i, th in enumerate(themes.list_themes(), start=1):
        assert "label:nth-of-type(%d) {" % i in css
        assert "label:nth-of-type(%d)::after" % i in css
        assert th["desc"][:8] in css
        assert th["source"][:8] in css
    assert css.count("background-image: linear-gradient") == len(themes.THEME_IDS)
    assert len(re.findall("nth-of-type", css)) == len(themes.THEME_IDS) * 2


def test_picker_is_a_single_control():
    """回归防线（T-UI-10）：不要又出现「好看的卡片点不动」的第二份展示层。"""
    css = settings_view.SETTINGS_CSS
    assert "#st-theme-radio .wrap > label" in css      # 被样式化的是 Radio 的 label 本体
    assert ".st-card" not in css and ".st-grid" not in css
    assert not hasattr(settings_view, "render_theme_cards")
    # 原生日志隐藏但仍在 tab 顺序里（键盘可达）：用 opacity/尺寸隐藏，而不是 display:none
    assert "> input { position:absolute; opacity:0" in css
    assert "display:none" not in css.split("#st-theme-radio")[1][:600]


def test_page_contains_both_sections():
    page = settings_view.render_page("wenyang")
    assert "设置" in page
    assert "外观 · 应用主题" in page
    assert "数据与运行环境" in page
    assert settings_view.render_theme_section_head() in page


def test_no_emoji_in_rendered_html():
    emoji = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
    for tid in themes.THEME_IDS:
        html = settings_view.render_page(tid)
        assert not emoji.search(html), "设置页在主题 %s 下含 emoji" % tid


def test_theme_names_are_escaped(monkeypatch):
    """主题元数据若含 HTML，必须被转义（防止未来接外部主题源时注入）。"""
    evil = dict(themes.THEMES["animal"])
    evil["name"] = "<img src=x onerror=alert(1)>"
    monkeypatch.setitem(themes.THEMES, "animal", evil)
    html = settings_view.render_page("animal")
    assert "<img" not in html
    assert "&lt;img" in html


def test_css_escapes_quotes_from_theme_metadata(monkeypatch):
    """主题说明里若出现英文引号，生成的 CSS 不能被打断（否则整页样式崩）。"""
    evil = dict(themes.THEMES["animal"])
    evil["desc"] = '引号 " 与反斜杠 \\ 都要安全'
    monkeypatch.setitem(themes.THEMES, "animal", evil)
    css = settings_view.theme_card_css()
    line = [l for l in css.split("\n") if "nth-of-type(4)::after" in l][0]
    assert '\\"' in line
    assert line.rstrip().endswith(chr(34) + "; }")   # 字符串正常闭合


def test_env_panel_uses_real_memory_counts(db):
    """conftest 的 db fixture 灌了 2 个商品（1 个民生）→ 页面必须如实显示。"""
    html = settings_view.render_env_panel("default")
    assert "2 个（民生 1）" in html
    assert "数据与运行环境" in html
    assert "（无数据）" in html          # 临时库没有销量，日期范围如实为空


def test_env_panel_degrades_when_memory_unavailable(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(settings_view.memory, "memory_stats", boom)
    html = settings_view.render_env_panel("default")
    assert "读不到" in html
    assert "数据与运行环境" in html     # 其余信息照常渲染


def test_status_block_shows_current_source():
    html = settings_view.render_status("beast")
    assert themes.get("beast")["name"] in html
    assert themes.get("beast")["source"] in html
