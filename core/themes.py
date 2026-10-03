# -*- coding: utf-8 -*-
"""小满 · 主题系统（移植自 CodeForge 的"CSS 变量作用域覆盖"方案）

移植来源
--------
E:\\vibe coding\\CodeForge\\src\\renderer\\styles\\
    global.css（野兽风浅色基线）/ dark-theme.css / animal-theme.css / wenyang-theme.css
以及该项目的 docs/ADR/ADR-005-theme-css-variables.md 与 scripts/check-theme-vars.mjs。

做法（与 CodeForge 同构，但落到小满自己的 token）
------------------------------------------------
  · 一个主题 = 一组 `--xm-*` 覆盖值（外加 Gradio 原生变量与字体/圆角/描边强度）
  · 通过 `<style>` 注入 `html:root` 作用域生效；页面所有组件只消费 `--xm-*`，换主题零改动
  · 不引入任何外部字体 / 图片资源（离线可用，字体走系统回退链）
  · 每个主题必须覆盖 REQUIRED_TOKENS 全部 token，否则 tests/test_themes.py 直接失败
    （思路同 CodeForge 的 check-theme-vars：主题漏变量 → 页面在非默认主题下破损）

注意
----
本文件是**唯一**允许出现颜色字面量的地方之一（另一个是 core/ui_theme.py 的组件样式）。
页面 / 视图模块禁止写死颜色，只能消费 token —— 见 CLAUDE.md UI 铁律。
"""

from __future__ import annotations

# ── 主题必须覆盖的 token（少一个就可能在换主题时露出默认色）──────────────
REQUIRED_TOKENS: tuple[str, ...] = (
    # 画布与表面
    "--xm-canvas", "--xm-surface", "--xm-surface-soft", "--xm-shell-bg",
    # 描边
    "--xm-hairline", "--xm-hairline-soft", "--xm-hairline-strong",
    "--xm-card-border", "--xm-border-w",
    # 文字
    "--xm-ink", "--xm-charcoal", "--xm-slate", "--xm-steel", "--xm-stone", "--xm-muted",
    # 主操作与链接
    "--xm-primary", "--xm-primary-pressed", "--xm-on-primary", "--xm-link",
    # 语义色与软底
    "--xm-success", "--xm-warning", "--xm-error",
    "--xm-success-soft", "--xm-warning-soft", "--xm-error-soft", "--xm-info-soft",
    # 侧边栏（本次新增的左侧导航）
    "--xm-sidebar-bg", "--xm-sidebar-fg", "--xm-sidebar-muted",
    "--xm-sidebar-active-bg", "--xm-sidebar-active-fg", "--xm-sidebar-border",
    # 形状与字体
    "--xm-font", "--xm-radius-xs", "--xm-radius-sm", "--xm-radius-md",
    "--xm-radius-lg", "--xm-radius-full",
    # 卡片观感
    "--xm-card-shadow",
)

# 间距是结构性的，不随主题变化（保留在 core/ui_theme.py）
SPACING_TOKENS: tuple[str, ...] = (
    "--xm-space-xxs", "--xm-space-xs", "--xm-space-sm", "--xm-space-md",
    "--xm-space-lg", "--xm-space-xl", "--xm-space-xxl", "--xm-space-xxxl",
)

# ── Gradio 原生组件变量（不覆盖的话 Dataframe/Dropdown/Accordion 会留在 Gradio 默认配色）──
GRADIO_TOKENS: tuple[str, ...] = (
    "--body-background-fill", "--background-fill-primary", "--background-fill-secondary",
    "--block-background-fill", "--block-border-color", "--block-title-text-color",
    "--block-label-text-color", "--panel-background-fill", "--panel-border-color",
    "--body-text-color", "--body-text-color-subdued",
    "--border-color-primary", "--border-color-accent",
    "--input-background-fill", "--input-border-color", "--input-placeholder-color",
    "--table-border-color", "--table-even-background-fill", "--table-odd-background-fill",
    "--color-accent", "--color-accent-soft",
    "--button-primary-background-fill", "--button-primary-text-color",
    "--button-secondary-background-fill", "--button-secondary-text-color",
    "--link-text-color", "--checkbox-background-color", "--slider-color",
)

