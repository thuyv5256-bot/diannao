# -*- coding: utf-8 -*-
"""「设置」页渲染测试：主题卡片 / 当前态 / 真实环境信息 / 转义 / 无 emoji。"""

import re

from core import settings_view, themes


def test_theme_cards_render_every_theme():
    html = settings_view.render_theme_cards("animal")
    for th in themes.list_themes():
        assert th["name"] in html
        assert th["source"] in html
    assert html.count("st-card") >= len(themes.THEME_IDS)


def test_only_current_theme_is_marked():
    html = settings_view.render_theme_cards("dark")
    assert html.count(">当前<") == 1
    assert "is-active" in html


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
    html = settings_view.render_theme_cards("animal")
    assert "<img" not in html
    assert "&lt;img" in html


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
