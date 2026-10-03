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
- **导航** 采用 `segmented-tab` 语义：未激活 `steel`，激活 `ink` + `2px` 底部描边；图标 monochrome 随文字色。

## 5. 图标

- **monochrome line icon / 统一符号体系**，同一视觉族、单色、随文字颜色继承（默认 muted、激活 ink）。
- **不使用彩色 Emoji、不使用 AI sparkle / robot / brain 图标**。
- 受 Gradio `gr.Tab` 无 `icon` 参数限制，导航图标采用**同族几何符号**（非 Emoji、无外链、无新依赖）；页面内小图标优先 inline SVG。

## 6. 响应式

| 断点 | 关键变化 |
|---|---|
| ≥1280px | 完整版式，1280px 容器 |
| 1024–1279px | 卡片 2 列 |
| 768–1023px | 卡片 1–2 列，表格允许横向滚动 |
| <768px | 单列；按钮/输入保持 ≥40/44px 触达高度 |

表格窄屏允许横向滚动；不出现溢出/错位。

## 7. 信息架构（属于小满，与 Notion 无关）

七页：今天该进什么货 / 为什么这样进 / 今天生意怎么样 / 它学会了什么 / 店里的老账本 / 实验验证 / 项目说明。
**首页不是 Dashboard**——顺序为：经营状态 → 今日提醒 → 下一次补货条件 → 本次补货建议 → 重点关注 → 完整清单 →（行内）查看原因。