_FONT_SANS = ('-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", '
              '"Microsoft YaHei", "Noto Sans SC", system-ui, sans-serif')
_FONT_ROUND = ('"Nunito", "Noto Sans SC", "MiSans", -apple-system, "PingFang SC", '
               '"Microsoft YaHei", sans-serif')
_FONT_SERIF = ('"Noto Serif SC", "Source Han Serif SC", "Songti SC", "SimSun", '
               '"Microsoft YaHei", serif')
_FONT_BEAST = ('"Inter", "Space Grotesk", -apple-system, BlinkMacSystemFont, "Segoe UI", '
               '"Microsoft YaHei", "PingFang SC", sans-serif')


def _gradio(canvas: str, surface: str, surface_soft: str, ink: str, subdued: str,
            border: str, accent: str, on_accent: str, link: str,
            primary_btn_bg: str, primary_btn_fg: str) -> dict:
    """由主题色推导 Gradio 原生变量，避免每个主题手写 28 行。"""
    return {
        "--body-background-fill": surface,
        "--background-fill-primary": canvas,
        "--background-fill-secondary": surface_soft,
        "--block-background-fill": canvas,
        "--block-border-color": border,
        "--block-title-text-color": ink,
        "--block-label-text-color": subdued,
        "--panel-background-fill": canvas,
        "--panel-border-color": border,
        "--body-text-color": ink,
        "--body-text-color-subdued": subdued,
        "--border-color-primary": border,
        "--border-color-accent": accent,
        "--input-background-fill": canvas,
        "--input-border-color": border,
        "--input-placeholder-color": subdued,
        "--table-border-color": border,
        "--table-even-background-fill": surface_soft,
        "--table-odd-background-fill": canvas,
        "--color-accent": accent,
        "--color-accent-soft": surface_soft,
        "--button-primary-background-fill": primary_btn_bg,
        "--button-primary-text-color": primary_btn_fg,
        "--button-secondary-background-fill": canvas,
        "--button-secondary-text-color": ink,
        "--link-text-color": link,
        "--checkbox-background-color": canvas,
        "--slider-color": accent,
    }


# ════════════════════════════════════════════════════════════════════
# 主题定义
# ════════════════════════════════════════════════════════════════════
THEMES: dict[str, dict] = {}

# ── 1. 小满默认（Notion 风 v2，即原 DESIGN.md 的 token，未改动）───────────
THEMES["default"] = {
    "id": "default",
    "name": "小满默认",
    "tag": "Notion 风（DESIGN.md v2）",
    "source": "本项目原有 token，未改动",
    "desc": "浅色纸面、紫色主操作、无阴影卡片。评委默认看到的版本。",
    "scheme": "light",
    "vars": {
        "--xm-canvas": "#ffffff", "--xm-surface": "#f6f5f4", "--xm-surface-soft": "#fafaf9",
        "--xm-shell-bg": "#ffffff",
        "--xm-hairline": "#e5e3df", "--xm-hairline-soft": "#ede9e4",
        "--xm-hairline-strong": "#c8c4be",
        "--xm-card-border": "#e5e3df", "--xm-border-w": "1px",
        "--xm-ink": "#1a1a1a", "--xm-charcoal": "#37352f", "--xm-slate": "#5d5b54",
        "--xm-steel": "#787671", "--xm-stone": "#a4a097", "--xm-muted": "#bbb8b1",
        "--xm-primary": "#5645d4", "--xm-primary-pressed": "#4534b3",
        "--xm-on-primary": "#ffffff", "--xm-link": "#0075de",
        "--xm-success": "#1aae39", "--xm-warning": "#dd5b00", "--xm-error": "#e03131",
        "--xm-success-soft": "#d9f3e1", "--xm-warning-soft": "#ffe8d4",
        "--xm-error-soft": "#fde0ec", "--xm-info-soft": "#dcecfa",
        "--xm-sidebar-bg": "#ffffff", "--xm-sidebar-fg": "#37352f",
        "--xm-sidebar-muted": "#787671",
        "--xm-sidebar-active-bg": "#f6f5f4", "--xm-sidebar-active-fg": "#1a1a1a",
        "--xm-sidebar-border": "#e5e3df",
        "--xm-font": _FONT_SANS,
        "--xm-radius-xs": "4px", "--xm-radius-sm": "6px", "--xm-radius-md": "8px",
        "--xm-radius-lg": "12px", "--xm-radius-full": "9999px",
        "--xm-card-shadow": "none",
    },
    "gradio": _gradio("#ffffff", "#ffffff", "#fafaf9", "#1a1a1a", "#5d5b54", "#e5e3df",
                      "#5645d4", "#ffffff", "#0075de", "#5645d4", "#ffffff"),
}

