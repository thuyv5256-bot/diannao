# -*- coding: utf-8 -*-
"""小满 · 「项目说明」页（产品叙事优先，遵循 DESIGN.md）。

第一屏回答"解决什么问题 / 怎么解决"，技术实现放到后面。
"""

ABOUT_CSS = """
.ab-hero h1 { font-size:26px; font-weight:700; color:#234E70; margin:0; }
.ab-hero p { font-size:14px; color:#66737F; margin:6px 0 0; }
.ab-sec { font-size:18px; font-weight:600; margin:22px 0 10px; }
.ab-card { background:#fff; border:1px solid #E5E9EC; border-radius:10px; padding:16px 18px; font-size:15px; color:#33414F; line-height:1.95; }
.ab-cap { display:flex; gap:12px; margin-bottom:10px; }
.ab-cap > div { flex:1; background:#fff; border:1px solid #E5E9EC; border-radius:10px; padding:14px 16px; }
.ab-cap b { font-size:15px; color:#234E70; }
.ab-cap span { font-size:13px; color:#66737F; display:block; margin-top:5px; line-height:1.85; }
.ab-table { width:100%; border-collapse:collapse; background:#fff; border:1px solid #E5E9EC; border-radius:8px; overflow:hidden; }
.ab-table th { text-align:left; font-size:13px; color:#66737F; font-weight:600; padding:10px 12px; background:#F6F8FA; border-bottom:1px solid #E5E9EC; }
.ab-table td { padding:10px 12px; font-size:14px; border-bottom:1px solid #F2F5F3; vertical-align:top; line-height:1.85; }
"""


def render_about():
    hero = ('<div class="ab-hero"><h1>小满 · 社区小店智能补货助手</h1>'
            '<p>面向社区小店的自进化智能补货 Agent</p></div>')
    problem = ('<div class="ab-sec">小满解决什么问题</div>'
               '<div class="ab-card">社区夫妻小店缺少专业数据分析能力，补货依赖经验，'
               '容易出现积压损耗或刚需商品断货。</div>')
    how = ('<div class="ab-sec">小满怎么解决</div><div class="ab-cap">'
           '<div><b>会算</b><span>根据真实销量、库存和经营事件，给出今天的补货建议。</span></div>'
           '<div><b>会记</b><span>从每天的真实经营反馈中，积累这家店自己的经验。</span></div>'
           '<div><b>会权衡</b><span>不只考虑利润，也考虑库存风险和民生商品保障。</span></div>'
           '</div>')
    tech = ('<div class="ab-sec">技术实现</div>'
            '<table class="ab-table"><tr><th>模块</th><th>做法</th></tr>'
            '<tr><td>需求预测</td><td>指数衰减加权平均 × 星期效应 × 节日因子；断货日销量还原为潜在需求再学习。</td></tr>'
            '<tr><td>R³ 多目标决策</td><td>收益 + 韧性 + 民生，两阶段整数优化；民生兜底优先锁定。</td></tr>'
            '<tr><td>记忆与自进化</td><td>SQLite 长期记忆；按真实经营反馈对备货做有上下限的小幅校准，防震荡。</td></tr>'
            '<tr><td>长期实验</td><td>180 天 Digital Store 对照实验，结果冻结在「实验验证」页，可复现。</td></tr>'
            '</table>')
    return hero + problem + how + tech
