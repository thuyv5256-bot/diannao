# -*- coding: utf-8 -*-
"""小满 · 「它学会了什么」经营经验页（产品化表达，遵循 DESIGN.md）。

把真实学习机制组织成店主能看懂的闭环：
发生了什么 → 店里记住了什么 → 后来再次遇到类似情况 → 建议发生了什么变化。
只用现有真实 Memory / evolution 数据，不制造案例。
"""

from . import memory

LEARN_CSS = """
.lw-lead { font-size:14px; color:#66737F; margin:6px 0 0; }
.lw-sum { background:#fff; border:1px solid #E5E9EC; border-radius:10px; padding:14px 18px; font-size:15px; color:#1F2933; }
.lw-sec-title { font-size:18px; font-weight:600; margin:22px 0 10px; }
.lw-rec { background:#fff; border:1px solid #E5E9EC; border-radius:8px; padding:14px 16px; margin-bottom:10px; }
.lw-rec-h { font-size:15px; font-weight:600; }
.lw-rec-d { font-size:12px; color:#8A959E; }
.lw-flow { margin-top:8px; font-size:13px; color:#33414F; line-height:1.9; }
.lw-empty { background:#F6F8FA; border:1px dashed #E5E9EC; border-radius:10px; padding:24px; text-align:center; color:#66737F; font-size:14px; line-height:2; }
"""


def _name_map():
    return {p['sku']: p['name'] for p in memory.get_products()}


def render_learn_page() -> str:
    exps = memory.get_experiences(limit=200)
    evo = {(e['day'], e['sku']): e for e in memory.get_evolution_log(limit=1000)}
    names = _name_map()
    lead = '<div class="lw-lead">从每天真实经营结果里，慢慢记住这家店的规律</div>'
    if not exps:
        return lead + '<div class="lw-empty">还没有形成这类经营经验。记录几天真实销售、断货或损耗后，小满会慢慢总结这家店的规律。</div>'
    n_exp = len(exps)
    n_eff = sum(1 for e in exps if (e['day'], e['sku']) in evo)
    summary = ('<div class="lw-sec-title">已经积累 %d 条经营经验</div>'
               '<div class="lw-sum">其中 <b>%d 次</b>真正影响了后续补货。</div>' % (n_exp, n_eff))
    recs = []
    for e in exps[:20]:
        nm = names.get(e['sku'], e['sku'])
        sig = e.get('signal') or ''
        sold = float(e.get('qty_sold') or 0)
        if sig == '断货':
            happen = '实际卖出 %.0f，断货 %.0f' % (sold, float(e.get('qty_stockout') or 0))
        else:
            happen = '实际卖出 %.0f，报损 %.0f' % (sold, float(e.get('qty_spoilage') or 0))
        ev = evo.get((e['day'], e['sku']))
        if ev:
            o = float(ev.get('old_value') or 0)
            nw = float(ev.get('new_value') or 0)
            change = '把安全库存系数从 %.2f %s到 %.2f' % (o, '上调' if nw > o else '下调', nw)
        else:
            change = '已记录，本次未触发策略调整'
        recs.append('<div class="lw-rec"><div class="lw-rec-h">%s <span class="lw-rec-d">%s</span></div>'
                    '<div class="lw-flow">当时发生了什么：%s<br>小满记住了什么：%s<br>后来建议怎么变化：%s</div></div>'
                    % (nm, e.get('day', ''), happen, e.get('lesson') or sig, change))
    return lead + summary + '<div class="lw-sec-title">经营经验记录</div>' + ''.join(recs)