# ── 2. 野兽风 · 浅色（CodeForge 默认 light / Neo-Brutalist）───────────────
THEMES["beast"] = {
    "id": "beast",
    "name": "野兽风 · 浅色",
    "tag": "Neo-Brutalist",
    "source": "CodeForge styles/global.css（:root 基线）",
    "desc": "黑描边 2px、硬投影、明黄侧边栏；CodeForge 的默认外观。",
    "scheme": "light",
    "vars": {
        "--xm-canvas": "#ffffff", "--xm-surface": "#fcfbf7", "--xm-surface-soft": "#f7f5ed",
        "--xm-shell-bg": "#fcfbf7",
        "--xm-hairline": "#111111", "--xm-hairline-soft": "#d8d5cc",
        "--xm-hairline-strong": "#000000",
        "--xm-card-border": "#000000", "--xm-border-w": "2px",
        "--xm-ink": "#111111", "--xm-charcoal": "#374151", "--xm-slate": "#4b5563",
        "--xm-steel": "#6b7280", "--xm-stone": "#898989", "--xm-muted": "#a3a3a3",
        "--xm-primary": "#111111", "--xm-primary-pressed": "#333333",
        "--xm-on-primary": "#ffffff", "--xm-link": "#111111",
        "--xm-success": "#059669", "--xm-warning": "#d97706", "--xm-error": "#dc2626",
        "--xm-success-soft": "#e7f6ef", "--xm-warning-soft": "#fdf1e0",
        "--xm-error-soft": "#fdeaea", "--xm-info-soft": "#fdf6dd",
        "--xm-sidebar-bg": "#facc15", "--xm-sidebar-fg": "#111111",
        "--xm-sidebar-muted": "#5b4a06",
        "--xm-sidebar-active-bg": "rgba(0,0,0,0.10)", "--xm-sidebar-active-fg": "#111111",
        "--xm-sidebar-border": "#000000",
        "--xm-font": _FONT_BEAST,
        "--xm-radius-xs": "0px", "--xm-radius-sm": "2px", "--xm-radius-md": "2px",
        "--xm-radius-lg": "4px", "--xm-radius-full": "2px",
        "--xm-card-shadow": "3px 3px 0 #000000",
    },
    "gradio": _gradio("#ffffff", "#fcfbf7", "#f7f5ed", "#111111", "#4b5563", "#000000",
                      "#111111", "#ffffff", "#111111", "#111111", "#ffffff"),
}

