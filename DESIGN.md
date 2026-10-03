# 小满 UI Design System v2

> 视觉组件体系来自 **VoltAgent/awesome-design-md · design-md/notion/DESIGN.md**（Notion 产品级视觉语言）。
> 信息架构与业务语义属于**小满 · 社区小店智能补货助手**；本文档不引入任何 Notion 品牌元素。
> 旧视觉规范已备份为 `DESIGN.legacy.md`（不再作为主要依据）。

## 0. 适配原则

- 只复用 Notion 的**产品级视觉语言**（tokens / 层级 / 密度 / 边框 / 状态），**不复制其官网营销结构**。
- 明确剔除：巨型 Hero 带、定价卡、logo wall、testimonial、深色营销 band、彩色 feature 卡阵列、任何 Notion 品牌名/Logo。
- 业务状态颜色**服从店真实语义**（见 §3 语义映射），不为"像 Notion"而滥用紫色。

## 1. 色彩 Tokens

```
/* 画布与表面 */
--xm-canvas:          #ffffff
--xm-surface:         #f6f5f4
--xm-surface-soft:    #fafaf9
--xm-hairline:        #e5e3df
--xm-hairline-soft:   #ede9e4
--xm-hairline-strong: #c8c4be

/* 文字 */
--xm-ink:      #1a1a1a
--xm-charcoal: #37352f
--xm-slate:    #5d5b54
--xm-steel:    #787671
--xm-stone:    #a4a097
--xm-muted:    #bbb8b1

/* 主操作（沿用 Notion primary 作主 CTA） */
--xm-primary:         #5645d4
--xm-primary-pressed: #4534b3
--xm-on-primary:      #ffffff
--xm-link:            #0075de

/* 语义（按小满业务重新指派，见 §3） */
--xm-success: #1aae39
--xm-warning: #dd5b00
--xm-error:   #e03131
/* 语义软底色（tint） */
--xm-success-soft: #d9f3e1
--xm-warning-soft: #ffe8d4
--xm-error-soft:   #fde0ec
--xm-info-soft:    #dcecfa
```

## 2. 字体 / 圆角 / 间距

**字体栈（中文安全回退，不依赖 Notion Sans）**
```
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
             "PingFang SC", "Microsoft YaHei", "Noto Sans SC", system-ui, sans-serif;
```

**层级（取自 Notion 比值，按中文可读性收敛）**
| 用途 | 字号 | 字重 | 行高 |
|---|---|---|---|
| 页面标题 heading-2 | 28px | 600 | 1.25 |
| 区块标题 heading-4 | 22px | 600 | 1.30 |
| 卡片标题 heading-5 | 18px | 600 | 1.40 |
| 正文 body-md | 16px | 400 | 1.55 |
| 次要 body-sm | 14px | 400 | 1.50 |
| 按钮 button-md | 14px | 500 | 1.30 |
| 标签 caption-bold | 13px | 600 | 1.40 |
| 微标 micro | 12px | 500 | 1.40 |

**圆角**：`--xm-radius-xs:4px`（chip）/ `sm:6px`（tag）/ `md:8px`（按钮、输入）/ `lg:12px`（卡片）/ `full:9999px`（状态徽标、pill）。**按钮用 md(8px) 矩形，不用胶囊。**
**间距**：4/8/12/16/20/24/32/40（`--xm-space-xxs … --xm-space-xxxl`）；区块间距 24–32px，卡片内边距 16–20px。
**容器**：内容最大宽度 **1280px**，左右 32px。

## 3. 语义映射（Notion 色 → 小满业务语义）

| 小满语义 | 用色 | 场景 |
|---|---|---|
| 主操作 primary | `--xm-primary` #5645d4 | 重新生成进货建议等**唯一主按钮** |
| 链接/次级动作 link | `--xm-link` #0075de | 查看原因、跳转等文字动作 |
| 民生保障正常 / 保存成功 | `--xm-success` + `--xm-success-soft` | 民生标签、提交成功 |
| 高温 / 暴雨 / 库存风险 | `--xm-warning` + `--xm-warning-soft` | 风险徽标、库存紧张 |
| 断货 / 严重风险 | `--xm-error` + `--xm-error-soft` | 断供、严重缺货 |
| 次级信息 / 中性 | `--xm-surface-soft` + `--xm-steel` | 说明文字、次要行 |

**不使用**：Notion 紫色做大面积背景 / 正文；营销用彩色 feature 卡阵列。

## 4. 组件（小满 v2 class）

- **按钮** `.xm-btn` + `.xm-btn-primary`（primary 底白字，md 圆角，10px 18px）/ `.xm-btn-secondary`（透明底 + hairline-strong 边框）/ `.xm-btn-ghost`（透明，8px 12px）/ `.xm-btn-link`（link 蓝文字，无边框）。高度统一 40px。
- **输入** `.xm-input`：白底、`1px solid hairline-strong`、md 圆角、高 44px；聚焦 `2px solid primary`。
- **卡片** `.xm-card`：白底、`1px solid hairline`、lg 圆角、20px 内边距，**无阴影**；强调模块用 `.xm-card-tint`（surface 底）。
- **徽标** `.xm-badge`（full 圆角、13px/600、2px 8px，胶囊）+ `.xm-badge-green/-orange/-red/-neutral`。
- **数据表** `.xm-table`：白底、hairline 边框、md 圆角；表头 `--xm-surface` 底、13px/600、steel 文字；行 `16px 20px` 内边距、底部 `1px hairline-soft` 分隔；文字 14px。
- **折叠** `.xm-acc`：白底、底部 `1px hairline` 分隔，`summary` 为 16px/500 ink。
- **区块** `.xm-sec` + `.xm-sec-title`（22px/600）。
- **导航（左侧边栏）**：应用外壳为「左栏 236px + 右栏自适应」。左栏是一张 `.xm-card` 语义的侧边栏（背景 `--xm-sidebar-bg`、描边 `--xm-sidebar-border`、圆角 lg、阴影 `--xm-card-shadow`），内含品牌区（应用名 + 当前主题）与竖排菜单；菜单项高 38px、md 圆角，未激活用 `--xm-sidebar-muted`，激活用 `--xm-sidebar-active-bg/-fg`。**不使用彩色 Emoji 图标**，激活态靠底色与字重区分。
  - 实现注意：Gradio 6 的 `gr.Tabs` 会把放不下的标签折叠成「More tabs」下拉，因此**隐藏其自带 `.tab-wrapper`**，导航改用 `gr.Radio#xm-nav`（点击 → `gr.Tabs(selected=…)`）；详见 [docs/TRD.md](docs/TRD.md) §7.2。

