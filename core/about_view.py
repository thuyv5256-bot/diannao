# -*- coding: utf-8 -*-
"""小满 · 「项目说明」页（v2；产品叙事优先，遵循 DESIGN.md）。

第一屏回答"解决什么问题 / 怎么解决"，技术实现放到后面。
样式只消费 --xm-* token 与共享 .xm-* 组件（颜色定义在 core/themes.py），本页不再自带颜色。
"""

# 本页无需自有样式：结构全部用共享组件（.xm-page / .xm-card / .xm-callout / .xm-table）
ABOUT_CSS = ""


def render_about():
    hero = ('<div class="xm-page">'
            '<div class="xm-h1">小满 · 智能补货</div>'
            '<div class="xm-sm" style="margin-top:6px">面向社区小店的智能补货 Agent</div>'
            '</div>')
    problem = ('<div class="xm-sec"><div class="xm-sec-title">小满解决什么问题</div>'
               '<div class="xm-callout">社区夫妻小店缺少专业数据分析能力，补货依赖经验，'
               '容易出现积压损耗或刚需商品断货。</div></div>')
    caps = [
        ("会算", "根据真实销量、库存和经营事件，给出这个决策日的补货建议。"),
        ("会记", "从每天的真实经营反馈中，积累这家店自己的经验。"),
        ("会权衡", "不只考虑利润，也考虑库存风险和民生商品保障。"),
    ]
    how = ('<div class="xm-sec"><div class="xm-sec-title">小满怎么解决</div>'
           '<div class="xm-kv-row">%s</div></div>'
           % ''.join('<div class="xm-card" style="flex:1;min-width:150px;margin-bottom:0">'
                     '<div class="xm-h3">%s</div>'
                     '<div class="xm-note" style="margin-top:6px">%s</div></div>' % (b, s)
                     for b, s in caps))
    rows = [
        ("需求预测", "指数衰减加权平均 × 星期效应 × 节日因子；断货日销量还原为潜在需求再学习。"),
        ("R³ 多目标决策", "收益 + 韧性 + 民生，两阶段整数优化；民生兜底优先锁定。"),
        ("记忆与自进化", "SQLite 长期记忆；按真实经营反馈对备货做有上下限的小幅校准，防震荡。"),
        ("长期实验", "180 天 Digital Store 对照实验，结果冻结在「实验验证」页，可复现。"),
    ]
    body = ''.join('<tr><td><b>%s</b></td><td>%s</td></tr>' % (m, d) for m, d in rows)
    tech = ('<div class="xm-sec"><div class="xm-sec-title">技术实现</div>'
            '<table class="xm-table"><tr><th>模块</th><th>做法</th></tr>%s</table></div>' % body)

    # ── 数据与设计边界（诚实披露，避免越界宣称）──
    limits = [
        ("演示用的是仿真数据",
         "180 天社区小店数字经营仿真数据，不是现实商户的POS 采集数据。"
         "原始 CSV 记录逐日销量与天气事件，<b>不包含真实断货 / 报损标签</b>。"),
        ("缺货如何产生",
         "统一模拟器在相同潜在需求下，由各算法自己的库存状态反推："
         "卖出 = min(潜在需求, 可售库存)，未满足 = 潜在需求 − 卖出。"
         "库存与损耗由批次 FEFO 与保质期逐日推演，不是采集值。"),
        ("结论的适用范围",
         "未满足需求降低 61.27%、民生 unmet 降低 73.02%、经营毛利提高 4.90%，"
         "是在<b>完全相同的模拟条件</b>下与传统补货方法的对照结果，"
         "属模拟实验，<b>不是</b>已在真实门店的实地验证。"),
        ("AI 影响幅度是安全边界",
         "实测高温场景需求乘数 1.40、春节 1.80，均为当前上限。"
         "大模型负责判断风险方向与强弱，超过可信范围的影响由系统截断，"
         "最终补货数量仍只由预测与 R³ 决定 —— 宁可保守，也不允许模型放大需求。"),
        ("部署形态",
         "面向单个社区小店的本地 / 轻量 Web 原型：数据存在本机，"
         "没有多租户隔离与生产级高可用设计。"),
    ]
    limits_html = (
        '<div class="xm-sec"><div class="xm-sec-title">数据与设计边界</div>'
        '<div class="xm-note" style="margin-bottom:10px">'
        '以下是这个系统<b>做不到</b>的事，先说清楚比事后解释更可靠。</div>'
        '<table class="xm-table"><tr><th>边界</th><th>说明</th></tr>%s</table></div>'
        % ''.join('<tr><td><b>%s</b></td><td>%s</td></tr>' % (k, v)
                  for k, v in limits))
    return hero + problem + how + tech + limits_html
