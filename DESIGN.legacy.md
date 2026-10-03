# 小满 · 设计文档（DESIGN）
# 小满 · UI Design System v1.0

> 产品定位：
> 面向社区小店经营者的智能补货与经营助手。
>
> 核心设计原则：
> 小满首先应该像一款真实、成熟、每天能使用的社区小店经营工具，
> 其次用户才会发现它背后拥有 Agent、R³、Memory 等智能能力。
>
> AI 应存在于能力中，而不是浮在视觉表面。

---

# 01. Brand Personality

小满的产品气质：

- 亲切，但不幼稚
- 专业，但不冰冷
- 智能，但不炫技
- 数据驱动，但不做复杂 Dashboard
- 有民生温度，但不过度煽情
- 像经营工具，而不是 AI Demo
- 像成熟产品，而不是比赛 PPT

关键词：

Community / Retail / Calm / Trust / Warm / Practical

中文：

社区感 × 经营感 × 温暖 × 克制 × 可信

---

# 02. Product Design Philosophy

## 2.1 AI invisible by default

日常经营页面不主动强调：

- AI
- Agent
- 大模型
- Memory
- R³
- Algorithm
- seed
- FINAL
- metrics

这些概念应该存在于：

- 为什么这样建议
- 它学会了什么
- 实验验证
- 项目说明

用户首先看到的是：

“今天发生了什么？”
“什么东西快没货？”
“应该进多少？”
“为什么？”
“要花多少钱？”

而不是：

“AI 使用了什么技术？”

---

# 03. Visual Direction

整体参考成熟的生产力工具和中国商家端产品的信息组织方式。

吸收：

- Notion 式克制的信息层级
- 中国商家小程序的任务导向
- 本地生活产品的亲切感
- 进销存工具的高效率
- 小满自己的民生属性

不是照抄任何现有产品。

---

# 04. Color System

## Background

Page Background:
#F7F8F6

Primary Surface:
#FFFFFF

Secondary Surface:
#F2F5F3

Subtle Highlight:
#F6F8FA

Divider / Border:
#E5E9EC

## Brand

Primary:
#234E70

Primary Hover:
#1C405D

Primary Soft:
#EAF1F5

## Responsibility / Essential Goods

Essential Green:
#3F7D5A

Essential Soft:
#EDF6F0

## Warning

Warning:
#D98B2B

Warning Soft:
#FFF6E8

## Danger

Danger:
#C94A45

Danger Soft:
#FDEEEE

## Text

Primary Text:
#1F2933

Secondary Text:
#66737F

Muted Text:
#8A959E

Disabled Text:
#AAB2B9

Do NOT introduce purple/blue AI gradients.

---

# 05. Typography

Use system Chinese sans-serif stack.

Preferred:

- PingFang SC
- Microsoft YaHei
- Noto Sans SC
- system-ui
- sans-serif

Do not use decorative futuristic fonts.

Hierarchy:

Page Title:
24–28px
font-weight: 700

Large Business Number:
28–36px
font-weight: 700

Section Title:
18–20px
font-weight: 600

Card Title:
16px
font-weight: 600

Body:
14–16px
font-weight: 400

Secondary:
13–14px

Caption:
12px

Line height should remain generous.

Do not make every number oversized.

---

# 06. Spacing

Base spacing unit:

4px

Preferred spacing scale:

4
8
12
16
20
24
32
40
48

Page horizontal padding:

Desktop:
32–40px

Mobile:
16px

Section spacing:

24–32px

Card internal padding:

16–20px

Avoid giant empty areas.

Avoid cramming information together.

---

# 07. Radius

Small controls:
6px

Standard card:
8px

Important card:
10px

Large container:
12px

Pill / Tag:
999px

Do not make every container 20–30px rounded.

---

# 08. Shadows

Shadows should be extremely subtle.

Default cards should preferably use:

background + border + spacing

instead of shadow.

If shadow is necessary:

0 2px 8px rgba(31,41,51,0.05)

Never use:

- glow
- neon shadow
- colored shadow
- glassmorphism

---

# 09. Navigation

Navigation should feel like a normal business application.

Desktop navigation:

今天进货
生意情况
为什么这样进
它学会了什么
老账本
实验验证

Do not use Emoji as primary navigation icons.

If icons are used:

use one consistent linear icon family.

Active state:

- brand color text
- subtle underline or subtle background

Do not use large colorful navigation pills.

---

# 10. Home Page Principle

Homepage is NOT a dashboard.

Homepage is:

“今天店主应该做什么？”

Information priority:

1. 今日经营提醒
2. 今日进货建议
3. 需要优先处理的商品
4. 民生商品保障状态
5. 为什么这样建议
6. Secondary business metrics

Do not start with four generic KPI cards.

---

# 11. Homepage Hero

Avoid giant marketing hero banners.

Preferred:

小满
10月2日 · 周五

下午好，今天有 3 件事值得留意

Then immediately enter actionable information.

The brand does not need to repeatedly say:

“自进化智能补货 Agent”

That belongs in project introduction.

---

# 12. Daily Brief

Use a compact business brief.

Example structure:

今日提醒

[Warning]
矿泉水明天可能紧张
预计需求增加，建议今天提前补货

[Success]
民生商品保障正常
19种民生商品达到最低保障要求

[Info]
今天没有供应商异常

Each item contains:

icon/status + title + one-line reason

No large card per alert.

---

# 13. Primary Action Card

One primary business decision can be visually emphasized.

Example:

今日建议进货

¥599

预计毛利 ¥297
民生保障 100%

[查看进货清单]

Only ONE primary CTA should dominate a screen region.