# ── 3. 野兽风 · 深色（CodeForge dark-theme.css）─────────────────────────
THEMES["dark"] = {
    "id": "dark",
    "name": "野兽风 · 深色",
    "tag": "Dark",
    "source": "CodeForge styles/dark-theme.css",
    "desc": "近黑底 + 品牌黄强调色；CodeForge 深色档，硬投影保留。",
    "scheme": "dark",
    "vars": {
        "--xm-canvas": "#1a1d23", "--xm-surface": "#0f1115", "--xm-surface-soft": "#21252e",
        "--xm-shell-bg": "#0f1115",
        "--xm-hairline": "#2a2f3a", "--xm-hairline-soft": "#232833",
        "--xm-hairline-strong": "#3a4150",
        "--xm-card-border": "#2a2f3a", "--xm-border-w": "2px",
        "--xm-ink": "#f0f2f5", "--xm-charcoal": "#cbd5e1", "--xm-slate": "#b8c5d6",
        "--xm-steel": "#8d97a8", "--xm-stone": "#6b7280", "--xm-muted": "#5a6472",
        "--xm-primary": "#facc15", "--xm-primary-pressed": "#fde047",
        "--xm-on-primary": "#111111", "--xm-link": "#facc15",
        "--xm-success": "#34d399", "--xm-warning": "#fbbf24", "--xm-error": "#f87171",
        "--xm-success-soft": "rgba(52,211,153,0.12)", "--xm-warning-soft": "rgba(251,191,36,0.12)",
        "--xm-error-soft": "rgba(248,113,113,0.12)", "--xm-info-soft": "rgba(250,204,21,0.12)",
        "--xm-sidebar-bg": "#0f1115", "--xm-sidebar-fg": "#f0f2f5",
        "--xm-sidebar-muted": "#8d97a8",
        "--xm-sidebar-active-bg": "rgba(250,204,21,0.12)", "--xm-sidebar-active-fg": "#facc15",
        "--xm-sidebar-border": "#2a2f3a",
        "--xm-font": _FONT_BEAST,
        "--xm-radius-xs": "0px", "--xm-radius-sm": "2px", "--xm-radius-md": "2px",
        "--xm-radius-lg": "4px", "--xm-radius-full": "2px",
        "--xm-card-shadow": "3px 3px 0 rgba(0,0,0,0.85)",
    },
    "gradio": _gradio("#1a1d23", "#0f1115", "#21252e", "#f0f2f5", "#8d97a8", "#2a2f3a",
                      "#facc15", "#111111", "#facc15", "#facc15", "#111111"),
}

# ── 4. 森友会（CodeForge animal-theme.css / Animal Island）───────────────
THEMES["animal"] = {
    "id": "animal",
    "name": "森友会",
    "tag": "Animal Island",
    "source": "CodeForge styles/animal-theme.css（animal-island-ui 参考库）",
    "desc": "薄荷绿 + 奶油黄 + 暖棕文字，大圆角与 3D 底部投影，圆润手感。",
    "scheme": "light",
    "vars": {
        "--xm-canvas": "#fdfdf5", "--xm-surface": "#f8f8f0", "--xm-surface-soft": "#f0e8d8",
        "--xm-shell-bg": "#f8f8f0",
        "--xm-hairline": "#e8dcc8", "--xm-hairline-soft": "#f0e8d8",
        "--xm-hairline-strong": "#aaa69d",
        "--xm-card-border": "#e8dcc8", "--xm-border-w": "2px",
        "--xm-ink": "#794f27", "--xm-charcoal": "#7d5a33", "--xm-slate": "#9f927d",
        "--xm-steel": "#9f927d", "--xm-stone": "#b8a98f", "--xm-muted": "#c4b89e",
        "--xm-primary": "#19c8b9", "--xm-primary-pressed": "#50b9ab",
        "--xm-on-primary": "#ffffff", "--xm-link": "#794f27",
        "--xm-success": "#6fba2c", "--xm-warning": "#dba90e", "--xm-error": "#e05a5a",
        "--xm-success-soft": "rgba(111,186,44,0.12)", "--xm-warning-soft": "rgba(245,195,28,0.14)",
        "--xm-error-soft": "rgba(224,90,90,0.10)", "--xm-info-soft": "#e6f9f6",
        "--xm-sidebar-bg": "#f5c31c", "--xm-sidebar-fg": "#794f27",
        "--xm-sidebar-muted": "#8a6a2e",
        "--xm-sidebar-active-bg": "rgba(255,255,255,0.35)", "--xm-sidebar-active-fg": "#5a3a1a",
        "--xm-sidebar-border": "#e8dcc8",
        "--xm-font": _FONT_ROUND,
        "--xm-radius-xs": "12px", "--xm-radius-sm": "16px", "--xm-radius-md": "16px",
        "--xm-radius-lg": "24px", "--xm-radius-full": "9999px",
        "--xm-card-shadow": "0 5px 0 0 #bdaea0",
    },
    "gradio": _gradio("#fdfdf5", "#f8f8f0", "#f0e8d8", "#794f27", "#9f927d", "#e8dcc8",
                      "#19c8b9", "#ffffff", "#794f27", "#19c8b9", "#ffffff"),
}

