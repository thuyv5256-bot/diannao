# -*- coding: utf-8 -*-
"""小满 · 首页（今天该进什么货）—— 经营工作台（Direction A：现代极简工作台）。

结构（对齐参考站：左导航 + 流体主区 + 首屏 KPI 条 + 2/3 主区 + 1/3 侧栏）：
  part='top'    → 页面头部 + KPI 条（整宽）
  part='rail'   → 右栏「今天提醒」（风险事件 / 民生 / 库存 / 供应）
  part='result' → 主区：明天重点关注（表）+ 完整进货清单（默认收起）

所有数字来自真实决策结果，不写死；颜色只用 --xm-* token（见 DESIGN.md / CLAUDE.md 铁律 8）。
"""

HOME_CSS = """
/* ═══ 商品行 + 整行决策详情（纯展示层）═══════════════════════════════════
   六阶段解释不再塞进「说明」列的单元格里，而是作为 colspan 详情行紧跟在
   对应商品主行正下方 —— 详情横向铺满整表宽度，主行保持紧凑。

   展开/收起沿用原生 <details name>：
     · name 分组 → 同一时间只有一个商品展开（accordion，50 行也不会无限拉长）；
     · 再次点击 summary → 原生收起；
     · <details> 只能控制自己的后代，详情行是它的兄弟 <tr>，故用 :has() 读 [open] 状态联动。*/
.xm-table tbody tr.xm-decision-detail { display:none; }
.xm-table tbody tr.xm-product-row:has(> td details.xm-acc[open]) + tr.xm-decision-detail { display:table-row; }

/* 触发器：单元格只放这一个短动作，宽度按内容收缩（不再被详情内容撑开） */
.xm-table td.xm-acc-cell { width:1%; white-space:nowrap; }
.xm-table .xm-acc > summary { cursor:pointer; list-style:none; display:inline-block;
  font-size:13px; font-weight:500; color:var(--xm-link); white-space:nowrap; }
.xm-table .xm-acc > summary::-webkit-details-marker { display:none; }
.xm-table .xm-acc > summary:hover { text-decoration:underline; }
.xm-acc-close { display:none; }
.xm-table .xm-acc[open] > summary .xm-acc-open { display:none; }
.xm-table .xm-acc[open] > summary .xm-acc-close { display:inline; }

/* 详情容器：自然撑开自己的区域，宽度由 colspan 决定，不设固定高度、不裁切 */
.xm-table td.xm-decision-cell { padding:0; vertical-align:top; background:var(--xm-surface-soft); }
.xm-decision { padding:14px 16px 16px; border-left:3px solid var(--xm-primary); }
.xm-decision-t { font-size:13px; font-weight:600; color:var(--xm-steel); margin-bottom:8px; }
.xm-decision-b { font-size:14px; line-height:1.8; color:var(--xm-ink);
  overflow-wrap:anywhere; word-break:break-word; }

@media (max-width: 767px) {
  /* 窄屏下表格已转为 block 流式，详情行改为自然纵向排列（不产生横向滚动） */
  .xm-table tbody tr.xm-product-row:has(> td details.xm-acc[open]) + tr.xm-decision-detail { display:block; }
  .xm-decision { padding:12px 12px 14px; }
}
"""

import datetime as _dt

from . import decision_basis, events

_WEEK = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _data_end_day() -> str:
    """历史经营记录的最后一天（只读，用于「数据截止日」披露）。

    用已有的 get_day_events()（与 sales 同源同截止），读失败返回「未知」，
    绝不影响任何计算。
    """
    try:
        from core import memory as _mem
        rows = _mem.get_day_events()
        if rows:
            return max(str(r.get("day") or "")[:10] for r in rows)
    except Exception:
        pass
    return "未知"


def _day_cn(day_str):
    try:
        d = _dt.date.fromisoformat(str(day_str)[:10])
        return "%d月%d日 · %s" % (d.month, d.day, _WEEK[d.weekday()])
    except Exception:
        return str(day_str)


def _greet():
    h = _dt.datetime.now().hour
    return "早上好" if h < 11 else ("中午好" if h < 13 else ("下午好" if h < 18 else "晚上好"))


