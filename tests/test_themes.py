# -*- coding: utf-8 -*-
"""主题系统测试：token 完整性 / 内容正确性 / 默认主题不被改坏。

移植自 CodeForge 的思路（scripts/check-theme-vars.mjs）：
主题只要漏一个变量，换主题时页面就会露出默认色 —— 所以这里把"完整性"钉死。
"""

import re

from core import themes


def test_theme_ids_and_registry_are_consistent():
    assert set(themes.THEME_IDS) == set(themes.THEMES.keys())
    assert themes.DEFAULT_ID in themes.THEMES
    assert len(themes.THEME_IDS) == len(set(themes.THEME_IDS)) >= 6


def test_every_theme_covers_all_required_tokens():
    for tid in themes.THEME_IDS:
        missing = themes.missing_tokens(tid)
        assert missing == [], "主题 %s 缺少 token: %s" % (tid, missing)


def test_every_theme_value_is_non_empty_string():
    for tid in themes.THEME_IDS:
        for key, val in themes.get(tid)["vars"].items():
            assert isinstance(val, str) and val.strip(), "%s.%s 值为空" % (tid, key)
        for key, val in (themes.get(tid).get("gradio") or {}).items():
            assert isinstance(val, str) and val.strip(), "%s(gradio).%s 值为空" % (tid, key)


def test_default_theme_keeps_historical_v2_palette():
    """默认主题必须还是 DESIGN.md v2 的原色 —— 防止主题改造把默认外观改坏。"""
    v = themes.get("default")["vars"]
    assert v["--xm-canvas"] == "#ffffff"
    assert v["--xm-primary"] == "#5645d4"
    assert v["--xm-ink"] == "#1a1a1a"
    assert v["--xm-card-shadow"] == "none"
    assert v["--xm-border-w"] == "1px"


def test_port_from_codeforge_keeps_their_signature_colors():
    """移植保真：几套主题的关键色必须与 CodeForge 源文件一致。"""
    assert themes.get("animal")["vars"]["--xm-primary"] == "#19c8b9"     # animal-theme.css
    assert themes.get("animal")["vars"]["--xm-sidebar-bg"] == "#f5c31c"  # --nav-bg
    assert themes.get("wenyang")["vars"]["--xm-canvas"] == "#fffbf0"     # 宣纸纸色
    assert themes.get("wenyang")["vars"]["--xm-primary"] == "#b91c1c"    # 朱砂
    assert themes.get("dark")["vars"]["--xm-primary"] == "#facc15"       # 品牌黄
    assert themes.get("dark")["vars"]["--xm-canvas"] == "#1a1d23"


def test_normalize_falls_back_to_default():
    assert themes.normalize("ANIMAL") == "animal"
    assert themes.normalize(" wenyang ") == "wenyang"
    assert themes.normalize(None) == themes.DEFAULT_ID
    assert themes.normalize("does-not-exist") == themes.DEFAULT_ID


def test_theme_css_contains_all_tokens_and_scope():
    css = themes.theme_css("beast")
    for tok in themes.REQUIRED_TOKENS:
        assert tok in css, "CSS 里缺 %s" % tok
    assert "html:root" in css           # 作用域要能盖住 Gradio 的 .dark
    assert "color-scheme: light" in css


def test_system_theme_has_dark_media_branch():
    css = themes.theme_css("system")
    assert "@media (prefers-color-scheme: dark)" in css
    assert "color-scheme: dark" in css
    assert themes.get("dark")["vars"]["--xm-canvas"] in css   # 深色分支确实用了深色值


def test_style_tag_carries_brand_and_theme_name():
    tag = themes.theme_style_tag("wenyang", brand="小满 · 智能补货", theme_label="纹样 · 宣纸")
    assert tag.startswith("<style id=\"xm-theme-vars\" data-theme-id=\"wenyang\">")
    assert "--xm-nav-brand" in tag and "纹样 · 宣纸" in tag
    assert tag.endswith("</style>")


def test_swatches_are_three_hex_colors():
    for tid in themes.THEME_IDS:
        sw = themes.swatches(tid)
        assert len(sw) == 3
        assert all(re.fullmatch(r"#[0-9a-fA-F]{6}", c) for c in sw), (tid, sw)


def test_theme_metadata_is_present_and_emoji_free():
    emoji = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
    for tid in themes.THEME_IDS:
        th = themes.get(tid)
        for key in ("name", "tag", "source", "desc"):
            val = th.get(key)
            assert isinstance(val, str) and val.strip(), "%s 缺 %s" % (tid, key)
            assert not emoji.search(val), "%s.%s 含 emoji" % (tid, key)
        assert th["scheme"] in ("light", "dark", "auto")


def test_resolved_vars_merges_gradio_tokens():
    v = themes.resolved_vars("dark")
    assert v["--xm-canvas"] == "#1a1d23"
    assert "--body-background-fill" in v