## 5. 图标

- **monochrome line icon / 统一符号体系**，同一视觉族、单色、随文字颜色继承（默认 muted、激活 ink）。
- **不使用彩色 Emoji、不使用 AI sparkle / robot / brain 图标**。页面内事件/状态一律用 `.xm-badge`（语气色 + 中文名）或 `.xm-callout` 表达；分区标题用 `.xm-sec-title`（大节）与 `.xm-h3`（卡内小标题），不再用 `###`+emoji 的 Markdown 标题。
- 放行的单色符号仅限：`✓ ✗ ★ ↑ ↓ → › ·`（状态、增减、指引），其余 emoji 由 `tests/test_ui_consistency.py` 直接拦下。
- 受 Gradio `gr.Tab` 无 `icon` 参数限制，导航图标采用**同族几何符号**（非 Emoji、无外链、无新依赖）；页面内小图标优先 inline SVG。

## 6. 响应式

| 断点 | 关键变化 |
|---|---|
| ≥1280px | 完整版式，1280px 容器 |
| 1024–1279px | 卡片 2 列 |
| 768–1023px | 卡片 1–2 列，表格允许横向滚动 |
| <768px | 单列；按钮/输入保持 ≥40/44px 触达高度 |
| ≤900px | **左侧边栏折叠为顶部横排菜单**（`#xm-shell` 转纵向，`#xm-nav` 换行排列） |

表格窄屏允许横向滚动；不出现溢出/错位。

## 7. 信息架构（属于小满，与 Notion 无关）

八页（左侧边栏自上而下）：今天该进什么货 / 为什么这样进 / 今天生意怎么样 / 它学会了什么 / 店里的老账本 / 实验验证 / 项目说明 / **设置**（外观主题 + 运行环境）。
**首页不是 Dashboard**——顺序为：经营状态 → 今日提醒 → 下一次补货条件 → 本次补货建议 → 重点关注 → 完整清单 →（行内）查看原因。

## 8. 主题系统（v2.1 新增）

**唯一实现**：`core/themes.py`（变量与取值）+ `core/ui_theme.py`（组件类）。机制与 CodeForge 的
ADR-005 同构 —— **CSS 变量作用域覆盖**：默认主题零改动，其他主题只覆盖变量。

| 主题 | 来源 | 关键特征 |
|---|---|---|
| 小满默认 | 本项目（原 DESIGN.md v2 token） | 白底、紫主操作、无阴影、1px 描边 |
| 野兽风 · 浅色 | CodeForge `styles/global.css`（Neo-Brutalist） | 黑描边 2px、硬投影、明黄侧边栏 |
| 野兽风 · 深色 | CodeForge `styles/dark-theme.css` | 近黑底 + 品牌黄，硬投影 |
| 森友会 | CodeForge `styles/animal-theme.css` | 薄荷绿/奶油黄/暖棕，大圆角 + 3D 底部投影 |
| 纹样 · 宣纸 | CodeForge `styles/wenyang-theme.css` | 宣纸米黄 + 墨字 + 朱砂红，宋体、小圆角、深墨侧边栏 |
| 跟随系统 | 本项目组合 | `@media (prefers-color-scheme: dark)` 自动切到野兽风深色 |

**规则（改主题前必读）**

1. 颜色 / 字体 / 圆角 / 描边强度 / 阴影**只允许**定义在 `core/themes.py` 与 `core/ui_theme.py`；页面与视图模块一律消费 `--xm-*`，禁止写死颜色。
2. 每个主题必须覆盖 `themes.REQUIRED_TOKENS` 全部 token（漏一个就会露出默认色）——由 `tests/test_themes.py` 强制。
3. 主题还要覆盖一组 Gradio 原生变量（`--body-background-fill` 等），否则 Dataframe/Dropdown/Accordion 会留在 Gradio 默认配色。
4. 换主题**不刷新页面**：设置页选中后重新渲染一个隐藏的 `<style>` 组件即可；选择持久化在 `data/ui_settings.json`。
5. 主题不得改变信息层级、间距与内容 —— 只影响观感，绝不影响任何计算结果。
6. **图表也要跟主题**：plotly 的底色/字色是**服务端渲染时烘进图里的**，改 CSS 变量不会影响已生成的图。所有图表统一 `fig.update_layout(**themes.plotly_layout(ACTIVE_THEME))`（色值用 `themes.palette(ACTIVE_THEME)`，plotly 不认 CSS 变量）；换主题时由 `apply_theme` 一并重画当前演进曲线，按需生成的评测/仿真图在生成时取当前主题。