def _briefs(plan, items):
    """今天提醒的条目（真实判定，不写死）：风险事件 / 民生达标 / 库存风险 / 供应状态。"""
    m = plan['metrics']
    out = []
    for k in (plan.get('risks') or []):
        label = events.EVENT_KEY_TO_LABEL.get(k, k)
        out.append(('warn', '决策日情况', '检测到%s' % label, '已据此调整该日的销量预计与备货建议'))
    sec = float(m.get('livelihood_secured_rate', 1.0) or 0.0)
    if sec >= 1.0 - 1e-9:
        out.append(('ok', '民生', '民生商品保障正常',
                    '%d 种民生商品达到最低保障要求' % int(m.get('livelihood_total_count', 0) or 0)))
    else:
        out.append(('warn', '民生', '民生保障存在缺口',
                    '达标率仅 %.0f%%，需优先补足' % (sec * 100)))
    nrisk = sum(1 for it in items if it.get('stockout_risk'))
    if nrisk:
        out.append(('warn', '库存', '%d 种商品可能不够卖' % nrisk, '现有库存覆盖不足，建议优先补货'))
    if any(it.get('supplier_down') for it in items):
        out.append(('warn', '供应', '部分商品供应商异常', '断供商品本次不可采购'))
    else:
        out.append(('info', '供应', '决策日没有供应商异常', '供应链正常'))
    return out


def _kpi(label, value, sub=None, delta=None, delta_kind='flat', value_cls=''):
    delta_html = ('<div class="xm-kpi-delta xm-kpi-delta-%s">%s</div>' % (delta_kind, delta)) if delta else ''
    sub_html = ('<div class="xm-kpi-sub">%s</div>' % sub) if sub else ''
    return ('<div class="xm-kpi"><div class="xm-kpi-k">%s</div>'
            '<div class="xm-kpi-v %s">%s</div>%s%s</div>' % (label, value_cls, value, delta_html, sub_html))


def _row(it):
    """一个商品 = 主行（紧凑）+ 紧随其下的整行详情（六阶段解释）。

    详情不再是「说明」列里的普通单元格内容，而是 colspan 详情行，横跨整表宽度。
    展开/收起用原生 <details name>：同一时间只展开一个（accordion），
    <details> 的开合通过 CSS :has() 联动到紧随其后的兄弟 <tr>。
    """
    unit = it['unit']
    qty = float(it['reorder_qty'] or 0)
    qty_html = ('%.0f <span class="xm-cap">%s</span>' % (qty, unit)) if qty > 0 else '<span class="xm-dim">暂不进货</span>'
    tags = _rowtags(it)
    # 触发器留在主行的「说明」列；name 相同 → 同一时间只展开一个商品
    why = ('<details class="xm-acc" name="xm-order-basis">'
           '<summary><span class="xm-acc-open">查看原因 ›</span>'
           '<span class="xm-acc-close">收起原因 ∧</span></summary></details>')
    main = ('<tr class="xm-product-row">'
            '<td><div class="xm-name">%s</div>%s</td>'
            '<td class="xm-num xm-dim">%.0f <span class="xm-cap">%s</span></td>'
            '<td class="xm-num xm-dim">%.1f <span class="xm-cap">%s</span></td>'
            '<td class="xm-num xm-dim">%.1f <span class="xm-cap">天</span></td>'
            '<td class="xm-num">%s</td><td class="xm-acc-cell">%s</td></tr>'
            % (it['name'], tags, float(it['on_hand'] or 0), unit, float(it['daily_demand'] or 0), unit,
               float(it.get('final_cover_days', 0) or 0), qty_html, why))
    # 详情行：colspan 取真实列数（_THEAD 的 th 个数），不写死
    detail = ('<tr class="xm-decision-detail"><td class="xm-decision-cell" colspan="%d">'
              '<div class="xm-decision"><div class="xm-decision-t">为什么这样进</div>'
              '<div class="xm-decision-b">%s</div></div></td></tr>'
              % (_NCOL, decision_basis.render_reorder_basis(it)))
    return main + detail


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


_THEAD = ('<tr><th>商品</th><th class="xm-num">建议进货</th><th class="xm-num">当前库存</th>'
          '<th class="xm-num">预计需求</th><th class="xm-num">够几天</th><th>说明</th></tr>')

# 详情行的 colspan 必须等于表头真实列数，从 _THEAD 推导而不是写死
_NCOL = _THEAD.count('<th')