# ── 5. 纹样 · 宣纸（CodeForge wenyang-theme.css / Xuan Paper）─────────────
THEMES["wenyang"] = {
    "id": "wenyang",
    "name": "纹样 · 宣纸",
    "tag": "Xuan Paper",
    "source": "CodeForge styles/wenyang-theme.css（wenyang.net 三主题之「宣纸」）",
    "desc": "宣纸米黄 + 墨字 + 朱砂印章红，宋体字骨、小圆角、深墨侧边栏；图录级留白。",
    "scheme": "light",
    "vars": {
        "--xm-canvas": "#fffbf0", "--xm-surface": "#f6eedb", "--xm-surface-soft": "#f0e6c8",
        "--xm-shell-bg": "repeating-linear-gradient(0deg, rgba(43,29,14,0.018) 0 1px, transparent 1px 4px), #f6eedb",
        "--xm-hairline": "#d6c7a8", "--xm-hairline-soft": "#e6dbbe",
        "--xm-hairline-strong": "#c9b99a",
        "--xm-card-border": "#c9b99a", "--xm-border-w": "1px",
        "--xm-ink": "#2b1d0e", "--xm-charcoal": "#5e4a33", "--xm-slate": "#8d7d6b",
        "--xm-steel": "#8d7d6b", "--xm-stone": "#b8a898", "--xm-muted": "#c4b6a2",
        "--xm-primary": "#b91c1c", "--xm-primary-pressed": "#9a1818",
        "--xm-on-primary": "#fff8e6", "--xm-link": "#b91c1c",
        "--xm-success": "#1a7a4c", "--xm-warning": "#9c7a1a", "--xm-error": "#b91c1c",
        "--xm-success-soft": "rgba(26,122,76,0.09)", "--xm-warning-soft": "rgba(156,122,26,0.10)",
        "--xm-error-soft": "rgba(185,28,28,0.08)", "--xm-info-soft": "rgba(74,107,138,0.10)",
        "--xm-sidebar-bg": "#1c1916", "--xm-sidebar-fg": "#f0e6c8",
        "--xm-sidebar-muted": "#a99a7d",
        "--xm-sidebar-active-bg": "rgba(201,168,92,0.20)", "--xm-sidebar-active-fg": "#fffbf0",
        "--xm-sidebar-border": "rgba(201,168,92,0.30)",
        "--xm-font": _FONT_SERIF,
        "--xm-radius-xs": "3px", "--xm-radius-sm": "4px", "--xm-radius-md": "6px",
        "--xm-radius-lg": "10px", "--xm-radius-full": "4px",
        "--xm-card-shadow": "0 2px 6px rgba(43,29,14,0.08)",
    },
    "gradio": _gradio("#fffbf0", "#f6eedb", "#f0e6c8", "#2b1d0e", "#8d7d6b", "#c9b99a",
                      "#b91c1c", "#fff8e6", "#b91c1c", "#b91c1c", "#fff8e6"),
}

# ── 6. 跟随系统（浅色 = 默认，深色 = 野兽风深色）────────────────────────
THEMES["system"] = {
    "id": "system",
    "name": "跟随系统",
    "tag": "Auto",
    "source": "本项目组合：默认（浅） + 野兽风深色（@media prefers-color-scheme: dark）",
    "desc": "系统/浏览器是深色就用深色，否则用默认浅色；不需要手动切。",
    "scheme": "auto",
    "vars": dict(THEMES["default"]["vars"]),
    "gradio": dict(THEMES["default"]["gradio"]),
    "_dark_vars": dict(THEMES["dark"]["vars"]),
    "_dark_gradio": dict(THEMES["dark"]["gradio"]),
}

DEFAULT_ID = "default"
THEME_IDS: tuple[str, ...] = ("default", "beast", "dark", "animal", "wenyang", "system")


