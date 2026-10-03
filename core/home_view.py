# -*- coding: utf-8 -*-
"""小满 · 首页（今天该进什么货）视觉样板 —— 经营工作台，而非 Dashboard。

严格遵循 DESIGN.md（UI Design System v1.0）：AI 藏在能力里、不浮在视觉表面；
所有数字来自真实决策结果，不写死、无机器人/聊天框/渐变/玻璃拟态/动画。
"""

HOME_CSS = ""

import datetime as _dt

from . import decision_basis, events

_WEEK = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _day_cn(day_str):
    try:
        d = _dt.date.fromisoformat(str(day_str)[:10])
        return "%d月%d日 · %s" % (d.month, d.day, _WEEK[d.weekday()])
    except Exception:
        return str(day_str)


def _greet():
    h = _dt.datetime.now().hour
    return "早上好" if h < 11 else ("中午好" if h < 13 else ("下午好" if h < 18 else "晚上好"))


def render_home_html(plan: dict, part=None) -> str:
    m = plan['metrics']
    items = plan['items']
    briefs = []
    for k in (plan.get('risks') or []):
        label = events.EVENT_KEY_TO_LABEL.get(k, k)
        briefs.append(('warn', '今日情况', '检测到%s' % label, '已据此调整今日的销量预计与备货建议'))
    sec = float(m.get('livelihood_secured_rate', 1.0) or 0.0)
    if sec >= 1.0 - 1e-9:
        briefs.append(('ok', '民生', '民生商品保障正常', '%d 种民生商品达到最低保障要求' % int(m.get('livelihood_total_count', 0) or 0)))
    else:
        briefs.append(('warn', '民生', '民生保障存在缺口', '达标率仅 %.0f%%，需优先补足' % (sec * 100)))
    nrisk = sum(1 for it in items if it.get('stockout_risk'))
    if nrisk:
        briefs.append(('warn', '库存', '%d 种商品可能不够卖' % nrisk, '现有库存覆盖不足，建议优先补货'))
    if any(it.get('supplier_down') for it in items):
        briefs.append(('warn', '供应', '部分商品供应商异常', '断供商品本次不可采购'))
    else:
        briefs.append(('info', '供应', '今天没有供应商异常', '供应链正常'))
    n_attention = sum(1 for lv, _t, _a, _b in briefs if lv == 'warn')
    _cls = {'warn': 'xm-badge-orange', 'ok': 'xm-badge-green', 'info': 'xm-badge-neutral', 'danger': 'xm-badge-red'}
    brief_html = ''.join(
        '<div class="xm-brief"><span class="xm-badge %s">%s</span>'
        '<div><div class="xm-brief-t">%s</div><div class="xm-brief-sub">%s</div></div></div>' % (_cls.get(lv, 'xm-badge-neutral'), tag, title, sub)
        for lv, tag, title, sub in briefs)
    dec_html = ('<div class="xm-card" style="padding:12px 16px"><div class="xm-cap">明天建议进货</div>'
                '<div class="xm-amount">¥%.0f</div>'
                '<div class="xm-sm">预计毛利 ¥%.0f　·　民生保障 %.0f%%　·　共 %d 种商品</div></div>'
                % (float(m.get('total_cost', 0) or 0), float(m.get('gross_margin', 0) or 0),
                   float(m.get('livelihood_secured_rate', 0) or 0) * 100, int(m.get('display_count', 0) or 0)))

    def _rowtags(it):
        tags = []
        if it.get('is_livelihood'):
            tags.append(('xm-badge-green', '民生'))
        if it.get('stockout_risk'):
            cover = float(it.get('final_cover_days', 0) or 0)
            tags.append(('xm-badge-red' if cover < 1 else 'xm-badge-orange', '可能断货'))
        elif float(it.get('risk_factor', 1) or 1) > 1.001:
            tags.append(('xm-badge-neutral', '需求上升'))
        if abs(float(it.get('memory_delta', 0) or 0)) > 1e-9:
            tags.append(('xm-badge-neutral', '参考历史经验'))
        return ''.join('<span class="xm-badge %s">%s</span>' % t for t in tags[:2])

    ordered = sorted([it for it in items if it['reorder_qty'] > 0 or it['daily_demand'] > 0], key=lambda x: (-x['is_livelihood'], -x['reorder_qty']))

    def _row(it):
        unit = it['unit']
        qty = float(it['reorder_qty'] or 0)
        qty_html = ('<span class="xm-num">%.0f</span> %s' % (qty, unit)) if qty > 0 else '<span class="xm-dim">暂不进货</span>'
        why = ('<details class="xm-acc"><summary>查看原因 ›</summary><div class="basis">%s</div></details>'
               % decision_basis.render_reorder_basis(it))
        return ('<tr><td><div class="xm-name">%s%s</div></td>'
                '<td class="xm-dim">%.0f %s</td><td class="xm-dim">%.1f %s</td>'
                '<td>%s</td><td class="xm-dim">%.1f 天</td><td>%s</td></tr>'
                % (it['name'], _rowtags(it), float(it['on_hand'] or 0), unit, float(it['daily_demand'] or 0),
                   unit, qty_html, float(it.get('final_cover_days', 0) or 0), why))

    att = [it for it in items if it.get('stockout_risk') or (it['is_livelihood'] and it.get('trimmed'))]
    att = sorted(att, key=lambda x: float(x.get('final_cover_days', 99) or 99))[:5]
    att_html = ''.join(_row(it) for it in att)
    full_html = ''.join(_row(it) for it in ordered)
    greet_line = ('今天有 %d 件事值得留意' % n_attention) if n_attention else '今天没有特别需要留意的事'
    _ref = plan.get('date')
    try:
        _ref = (_dt.date.fromisoformat(str(plan.get('date'))[:10]) - _dt.timedelta(days=1)).isoformat()
    except Exception:
        pass
    head = ('<div class="xm-h1">小满</div>'
            '<div class="xm-cap" style="margin-top:2px">今天 · %s</div>'
            '<div class="xm-body" style="margin-top:8px;font-weight:500">%s，%s</div></div>'
            % (_day_cn(_ref), _greet(), greet_line))
    att_sec = ('<div class="xm-sec"><div class="xm-sec-title">明天重点关注</div><div class="xm-hint">建议先确认这些商品的备货情况</div>'
               '<table class="xm-table"><tr><th>商品</th><th>当前库存</th><th>预计需求</th>'
               '<th>建议进货</th><th>进货后约够</th><th>说明</th></tr>' + att_html + '</table></div>') if att_html else ''
    spec_note = ''
    if plan.get('risks'):
        labels = '、'.join(events.EVENT_KEY_TO_LABEL.get(k, k) for k in plan['risks'])
        spec_note = '<div class="xm-brief-sub" style="margin:8px 0 0">已考虑%s对相关商品需求的影响。</div>' % labels
    tbl = '<table class="xm-table"><tr><th>商品</th><th>当前库存</th><th>预计需求</th><th>建议进货</th><th>进货后约够</th><th>说明</th></tr>'
    top = ('<div class="xm-home">' + head
           + '<div class="xm-sec"><div class="xm-sec-title">今日提醒</div>' + brief_html + '</div></div>')
    result = ('<div class="xm-home">'
              + '<div class="xm-sec"><div class="xm-sec-title">明天建议这样进</div>' + dec_html + spec_note + '</div>'
              + att_sec
              + '<div class="xm-sec"><div class="xm-sec-title">完整进货清单</div>' + tbl + full_html + '</table></div></div>')
    if part == 'top':
        return top
    if part == 'result':
        return result
    return top + result