def render_home_html(plan: dict, part=None) -> str:
    m = plan['metrics']
    items = plan['items']
    briefs = _briefs(plan, items)
    n_attention = sum(1 for lv, _t, _a, _b in briefs if lv == 'warn')
    _cls = {'warn': 'xm-badge-orange', 'ok': 'xm-badge-green', 'info': 'xm-badge-neutral', 'danger': 'xm-badge-red'}
    brief_html = ''.join(
        '<div class="xm-brief"><span class="xm-badge %s">%s</span>'
        '<div><div class="xm-brief-t">%s</div><div class="xm-brief-sub">%s</div></div></div>'
        % (_cls.get(lv, 'xm-badge-neutral'), tag, title, sub)
        for lv, tag, title, sub in briefs)

    # ── 页面头部 ──
    _ref = plan.get('date')
    try:
        _ref = (_dt.date.fromisoformat(str(plan.get('date'))[:10]) - _dt.timedelta(days=1)).isoformat()
    except Exception:
        pass
    risk_txt = '无特殊风险事件'
    if plan.get('risks'):
        risk_txt = '、'.join(events.EVENT_KEY_TO_LABEL.get(k, k) for k in plan['risks'])
    # 演示日期披露：本项目使用固定的180 天仿真数据集，「今天」是店主视角的
    # 功能名称，不代表电脑当前日期。这里显式给出决策日与数据截止日，
    # 避免把仿真演示误读成真实门店的实时经营。
    _plan_day = str(plan.get('date') or '')[:10]
    head = ('<div class="xm-page-head"><div>'
            '<div class="xm-h1">今天该进什么货</div>'
            '<div class="xm-page-sub">%s · %s　预算 ¥%.0f　生效风险：%s</div>'
            '<div class="xm-sm" style="margin-top:6px">'
            '仿真经营演示 · 决策日期：%s　基于截至 %s 的 180 天模拟经营记录'
            '</div>'
            '</div></div>'
            % (_day_cn(_ref), _greet(), float(plan.get('budget', 0) or 0), risk_txt,
               _plan_day or '（未指定）', _data_end_day()))

    # ── KPI 条（首屏就能看到四个关键数字）──
    sec = float(m.get('livelihood_secured_rate', 0.0) or 0.0)
    first_warn = next((t for lv, _tag, t, _s in briefs if lv == 'warn'), '没有需要特别处理的事')
    kpis = (
        _kpi('决策日建议进货', '¥%.0f' % float(m.get('total_cost', 0) or 0),
             sub='共 %d 种商品需要进货' % int(m.get('display_count', 0) or 0))
        + _kpi('预计毛利', '¥%.0f' % float(m.get('gross_margin', 0) or 0),
               sub='按真实进销价与需求预测计算')
        + _kpi('民生保障', '%.0f%%' % (sec * 100),
               delta=('全部达标' if sec >= 1.0 - 1e-9 else '存在缺口'),
               delta_kind=('up' if sec >= 1.0 - 1e-9 else 'down'),
               sub='%d 种民生商品' % int(m.get('livelihood_total_count', 0) or 0))
        + _kpi('需要留意', '%d 件' % n_attention, sub=first_warn,
               delta_kind='flat')
    )
    top = '<div class="xm-home">%s<div class="xm-kpi-row">%s</div></div>' % (head, kpis)

    if part == 'top':
        return top

    # ── 右栏：今天提醒 ──
    rail = ('<div class="xm-home"><div class="xm-card">'
            '<div class="xm-sec-head"><div class="xm-h3">决策日提醒</div>'
            '<span class="xm-cap">%d 件需要留意</span></div>'
            '<div style="margin-top:12px">%s</div></div></div>'
            % (n_attention, brief_html))
    if part == 'rail':
        return rail

    # ── 主区：重点关注 + 完整清单（默认收起）──
    att = [it for it in items if it.get('stockout_risk') or (it['is_livelihood'] and it.get('trimmed'))]
    att = sorted(att, key=lambda x: float(x.get('final_cover_days', 99) or 99))[:5]
    att_html = ''.join(_row(it) for it in att)
    att_sec = ('<div class="xm-card">'
               '<div class="xm-sec-head"><div class="xm-h3">次日重点关注</div>'
               '<span class="xm-cap">建议先确认这些商品的备货</span></div>'
               '<table class="xm-table" style="margin-top:12px">%s%s</table></div>'
               % (_THEAD, att_html)) if att_html else ''

    ordered = sorted([it for it in items if it['reorder_qty'] > 0 or it['daily_demand'] > 0],
                     key=lambda x: (-x['is_livelihood'], -x['reorder_qty']))
    full_html = ''.join(_row(it) for it in ordered)
    total_qty = sum(float(it['reorder_qty'] or 0) for it in items)
    fold = ('<details class="xm-fold"><summary>完整进货清单'
            '<span class="xm-fold-meta">共 %d 种商品 · 建议进货合计 %.0f 件</span></summary>'
            '<div class="xm-fold-body"><table class="xm-table">%s%s</table></div></details>'
            % (len(ordered), total_qty, _THEAD, full_html))

    note = ''
    if plan.get('risks'):
        labels = '、'.join(events.EVENT_KEY_TO_LABEL.get(k, k) for k in plan['risks'])
        note = ('<div class="xm-callout" style="margin-top:12px">已考虑<b>%s</b>对相关商品需求的影响，'
                '事件因子只在需求预测侧乘一次，覆盖天数里不再叠加缓冲。</div>' % labels)
    result = '<div class="xm-home">%s%s%s</div>' % (att_sec, fold, note)
    if part == 'result':
        return result
    return top + result
