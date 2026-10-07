# -*- coding: utf-8 -*-
"""小满 · 「它学会了什么」经营经验页（UI v2，遵循 DESIGN.md）。

把真实学习闭环组织成店主能看懂的内容：
  真实经营反馈 → 形成经营经验 → 调整策略/决策 → 以后补货参考
只用现有真实 Memory / evolution 数据，不制造案例、不宣称「自动学习模型」。

本模块只负责**页面表达**，不碰任何业务逻辑：
  · 经验何时形成、是否触发策略校准，完全由 core.evolution 决定；
  · 所有文案只描述代码当前真实具备的能力 —— demo-store 当前 experiences /
    evolution_log 为空时，页面如实显示「还没有形成经营经验」，不伪造记录。
"""

from . import memory

LEARN_CSS = """
/* 经营经验卡：document-style，紧凑行，subtle divider */
.lx-exp { background:var(--xm-canvas); border:1px solid var(--xm-hairline);
  border-radius:var(--xm-radius-lg); padding:var(--xm-space-lg); margin-bottom:var(--xm-space-md); }
.lx-exp-h { display:flex; align-items:center; gap:8px; margin-bottom:10px; flex-wrap:wrap; }
.lx-exp-name { font-size:15px; font-weight:600; color:var(--xm-ink); }
.lx-exp-day { font-size:13px; color:var(--xm-steel); margin-left:auto; }
.lx-exp-rows > div { font-size:14px; line-height:1.8; color:var(--xm-charcoal); padding:2px 0; }
.lx-exp-rows .k { color:var(--xm-slate); }
/* 真实空状态 */
.lx-empty { background:var(--xm-surface-soft); border:1px dashed var(--xm-hairline-strong);
  border-radius:var(--xm-radius-lg); padding:28px 24px; text-align:center; }
.lx-empty p { font-size:14px; color:var(--xm-slate); line-height:1.9; margin:6px 0; }
/* 自进化闭环流程线（轻量，monochrome，无 emoji / 动画） */
.lx-flow { display:flex; align-items:center; gap:10px; flex-wrap:wrap;
  margin-top:var(--xm-space-lg); padding-top:var(--xm-space-md);
  border-top:1px solid var(--xm-hairline-soft); font-size:14px; }
.lx-flow .step { color:var(--xm-charcoal); }
.lx-flow .arr { color:var(--xm-stone); font-weight:600; }
"""


def render_head() -> str:
    return ('<div class="xm-page">'
            '<div class="xm-h1">它学会了什么</div>'
            '<div class="xm-sm" style="margin-top:6px">'
            '小满会从每天真实经营结果里，慢慢记住这家店的规律。</div>'
            '%s'
            '</div>' % render_demo_notice())


def render_demo_notice() -> str:
    """演示数据标识：明确告知这些经验来自模拟经营历史，非现实商户采集。

    数据来源是 seed_demo_history.py 写入的「演示门店 · 模拟经营历史」，
    经验本身由 core/evolution.py 的正常业务逻辑生成 —— 这里只做来源标注。
    """
    return ('<div class="xm-callout" style="margin-top:10px">'
            '<b>演示门店 · 模拟经营历史</b>　'
            '本页经验来自项目自带的仿真数据集，用于演示小满的学习闭环，'
            '并非现实门店采集的数据。'
            '</div>')


def render_learn_page() -> str:
    """展示真实经营经验；无记录时返回真实空状态。

    经验来自 memory.get_experiences；可追踪的策略变化来自 memory.get_evolution_log，
    二者按 (day, sku) 关联（反馈 → 经验 → 后续变化 的闭环链路）。
    """
    exps = memory.get_experiences(limit=200)
    names = {p['sku']: p['name'] for p in memory.get_products()}
    if not exps:
        return render_empty() + render_flow()

    evo = {(e['day'], e['sku']): e for e in memory.get_evolution_log(limit=1000)}
    cards = ''.join(_render_exp(e, names.get(e['sku'], e['sku']), evo) for e in exps[:20])
    n_eff = sum(1 for e in exps[:20] if (e['day'], e['sku']) in evo)
    sub = ''
    if n_eff:
        sub = ('<div class="xm-cap" style="margin:-2px 0 10px">'
               '其中 %d 条已经真实影响了后续的补货建议。</div>' % n_eff)
    body = ('<div class="xm-sec"><div class="xm-sec-title">最近学到的经营经验</div>'
            '%s%s</div>' % (sub, cards))
    return body + render_flow()


def render_empty() -> str:
    return ('<div class="lx-empty">'
            '<div class="xm-h3" style="margin:0 0 8px;color:var(--xm-ink)">还没有形成经营经验</div>'
            '<p>记录几天真实销售、断货或损耗后，小满会慢慢总结这家店的规律。</p>'
            '<p class="xm-cap">下方的「去记录经营情况 →」可以跳到录入页。</p>'
            '</div>')


def render_flow() -> str:
    """页面底部：一句流程，说明自进化闭环（不堆四张巨型卡片）。"""
    return ('<div class="lx-flow">'
            '<span class="step">经营结果</span><span class="arr">→</span>'
            '<span class="step">记进老账本</span><span class="arr">→</span>'
            '<span class="step">总结经验</span><span class="arr">→</span>'
            '<span class="step">影响以后补货</span>'
            '</div>')


def _render_exp(e: dict, nm: str, evo: dict) -> str:
    """单条经验：发生了什么 → 小满记住了什么 → 以后会怎样参考。

    内容全部取真实字段；若确实产生了策略变化（evolution_log 有同 (day,sku) 记录），
    才补一句「已影响后续补货 + 安全库存系数变化」，否则只说「记下来、没触发调整」。
    """
    sig = e.get('signal') or ''
    sold = float(e.get('qty_sold') or 0)
    if sig == '断货':
        happen = '实际卖出 %.0f，断货 %.0f' % (sold, float(e.get('qty_stockout') or 0))
    else:
        happen = '实际卖出 %.0f，报损 %.0f' % (sold, float(e.get('qty_spoilage') or 0))

    badge = ('<span class="xm-badge xm-badge-red">断货</span>' if sig == '断货'
             else '<span class="xm-badge xm-badge-orange">积压损耗</span>')
    lesson = e.get('lesson') or sig
    adjust = e.get('adjustment') or ''

    ev = evo.get((e['day'], e['sku']))
    if ev:
        o = float(ev.get('old_value') or 0)
        nw = float(ev.get('new_value') or 0)
        change = '把安全库存系数从 %.2f %s到 %.2f' % (o, '上调' if nw > o else '下调', nw)
        change_tail = (' <span class="xm-cap">（已影响后续补货：%s）</span>' % change)
    else:
        change_tail = ' <span class="xm-cap">（本次只记下来，还没触发策略调整）</span>'

    return ('<div class="lx-exp">'
            '<div class="lx-exp-h"><span class="lx-exp-name">%s</span>%s'
            '<span class="lx-exp-day">%s</span></div>'
            '<div class="lx-exp-rows">'
            '<div><span class="k">当时发生了什么：</span>%s</div>'
            '<div><span class="k">小满记住了什么：</span>%s</div>'
            '<div><span class="k">以后会怎样参考：</span>%s%s</div>'
            '</div></div>' % (nm, badge, e.get('day', ''), happen, lesson, adjust, change_tail))
