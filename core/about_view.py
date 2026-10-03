# -*- coding: utf-8 -*-
"""小满 · 「项目说明」页（v2；产品叙事优先，遵循 DESIGN.md）。

第一屏回答"解决什么问题 / 怎么解决"，技术实现放到后面。
样式只消费 --xm-* token 与共享 .xm-* 组件（颜色定义在 core/themes.py），本页不再自带颜色。
"""

# 本页无需自有样式：结构全部用共享组件（.xm-page / .xm-card / .xm-callout / .xm-table）
ABOUT_CSS = ""


def render_about():
    hero = ('<div class="xm-page">'
            '<div class="xm-h1">小满 · 社区小店智能补货助手</div>'
            '<div class="xm-sm" style="margin-top:6px">面向社区小店的自进化智能补货 Agent</div>'
            '</div>')
    problem = ('<div class="xm-sec"><div class="xm-sec-title">小满解决什么问题</div>'
               '<div class="xm-callout">社区夫妻小店缺少专业数据分析能力，补货依赖经验，'
               '容易出现积压损耗或刚需商品断货。</div></div>')
    caps = [
        ("会算", "根据真实销量、库存和经营事件，给出今天的补货建议。"),
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
    return hero + problem + how + tech