def normalize(theme_id) -> str:
    """把任意值收敛成合法主题 id（未知/空 → 默认主题）。"""
    tid = str(theme_id or "").strip().lower()
    return tid if tid in THEMES else DEFAULT_ID


def get(theme_id) -> dict:
    return THEMES[normalize(theme_id)]


def list_themes() -> list[dict]:
    """按 THEME_IDS 顺序返回主题（供设置页渲染卡片）。"""
    return [THEMES[t] for t in THEME_IDS]


def resolved_vars(theme_id) -> dict:
    """主题完整变量表（测试与文档用；含 Gradio 变量）。"""
    th = get(theme_id)
    out = dict(th["vars"])
    out.update(th.get("gradio") or {})
    return out


def missing_tokens(theme_id) -> list[str]:
    """缺哪些必需 token（测试用；空列表 = 完整）。"""
    th = get(theme_id)
    return [t for t in REQUIRED_TOKENS if t not in th["vars"]]


def _decl_block(vars_map: dict) -> str:
    return "\n".join("  %s: %s;" % (k, v) for k, v in vars_map.items())


_SCOPE = ("html:root,\nhtml:root .gradio-container,\nhtml:root .dark,\nhtml:root body")


def theme_css(theme_id=None) -> str:
    """生成该主题的 CSS 变量块（注入 <style> 后立即生效）。

    · 作用域带 `html:root` 前缀，确保盖住 Gradio 自带的 `.dark` 覆盖；
    · `color-scheme` 让原生滚动条 / 表单控件跟随主题；
    · `system` 主题额外输出 `@media (prefers-color-scheme: dark)` 深色分支。
    """
    th = get(theme_id)
    scheme = th.get("scheme", "light")
    light_map = dict(th["vars"], **th.get("gradio", {}))
    if th.get("_dark_vars"):
        dark_map = dict(th["_dark_vars"], **th.get("_dark_gradio", {}))
        dark_block = "\n".join("  " + ln for ln in _decl_block(dark_map).split("\n"))
        return ("/* %s · 浅色分支 */\n%s {\n  color-scheme: light;\n%s\n}\n"
                "/* %s · 深色分支 */\n@media (prefers-color-scheme: dark) {\n%s {\n"
                "  color-scheme: dark;\n%s\n  }\n}\n") % (
                    th["name"], _SCOPE, _decl_block(light_map),
                    th["name"], _SCOPE, dark_block)
    css_scheme = {"light": "light", "dark": "dark"}.get(scheme, "light")
    return "/* %s · %s */\n%s {\n  color-scheme: %s;\n%s\n}\n" % (
        th["name"], th.get("source", ""), _SCOPE, css_scheme, _decl_block(light_map))


def theme_style_tag(theme_id=None, brand=None, theme_label=None) -> str:
    """可直接塞进 gr.HTML 的 <style> 标签（换主题时重新渲染即生效）。

    brand / theme_label 给左侧边栏的品牌区用：写入 `--xm-nav-brand`，
    由 ui_theme 的 `#main-nav > .tab-wrapper::before` 消费（多行在 content 里用 CSS 换行转义）。
    """
    th = get(theme_id)
    css = theme_css(th["id"])
    if brand:
        lines = [str(brand)]
        if theme_label:
            lines.append("当前主题：%s" % theme_label)
        css += 'html:root { --xm-nav-brand: "%s"; }\n' % "\\A ".join(lines)
    return ('<style id="xm-theme-vars" data-theme-id="%s">\n%s</style>' %
            (th["id"], css))


def swatches(theme_id) -> list[str]:
    """卡片预览用的三个色（画布 / 主操作 / 文字），全部取自主题变量，不另造色。"""
    v = get(theme_id)["vars"]
    out = []
    for key in ("--xm-canvas", "--xm-primary", "--xm-ink"):
        val = str(v.get(key, "#ffffff"))
        out.append(val if val.startswith("#") else "#ffffff")
    return out


def apply_to_static_css(css: str, theme_id=None) -> str:
    """把主题变量块拼进静态 CSS（首屏即带上当前主题，避免闪烁）。"""
    return theme_css(theme_id) + css
