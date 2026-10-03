# -*- coding: utf-8 -*-
"""小满 · 「店里的老账本」经营档案页（产品化表达，遵循 DESIGN.md）。

产品定位：小满记住的这家店过去发生过什么。
只用现有真实数据（memory_stats / 历史事件 / 商品经营档案 / 供应商），不写死、不虚构。
"""

from . import analysis, memory

LEDGER_CSS = """
.lv-lead { font-size:14px; color:#66737F; margin:6px 0 14px; }
.lv-sum { display:flex; flex-wrap:wrap; gap:22px; background:#fff; border:1px solid #E5E9EC; border-radius:10px; padding:14px 18px; }
.lv-sum div { font-size:13px; color:#66737F; }
.lv-sum b { font-size:20px; font-weight:700; color:#234E70; margin-right:4px; }
.lv-sec-title { font-size:18px; font-weight:600; margin:22px 0 10px; }
.lv-table { width:100%; border-collapse:collapse; background:#fff; border:1px solid #E5E9EC; border-radius:8px; overflow:hidden; }
.lv-table th { text-align:left; font-size:13px; color:#66737F; font-weight:600; padding:10px 12px; background:#F6F8FA; border-bottom:1px solid #E5E9EC; }
.lv-table td { padding:10px 12px; font-size:14px; border-bottom:1px solid #F2F5F3; }
.lv-ev { display:flex; justify-content:space-between; align-items:center; padding:10px 14px; background:#fff; border:1px solid #E5E9EC; border-radius:8px; margin-bottom:8px; font-size:14px; }
.lv-ev .lv-ev-d { color:#8A959E; font-size:13px; }
.lv-note { font-size:13px; color:#66737F; margin-top:18px; line-height:1.9; }
"""


def _name_map():
    return {p['sku']: p for p in memory.get_products()}


def render_ledger() -> str:
    stats = memory.memory_stats()
    lead = '<div class="lv-lead">过去的销售、断货、损耗和特殊情况，都留在这里</div>'
    summary = ('<div class="lv-sum">'
               '<div><b>%s</b>天经营记录</div><div><b>%s</b>条销量明细</div>'
               '<div><b>%s</b>种商品档案</div><div><b>%s</b>种民生商品</div></div>'
               % (stats.get('累计覆盖天数', 0), stats.get('销量记录条数', 0),
                  stats.get('商品数', 0), stats.get('民生商品数', 0)))
    evs = memory.get_events_summary()
    ev_html = ''
    if evs:
        er = ''.join('<div class="lv-ev"><div><b>%s</b></div><div class="lv-ev-d">%s 天 · %s ~ %s</div></div>' % (e['event'], e['days'], e['first_day'], e['last_day']) for e in evs)
        ev_html = '<div class="lv-sec-title">过去发生过什么</div>' + er
    health = analysis.sku_health_report()
    prows = []
    for h in health:
        star = '★ ' if h['is_livelihood'] else ''
        so = ('%d 天' % h['stockout_days']) if h['stockout_days'] else '—'
        sp = ('%d 天' % h['spoilage_days']) if h['spoilage_days'] else '—'
        prows.append('<tr><td>%s%s</td><td>%s</td><td>%.1f</td><td>%.0f</td><td>%s</td><td>%s</td></tr>' % (star, h['name'], h['category'], h['avg_daily'], h['on_hand'], so, sp))
    prod = ('<div class="lv-sec-title">商品经营档案</div>'
            '<table class="lv-table"><tr><th>商品</th><th>品类</th><th>日均销量</th>'
            '<th>当前库存</th><th>曾断货</th><th>曾损耗</th></tr>' + ''.join(prows) + '</table>')
    sup = ''
    sups = memory.get_suppliers()
    if sups:
        sr = ''.join('<tr><td>%s</td><td>%d 种</td><td>约 %.1f 天</td></tr>' % (s['supplier'], s['sku_count'], s['avg_lead_days']) for s in sups)
        sup = ('<div class="lv-sec-title">供应商与到货时间</div>'
               '<table class="lv-table"><tr><th>供应商</th><th>覆盖商品</th><th>平均到货时间</th></tr>' + sr + '</table>')
    note = '<div class="lv-note">老账本负责记住发生过什么，小满会从这些真实经营记录中逐渐总结经验。</div>'
    return lead + summary + ev_html + prod + sup + note
