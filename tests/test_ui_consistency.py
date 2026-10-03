# -*- coding: utf-8 -*-
"""UI 规范一致性校验（ARD T-QA-02）：把「禁 emoji / 禁写死颜色」变成会失败的测试。

规则来自 DESIGN.md §5 与 CLAUDE.md 铁律 8：
  · UI 产出文件**不允许出现彩色 Emoji**（只放行 ✓ ✗ ★ 这类单色符号）；
  · **已迁移 v2 的模块不允许写死颜色** —— 颜色只能来自 core/themes.py（主题变量）
    与 core/ui_theme.py（组件类）；
  · 旧体系 class（`dn-` / `badge b-*` / `kpi-row`）不允许回流。

为什么用"已迁移清单"而不是一刀切：why / final / about 三页还没迁移（T-UI-02/03/04），
它们仍有内联色，先留在 PENDING；迁移完成后把模块名移进 MIGRATED，测试立刻开始兜住。
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
ALLOWED_SYMBOLS = set("✓✗★☆↑↓→←›·—…×")
HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")

# 直接产出 HTML / CSS 的文件
UI_FILES = (
    ["app.py", "core/ui_theme.py", "core/themes.py"]
    + sorted(str(p.relative_to(ROOT)).replace("\\", "/")
             for p in (ROOT / "core").glob("*_view.py"))
)

# 已经迁移到 v2 的模块：不允许写死颜色（themes/ui_theme 是 token 源，天然豁免）
COLOR_TOKEN_SOURCES = {"core/ui_theme.py", "core/themes.py"}
MIGRATED = {
    "app.py",
    "core/home_view.py",
    "core/feedback_view.py",
    "core/learn_view.py",
    "core/ledger_view.py",
    "core/settings_view.py",
    # T-UI-02 / T-UI-03 / T-UI-04：三页已完成 v2 迁移（白名单清零）
    "core/why_view.py",
    "core/final_view.py",
    "core/about_view.py",
}
# 迁移完成后再无豁免：新页面若还没迁移，必须显式登记在这里 + 在 ARD 建对应任务
PENDING_MIGRATION: set = set()

LEGACY_PATTERNS = ("dn-card", "dn-hero", "dn-row", "dn-risk", "badge b-", "kpi-row", 'class="kpi"')


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_ui_file_list_is_complete():
    """清单必须覆盖所有真正会渲染 HTML 的模块（新增页面别忘了加进来）。"""
    assert "app.py" in UI_FILES
    for rel in MIGRATED | PENDING_MIGRATION:
        assert rel in UI_FILES, "%s 不在 UI_FILES 里" % rel


def test_no_emoji_in_ui_files():
    offenders = {}
    for rel in UI_FILES:
        text = _read(rel)
        hits = sorted({c for c in EMOJI_RE.findall(text) if c not in ALLOWED_SYMBOLS})
        if hits:
            offenders[rel] = hits
    assert offenders == {}, "UI 文件里出现彩色 Emoji（DESIGN.md §5 禁用）：%s" % offenders


def test_migrated_modules_have_no_hardcoded_colors():
    offenders = {}
    for rel in sorted(MIGRATED - COLOR_TOKEN_SOURCES):
        hits = sorted(set(HEX_RE.findall(_read(rel))))
        if hits:
            offenders[rel] = hits
    assert offenders == {}, ("已迁移模块里出现写死颜色，应改为 --xm-* token：%s" % offenders)


def test_color_homes_are_clean():
    """颜色只有一个家：themes.py。ui_theme.py 的组件类必须 100% 消费 token。"""
    assert HEX_RE.search(_read("core/themes.py")), "themes.py 应当持有主题色值（唯一颜色来源）"
    assert not HEX_RE.search(_read("core/ui_theme.py")), \
        "ui_theme.py 不应写死颜色，组件一律用 --xm-* token"


def test_every_view_module_is_classified():
    """每个 *_view.py 要么在 MIGRATED（受颜色/emoji 约束），要么在 PENDING（且 ARD 里有任务）。

    这条防的是"新加一个页面视图却没人管"——迁移完之后 MIGRATED 就是唯一入口。
    """
    views = {str(p.relative_to(ROOT)).replace("\\", "/")
             for p in (ROOT / "core").glob("*_view.py")}
    unclassified = views - MIGRATED - PENDING_MIGRATION
    assert unclassified == set(), "这些视图模块既不在 MIGRATED 也不在 PENDING：%s" % unclassified
    if PENDING_MIGRATION:
        ard = _read("docs/ARD.md")
        for task in ("T-UI-01", "T-UI-02", "T-UI-03", "T-UI-04"):
            assert task in ard, "%s 已不在 ARD 中，请同步 PENDING_MIGRATION" % task


def test_no_legacy_class_names_in_app():
    text = _read("app.py")
    left = [p for p in LEGACY_PATTERNS if p in text]
    assert left == [], "app.py 里仍有旧体系 class：%s" % left


def test_theme_aware_plotly_layout_follows_dark_theme():
    from core import themes
    light = themes.plotly_layout("default")
    dark = themes.plotly_layout("dark")
    assert light["template"] == "plotly_white"
    assert dark["template"] == "plotly_dark"
    assert dark["paper_bgcolor"] == themes.get("dark")["vars"]["--xm-canvas"]
    assert dark["font"]["color"] == themes.get("dark")["vars"]["--xm-ink"]
    assert dark["colorway"][0] == themes.get("dark")["vars"]["--xm-primary"]


def test_evolution_chart_uses_active_theme(db, monkeypatch):
    """深色主题下，图表背景/文字必须跟着变（而不是永远白底黑字）。"""
    import app
    monkeypatch.setattr(app, "ACTIVE_THEME", "dark", raising=False)
    fig = app.evolution_chart("L1")
    assert fig.layout.paper_bgcolor == "#1a1d23"
    assert fig.layout.plot_bgcolor == "#1a1d23"
    monkeypatch.setattr(app, "ACTIVE_THEME", "default", raising=False)
    fig2 = app.evolution_chart("L1")
    assert fig2.layout.paper_bgcolor == "#ffffff"