---

# 14. Product List

Prefer list/table hybrid instead of oversized cards.

Example:

矿泉水
民生 · 需求上升

现有 72瓶
预计明日 33.8瓶

建议进货                       84瓶
约够 4.6 天                     >

Rows should be easy to scan.

Essential goods use subtle green tags.

Risk products use warning colors only where needed.

Do not paint the entire row red/orange.

---

# 15. Status Tags

Examples:

民生
库存紧张
需求上升
正常
可能断货
参考历史经验

Tags should:

- use soft background
- have restrained saturation
- use small typography
- communicate status

Do not use tags as decoration.

---

# 16. Buttons

Primary button:

brand background
white text
8px radius

Secondary:

white background
border
primary text

Text action:

no container unless needed

Avoid multiple competing primary buttons.

Button copy should be action-oriented:

查看进货单
查看原因
提交今日经营情况
查看实验结果

Avoid:

帮我算算
让AI分析
AI智能生成

---

# 17. Human Language

Translate system language into merchant language.

Prefer:

Agent 今日判断
→ 今日提醒

Forecast
→ 预计需求

Event
→ 今日情况

Memory 命中
→ 参考了过去经验

R³ 权衡
→ 为什么这样建议

Policy Adjustment
→ 建议调整

Spoilage
→ 损耗

Formal Experiment
→ 实验验证

Technical terminology may appear in secondary explanations.

---

# 18. Explainability Page

The explainability page answers:

“为什么让我进这么多？”

Keep existing real six-stage decision chain:

1. 看环境
2. 算需求
3. 翻老账
4. 查库存
5. 做权衡
6. 给结论

But visually present it as a natural decision process,
not an AI reasoning transcript.

Top:

为什么建议进 84 瓶矿泉水？

Short conclusion first.

Then detailed evidence.

Never expose chain-of-thought or internal hidden reasoning.
Only show structured decision evidence already generated by the system.

---

# 19. Memory Page

Do not make Memory feel like an AI feature showcase.

Page question:

“小满从过去经营中学到了什么？”

Preferred language:

过去发生过什么
→ 店里记住了什么
→ 后来遇到类似情况
→ 建议发生了什么变化

Show real historical evidence.

Never manufacture a successful Memory case.

Empty state should feel intentional:

“还没有形成这类经营经验。
记录几天实际销售后，小满会逐渐总结规律。”

---

# 20. Ledger

“老账本” should visually resemble historical business records.

Focus:

- date
- product
- event
- sales
- stockout
- spoilage
- outcome

Avoid AI styling.

Tables should use:

clear header
subtle zebra/background
reasonable row height
sticky header when necessary

---

# 21. Experiment Validation

This is the only page allowed to feel more research-oriented.

It may display:

R³
Memory A/B
Traditional
seed
180 days
metrics
reproducibility information

But still follow the same visual system.

Information order:

Question
→ Key finding
→ Visual evidence
→ Detailed table
→ Experiment setup

Do not begin with implementation terminology.

---

# 22. Experimental Integrity

Never visually hide unfavorable results.

Never imply superiority where data does not show it.

No:

- 综合评分
- AI评分
- 排名
- “全面领先”
- “完胜传统算法”

For Spoilage Control A/B:

If ON/OFF remain equal, state neutrally:

“当前180天基准环境下，未观察到损耗控制开关带来的可测增量。”

Null results are valid experimental results.

---

# 23. Charts

Charts should be sparse.

Use charts only when they answer a clear question.

Preferred:

- simple bars
- simple lines
- paired comparison

Avoid:

- radar charts
- gauges
- 3D charts
- decorative charts
- excessive pie charts

Do not use rainbow palettes.

One chart = one message.

---

# 24. Empty States

Empty state must explain:

1. What is missing
2. Why
3. What user can do next

Example:

还没有学习记录

记录一次真实销售、断货或损耗情况后，
这里会逐渐形成店铺自己的经营经验。

[去记录今天的经营情况]

No robot illustration required.

---

# 25. Desktop & Mobile

The competition demo currently runs on desktop,
but the product should visually suggest that it can become a merchant mini-program.

Desktop:

max content width around 1180–1280px

Do not stretch content across the entire screen.

Mobile:

single-column
16px padding
bottom navigation can replace desktop top navigation
tables should transform into list cards when necessary

Do not merely shrink desktop tables.

---

# 26. AI Visual Restrictions

Do NOT use:

❌ purple-blue gradient
❌ glowing borders
❌ robot avatars
❌ floating AI orb
❌ sparkles everywhere
❌ excessive Emoji
❌ glassmorphism
❌ giant gradient hero
❌ “AI正在思考”
❌ fake chat interface
❌ every section as a rounded card
❌ every number as KPI
❌ unnecessary animations

---

# 27. Desired Impression

Within 10 seconds:

“这是给小店老板用的经营工具。”

Within 30 seconds:

“它会告诉老板今天应该进什么货，而且会解释。”

Within 60 seconds:

“它还会记住过去经营情况。”

After experiment page:

“背后的决策机制和学习效果做过长期实验验证。”

This is the intended narrative hierarchy.

---

# 28. Product Signature

The intelligence of 小满 should be expressed through:

- better prioritization
- clear recommendations
- understandable explanations
- memory of past events
- responsible treatment of essential goods
- evidence from long-term experiments

NOT through futuristic visual styling.

---

# 29. Final Rule

When there is a conflict between:

“looks impressive”

and

“feels like a real product”

choose:

“feels like a real product”.

When there is a conflict between:

“show more AI”

and

“help the shop owner understand what to do”

choose:

“help the shop owner understand what to do”.