# -*- coding: utf-8 -*-
"""小满 · 「FINAL 实验对比」展示页（只读取 eval/final 冻结结果，不重跑实验、不写死数字）。

v2 迁移（T-UI-03）：页面结构改用共享组件（.xm-page/.xm-card/.xm-h3/.xm-table/.xm-callout/
.xm-kv*/xm-bar*/.xm-badge/.xm-acc），颜色一律用 --xm-* token —— 本页不再自带颜色。
数据读取与计算逻辑未改动。
"""

import csv
import json
import os

FINAL_DIR = os.path.join('eval', 'final')

# 本页无需自有样式：全部消费 core/ui_theme.py 的共享组件与 token
FINAL_CSS = ""


def load_final():
    p = os.path.join(FINAL_DIR, 'final_experiment_summary.json')
    if not os.path.exists(p):
        return None
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def _pct(x):
    return "%.3f%%" % (float(x or 0.0) * 100.0)


def _money(x):
    return "¥%.0f" % float(x or 0.0)


def _read_daily(name):
    p = os.path.join(FINAL_DIR, name)
    if not os.path.exists(p):
        return []
    with open(p, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def memory_stats():
    """从 FINAL Memory A/B 的逐日流水真实统计命中/改变次数与一个可追溯案例。"""
    on = _read_daily('memory_ab/daily_memory_on.csv')
    off = _read_daily('memory_ab/daily_memory_off.csv')
    if not on:
        return {}
    hits = [r for r in on if abs(float(r.get('memory_adjustment_factor') or 1.0) - 1.0) > 1e-9]
    offmap = {(r['day'], r['sku']): float(r.get('reorder_qty') or 0.0) for r in off}
    changed = sum(1 for r in on
                  if abs(float(r.get('reorder_qty') or 0.0) - offmap.get((r['day'], r['sku']), 0.0)) > 1e-9)
    case = None
    for r in hits:
        b = offmap.get((r['day'], r['sku']))
        if b is not None and abs(float(r['reorder_qty']) - b) > 1e-9:
            case = {'day': r['day'], 'name': r.get('name', r['sku']),
                    'factor': float(r['memory_adjustment_factor']),
                    'on': float(r['reorder_qty']), 'off': b}
            break
    return {'hits': len(hits), 'changed': changed, 'case': case}


def _sum_daily(path, cols):
    """把逐日流水的若干列求和（缺失列按 0），用于从冻结证据里现算差额。"""
    rows = _read_daily(path)
    if not rows:
        return {}
    out = {c: 0.0 for c in cols}
    for r in rows:
        for c in cols:
            try:
                out[c] += float(r.get(c) or 0.0)
            except (TypeError, ValueError):
                pass
    return out


def tradeoff_mechanism():
    """T-EXP-03：−Revenue 的累计毛利为何略高 —— 从冻结流水现算「多进货 / 多卖货」的差额。

    只读 eval/final/ablation_3obj 的两组逐日流水，不重跑实验、不写死数字。
    """
    cols = ('revenue', 'purchase_cost', 'sold_qty', 'stockout_qty', 'gross_margin')
    full = _sum_daily('ablation_3obj/daily_full.csv', cols)
    norev = _sum_daily('ablation_3obj/daily_no_revenue.csv', cols)
    if not full or not norev:
        return {}
    return {k: norev[k] - full[k] for k in cols}


def spoilage_headroom():
    """T-EXP-02：损耗控制开关为何在该数据集下无差异 —— 算「短保可售容量 − 理想补货量」的余量。

    只读 FINAL 的 spoilage A/B（control_on）逐日流水。余量恒 ≥ 0 且采购上限从未命中，
    就说明上限从未生效 —— 这正是 ON / OFF 各项完全一致的机制（如实说明，不美化）。
    """
    rows = _read_daily('spoilage_ab/daily_control_on.csv')
    if not rows:
        return {}
    slack, capped = [], 0
    for r in rows:
        try:
            slack.append(float(r['free_sellable_capacity']) - float(r['raw_reorder_uncapped']))
        except (KeyError, TypeError, ValueError):
            continue
        if str(r.get('spoilage_capped')) in ('1', 'True', 'true'):
            capped += 1
    if not slack:
        return {}
    slack.sort()
    return {'n': len(slack), 'min': slack[0], 'median': slack[len(slack) // 2],
            'max': slack[-1], 'capped': capped}


def _card(value, label, sub=None):
    sub_html = '<div class="xm-kv-sub">%s</div>' % sub if sub else ''
    return ('<div class="xm-kv"><div class="xm-kv-v">%s</div>'
            '<div class="xm-kv-k">%s</div>%s</div>' % (value, label, sub_html))


def _howto(text):
    return '<div class="xm-callout">怎么看：%s</div>' % text


def _kv_delta(name, a, b, is_pct=False, better_low=False):
    fmt = _pct if is_pct else (lambda v: "%.1f" % float(v or 0.0))
    d = float(a or 0.0) - float(b or 0.0)
    if is_pct:
        d_txt = "%+.3fpp" % (d * 100.0)
        better = (d < 0) if better_low else (d > 0)
    else:
        d_txt = "%+.1f" % d
        better = (d < 0) if better_low else (d > 0)
    color = "var(--xm-success)" if better else "var(--xm-error)"
    return ("<tr><td>%s</td><td class='xm-num'>%s</td><td class='xm-num'>%s</td>"
            "<td class='xm-num' style='color:%s;font-weight:600'>%s</td></tr>"
            % (name, fmt(a), fmt(b), color, d_txt))


def _bars(title, pairs):
    """轻量横向条形对比（一张图一个结论）。pairs: [(label, value)]"""
    maxv = max([abs(v) for _, v in pairs] + [1e-9])
    rows = ""
    for label, v in pairs:
        w = abs(v) / maxv * 100.0
        rows += ('<div class="xm-bar-row"><div class="xm-bar-label">%s</div>'
                 '<div class="xm-bar-track"><div class="xm-bar-fill" style="width:%.1f%%"></div></div>'
                 '<div class="xm-bar-val">%s</div></div>' % (label, w, _pct(v)))
    return '<div class="xm-h3" style="margin:14px 0 2px">%s</div>%s' % (title, rows)


def _section(title, body, summary=None):
    """统一的小节外壳：不给 summary 就展开成卡片；给了就折成 .xm-fold（默认收起）。

    Direction A：结论（①③）保持展开，明细（②④）默认收起，页高从 2837px 降下来。
    """
    if summary is None:
        return ('<div class="xm-card" style="margin-top:14px">'
                '<div class="xm-h3">%s</div>%s</div>' % (title, body))
    return ('<details class="xm-fold" style="margin-top:14px"><summary>%s'
            '<span class="xm-fold-meta">%s</span></summary>'
            '<div class="xm-fold-body">%s</div></details>' % (title, summary, body))


def render_html():
    d = load_final()
    if not d:
        return "<div class='xm-callout'>未找到 FINAL 实验结果文件（eval/final/）。</div>"
    res = d['results']
    r3v = res.get('r3_vs_traditional', {})
    dian = r3v.get('diannao', {})
    base = r3v.get('baseline', {})
    seed = d.get('seed')
    budget = d.get('budget')
    budget_txt = ("¥%.0f" % float(budget)) if budget is not None else "—"
    head = ('<div class="xm-page"><div class="xm-h1">小满</div>'
            '<div class="xm-sm" style="margin-top:6px">面向社区小店的智能补货 Agent</div>'
            '<div class="xm-cap" style="margin-top:6px">180 天社区小店数字经营仿真实验　'
            '固定随机种子 %s　每日预算 %s　统一指标口径</div></div>' % (seed, budget_txt))
    cred = ('<div class="xm-chips">%s</div>' % "".join(
        '<span class="xm-badge xm-badge-neutral">%s</span>' % t
        for t in ["同一需求环境", "同一初始库存", "同一预算", "同一供应链规则",
                  "统一指标口径", "固定随机种子", "结果可复现"]))
    rows1 = "".join(_kv_delta(n, dian.get(k), base.get(k), p, low) for n, k, p, low in [("累计毛利（元）", "cumulative_gross_margin", False, False), ("总体缺货率", "stockout_rate", True, True), ("民生商品缺货率", "livelihood_stockout_rate", True, True), ("民生保障率", "livelihood_secured_rate", True, False), ("损耗率", "spoilage_rate", True, True), ("平均库存资金占用（元）", "avg_inventory_capital", False, True), ("库存周转率", "inventory_turnover", False, False)])
    h1 = "民生缺货率 小满 %s / 传统 %s；总体缺货率 小满 %s / 传统 %s。两项不一定同向，请逐项看下表。小满不是追求每个经营指标都超过传统方法，而是在经营收益、抗风险与民生保障之间做多目标取舍。" % (_pct(dian.get('livelihood_stockout_rate')), _pct(base.get('livelihood_stockout_rate')), _pct(dian.get('stockout_rate')), _pct(base.get('stockout_rate')))
    hl = ('<div class="xm-kpi-row">'
          '<div class="xm-kpi"><div class="xm-kpi-k">民生保障率</div>'
          '<div class="xm-kpi-v">%s</div><div class="xm-kpi-sub">传统 %s</div></div>'
          '<div class="xm-kpi"><div class="xm-kpi-k">民生商品缺货率</div>'
          '<div class="xm-kpi-v">%s</div><div class="xm-kpi-sub">传统 %s</div></div>'
          '<div class="xm-kpi"><div class="xm-kpi-k">累计毛利</div>'
          '<div class="xm-kpi-v">%s</div><div class="xm-kpi-sub">传统 %s</div></div></div>'
          % (_pct(dian.get('livelihood_secured_rate')), _pct(base.get('livelihood_secured_rate')),
             _pct(dian.get('livelihood_stockout_rate')), _pct(base.get('livelihood_stockout_rate')),
             _money(dian.get('cumulative_gross_margin')), _money(base.get('cumulative_gross_margin'))))
    sec1 = hl + _section(
        '① 小满 vs Traditional（180 天公平对照）',
        "<table class='xm-table'><tr><th>指标</th><th class='xm-num'>小满</th><th class='xm-num'>Traditional</th><th class='xm-num'>变化</th></tr>%s</table>"
        "<div class='xm-cap' style='margin-top:8px'>变化 = 小满 − Traditional；绿=对小满有利，红=对小满不利。</div>" % rows1
        + _howto(h1))
    abl = res.get('ablation_3obj', {})
    abl_rows = [("Full R³", abl.get('full', {})), ("− Revenue", abl.get('no_revenue', {})), ("− Resilience", abl.get('no_resilience', {})), ("− Responsibility", abl.get('no_responsibility', {}))]
    b_so = _bars("移除某模块后 · 总体缺货率", [(n, s.get('stockout_rate', 0)) for n, s in abl_rows])
    b_liv = _bars("移除某模块后 · 民生商品缺货率", [(n, s.get('livelihood_stockout_rate', 0)) for n, s in abl_rows])
    abl_table = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (n, _money(s.get('cumulative_gross_margin')), _pct(s.get('stockout_rate')), _pct(s.get('livelihood_stockout_rate'))) for n, s in abl_rows)
    h2 = "例如：移除 Resilience 后总体缺货率上升、移除 Responsibility 后民生缺货率上升；某指标变差即说明该目标在起作用。"
    mech = tradeoff_mechanism()
    mech_html = ""
    if mech:
        mech_html = ("<div class='xm-callout xm-callout-info' style='margin-top:10px'>"
                     "为什么 −Revenue 的累计毛利反而高 ¥%.0f：它多花 ¥%.0f 采购、多卖 %.0f 件（缺货少 %.0f 件），"
                     "多卖出的收入（+¥%.0f）盖过了多花的成本 —— 去掉收益目标后，预算被用来补齐目标库存缺口。"
                     "所以不是「收益目标有害」，而是该环境下它只影响「同等预算下的边际选择」；"
                     "被显著影响的其实是民生侧（见下表 −Responsibility 一行）。</div>"
                     % (mech['gross_margin'], mech['purchase_cost'], mech['sold_qty'],
                        abs(mech['stockout_qty']), mech['revenue']))
    sec2 = _section(
        '② R³ 三目标如何改变经营取舍',
        "<p class='xm-note' style='margin:0 0 8px'>关掉 R³ 某一个目标后的真实变化（不做综合评分、不排名）。</p>"
        + b_so + b_liv
        + "<table class='xm-table' style='margin-top:12px'><tr><th>方案</th><th class='xm-num'>累计毛利</th><th class='xm-num'>总体缺货率</th><th class='xm-num'>民生缺货率</th></tr>"
        + abl_table + "</table>" + _howto(h2) + mech_html, summary='2 张对比图 + 明细表')
    mem = res.get('memory_ab', {})
    m_on = mem.get('memory_on', {})
    m_off = mem.get('memory_off', {})
    ms = memory_stats()
    mem_cards = ('<div class="xm-kv-row" style="margin-top:12px">'
                 + _card(str(m_on.get('memory_experiences', 0)), "形成经验数")
                 + _card(str(ms.get('hits', 0)), "Memory 命中次数")
                 + _card(str(ms.get('changed', 0)), "改变补货次数") + '</div>')
    mrows = "".join(_kv_delta(n, m_on.get(k), m_off.get(k), p, low) for n, k, p, low in [("累计毛利（元）", "cumulative_gross_margin", False, False), ("总体缺货率", "stockout_rate", True, True), ("民生商品缺货率", "livelihood_stockout_rate", True, True)])
    n_exp = m_on.get('memory_experiences', 0)
    n_hit = ms.get('hits', 0)
    n_chg = ms.get('changed', 0)
    h3 = "形成经验 %s 条 → 后续命中 %s 次 → 改变补货 %s 次 → 长期经营结果随之变化（均来自 FINAL 逐日流水真实统计）。" % (n_exp, n_hit, n_chg)
    c = ms.get('case')
    case_html = ("<div class='xm-callout xm-callout-info' style='margin-top:10px'>可追溯案例：<b>%s</b> %s 命中记忆（修正系数 %.3f），补货由 %.0f 件调整为 <b>%.0f 件</b>。</div>" % (c['name'], c['day'], c['factor'], c['off'], c['on'])) if c else ""
    sec3 = _section(
        '③ 经营经验真的会影响后续决策吗？（Memory A/B）',
        "<table class='xm-table'><tr><th>指标</th><th class='xm-num'>Memory ON</th><th class='xm-num'>Memory OFF</th><th class='xm-num'>变化</th></tr>"
        + mrows + "</table>" + mem_cards + _howto(h3) + case_html)
    sp = res.get('spoilage_ab', {})
    sp_on = sp.get('control_on', {})
    sp_off = sp.get('control_off', {})
    srows = "".join(_kv_delta(n, sp_on.get(k), sp_off.get(k), p, low) for n, k, p, low in [("损耗件数", "spoilage_qty", False, True), ("损耗成本（元）", "spoilage_cost", False, True), ("损耗率", "spoilage_rate", True, True), ("总体缺货率", "stockout_rate", True, True), ("累计毛利（元）", "cumulative_gross_margin", False, False)])
    _sp_keys = ['spoilage_qty', 'spoilage_cost', 'spoilage_rate', 'stockout_rate', 'cumulative_gross_margin']
    _same = all(abs(float(sp_on.get(k, 0) or 0) - float(sp_off.get(k, 0) or 0)) < 1e-9 for k in _sp_keys)
    h4 = ("当前 180 天基准环境下，未观察到损耗控制开关带来的可测增量（ON 与 OFF 各项一致）。" if _same else "ON 与 OFF 存在差异，见下表：")
    headroom = spoilage_headroom()   # 注意：不要叫 head，head 是页面头部 HTML
    head_html = ""
    if headroom:
        head_html = ("<div class='xm-callout xm-callout-info' style='margin-top:10px'>"
                     "为什么两项完全一致：本次基准的 %d 条决策里，「短保可售容量 − 理想补货量」最小余量 %.1f 件、"
                     "中位 %.1f 件、最大 %.1f 件，采购上限命中 %d 次 —— 上限<b>从未生效</b>，"
                     "开关开或关都不会改变任何一天的补货量。</div>"
                     % (headroom['n'], headroom['min'], headroom['median'], headroom['max'],
                        headroom['capped']))
    sec4 = _section(
        '④ 损耗控制 A/B',
        "<table class='xm-table'><tr><th>指标</th><th class='xm-num'>ON</th><th class='xm-num'>OFF</th><th class='xm-num'>变化</th></tr>" + srows + "</table>"
        "<div class='xm-cap' style='margin-top:8px'>若 ON 与 OFF 各项一致，说明损耗控制在该数据下未触发（如实显示，不做美化）。</div>"
        + _howto(h4) + head_html, summary='ON / OFF 逐项对照')
    intro = ('<div class="xm-card" style="margin-top:14px">'
             '<div class="xm-cap">实验问题</div>'
             '<div class="xm-h3" style="margin-top:4px">小满与传统补货方法有什么区别？R³ 与经营经验是否产生了真实影响？</div>'
             '<div class="xm-note" style="margin-top:10px">下面四组结果回答这两个问题：先给结论，再看数据，实验设置放在最后。</div></div>')
    settings = ('<details class="xm-acc xm-sec"><summary>实验设置与可复现信息</summary>'
                '<div style="margin-top:10px">' + cred + '</div></details>')
    return head + intro + sec1 + sec2 + sec3 + sec4 + settings
