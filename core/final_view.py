# -*- coding: utf-8 -*-
"""小满 · 「FINAL 实验对比」展示页（只读取 eval/final 冻结结果，不重跑实验、不写死数字）。"""
import csv
import json
import os

FINAL_DIR = os.path.join('eval', 'final')


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


def _card(value, label, sub=None):
    sub_html = ("<div style='font-size:12px;color:#8b98a8;margin-top:2px'>%s</div>" % sub) if sub else ""
    return ("<div style='flex:1;min-width:120px;background:#f8fafc;border:1px solid #e6ecf2;"
            "border-radius:8px;padding:12px 14px;'>"
            "<div style='font-size:20px;font-weight:800;color:#1f4e79;'>%s</div>"
            "<div style='font-size:13px;color:#5a6b7d;margin-top:2px'>%s</div>%s</div>"
            % (value, label, sub_html))


def _howto(text):
    return ("<div style='margin:10px 0 0;padding:8px 12px;background:#eef4f9;border-radius:6px;"
            "font-size:13px;color:#2c5f8a'>👀 怎么看：%s</div>" % text)


def _kv_delta(name, a, b, is_pct=False, better_low=False):
    fmt = _pct if is_pct else (lambda v: "%.1f" % float(v or 0.0))
    d = float(a or 0.0) - float(b or 0.0)
    if is_pct:
        d_txt = "%+.3fpp" % (d * 100.0)
        better = (d < 0) if better_low else (d > 0)
    else:
        d_txt = "%+.1f" % d
        better = (d < 0) if better_low else (d > 0)
    color = "#3f8f6b" if better else "#c0564f"
    return ("<tr><td>%s</td><td>%s</td><td>%s</td>"
            "<td style='color:%s;font-weight:700'>%s</td></tr>"
            % (name, fmt(a), fmt(b), color, d_txt))


def _bars(title, pairs):
    """轻量横向条形对比（一张图一个结论）。pairs: [(label, value0~1)]"""
    maxv = max([abs(v) for _, v in pairs] + [1e-9])
    rows = ""
    for label, v in pairs:
        w = abs(v) / maxv * 100.0
        color = "#2c5f8a"
        rows += ("<div style='display:flex;align-items:center;margin:6px 0'>"
                 "<div style='width:150px;font-size:13px;color:#5a6b7d'>%s</div>"
                 "<div style='flex:1;background:#eef1f5;border-radius:4px;height:20px'>"
                 "<div style='width:%.1f%%;background:%s;border-radius:4px;height:20px'></div></div>"
                 "<div style='width:76px;text-align:right;font-size:13px;font-weight:700;color:#1f4e79'>%s</div></div>"
                 % (label, w, color, _pct(v)))
    return ("<div style='background:#fff;border:1px solid #e6ecf2;border-radius:8px;"
            "padding:14px 16px;margin-top:10px'>"
            "<div style='font-weight:700;color:#1f4e79;margin-bottom:4px'>%s</div>%s</div>"
            % (title, rows))


def render_html():
    d = load_final()
    if not d:
        return "<div class='note'>未找到 FINAL 实验结果文件（eval/final/）。</div>"
    res = d['results']
    r3v = res.get('r3_vs_traditional', {})
    dian = r3v.get('diannao', {})
    base = r3v.get('baseline', {})
    seed = d.get('seed')
    budget = d.get('budget')
    budget_txt = ("¥%.0f" % float(budget)) if budget is not None else "—"
    head = ("<div style='padding:24px 28px;background:#f7fafc;border-bottom:1px solid #e6ecf2'>"
            "<h1 style='font-size:30px;margin:0;color:#1f4e79'>小满</h1>"
            "<p style='font-size:15px;margin:6px 0 0;color:#33414f'>面向社区小店的自进化智能补货 Agent</p>"
            "<p style='margin:8px 0 0;font-size:13px;color:#8b98a8'>180 天社区小店数字经营仿真实验　固定随机种子 %s　每日预算 %s　统一指标口径</p></div>" % (seed, budget_txt))
    cred = ("<div style='display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 4px'>" + "".join("<span style='background:#eef4f9;color:#2c5f8a;font-size:12px;padding:4px 10px;border-radius:12px'>%s</span>" % t for t in ["同一需求环境", "同一初始库存", "同一预算", "同一供应链规则", "统一指标口径", "固定随机种子", "结果可复现"]) + "</div>")
    rows1 = "".join(_kv_delta(n, dian.get(k), base.get(k), p, low) for n, k, p, low in [("累计毛利（元）", "cumulative_gross_margin", False, False), ("总体缺货率", "stockout_rate", True, True), ("民生商品缺货率", "livelihood_stockout_rate", True, True), ("民生保障率", "livelihood_secured_rate", True, False), ("损耗率", "spoilage_rate", True, True), ("平均库存资金占用（元）", "avg_inventory_capital", False, True), ("库存周转率", "inventory_turnover", False, False)])
    h1 = "民生缺货率 小满 %s / 传统 %s；总体缺货率 小满 %s / 传统 %s。两项不一定同向，请逐项看下表。小满不是追求每个经营指标都超过传统方法，而是在经营收益、抗风险与民生保障之间做多目标取舍。" % (_pct(dian.get('livelihood_stockout_rate')), _pct(base.get('livelihood_stockout_rate')), _pct(dian.get('stockout_rate')), _pct(base.get('stockout_rate')))
    hl = ('<div style="display:flex;gap:10px;margin:10px 0;font-size:13px">'
          '<div style="flex:1;background:#F6F8FA;border:1px solid #E5E9EC;border-radius:8px;padding:9px 12px">民生保障率 <b style="color:#234E70">%s</b> <span style="color:#66737F">／传统 %s</span></div>'
          '<div style="flex:1;background:#F6F8FA;border:1px solid #E5E9EC;border-radius:8px;padding:9px 12px">民生商品缺货率 <b style="color:#234E70">%s</b> <span style="color:#66737F">／传统 %s</span></div>'
          '<div style="flex:1;background:#F6F8FA;border:1px solid #E5E9EC;border-radius:8px;padding:9px 12px">累计毛利 <b style="color:#234E70">%s</b> <span style="color:#66737F">／传统 %s</span></div></div>'
          % (_pct(dian.get('livelihood_secured_rate')), _pct(base.get('livelihood_secured_rate')),
             _pct(dian.get('livelihood_stockout_rate')), _pct(base.get('livelihood_stockout_rate')),
             _money(dian.get('cumulative_gross_margin')), _money(base.get('cumulative_gross_margin'))))
    sec1 = hl + ("<div class='dn-card' style='margin-top:14px'><h3 style='margin-top:0'>① 小满 vs Traditional（180 天公平对照）</h3>"
            "<table class='dn'><tr><th>指标</th><th>小满</th><th>Traditional</th><th>变化</th></tr>%s</table>"
            "<div style='margin-top:8px;font-size:12px;color:#8b98a8'>变化 = 小满 − Traditional；绿=对小满有利，红=对小满不利。</div>" % rows1) + _howto(h1) + "</div>"
    abl = res.get('ablation_3obj', {})
    abl_rows = [("Full R³", abl.get('full', {})), ("− Revenue", abl.get('no_revenue', {})), ("− Resilience", abl.get('no_resilience', {})), ("− Responsibility", abl.get('no_responsibility', {}))]
    b_so = _bars("移除某模块后 · 总体缺货率", [(n, s.get('stockout_rate', 0)) for n, s in abl_rows])
    b_liv = _bars("移除某模块后 · 民生商品缺货率", [(n, s.get('livelihood_stockout_rate', 0)) for n, s in abl_rows])
    abl_table = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (n, _money(s.get('cumulative_gross_margin')), _pct(s.get('stockout_rate')), _pct(s.get('livelihood_stockout_rate'))) for n, s in abl_rows)
    h2 = "例如：移除 Resilience 后总体缺货率上升、移除 Responsibility 后民生缺货率上升；某指标变差即说明该目标在起作用。"
    sec2 = ("<div class='dn-card' style='margin-top:14px'><h3 style='margin-top:0'>② R³ 三目标如何改变经营取舍</h3><p style='font-size:13px;color:#5a6b7d;margin:0 0 8px'>关掉 R³ 某一个目标后的真实变化（不做综合评分、不排名）。</p>" + b_so + b_liv + "<table class='dn' style='margin-top:12px'><tr><th>方案</th><th>累计毛利</th><th>总体缺货率</th><th>民生缺货率</th></tr>" + abl_table + "</table>" + _howto(h2) + "</div>")
    mem = res.get('memory_ab', {})
    m_on = mem.get('memory_on', {})
    m_off = mem.get('memory_off', {})
    ms = memory_stats()
    mem_cards = "<div style='display:flex;gap:10px;margin-top:10px'>" + _card(str(m_on.get('memory_experiences', 0)), "形成经验数") + _card(str(ms.get('hits', 0)), "Memory 命中次数") + _card(str(ms.get('changed', 0)), "改变补货次数") + "</div>"
    mrows = "".join(_kv_delta(n, m_on.get(k), m_off.get(k), p, low) for n, k, p, low in [("累计毛利（元）", "cumulative_gross_margin", False, False), ("总体缺货率", "stockout_rate", True, True), ("民生商品缺货率", "livelihood_stockout_rate", True, True)])
    n_exp = m_on.get('memory_experiences', 0)
    n_hit = ms.get('hits', 0)
    n_chg = ms.get('changed', 0)
    h3 = "形成经验 %s 条 → 后续命中 %s 次 → 改变补货 %s 次 → 长期经营结果随之变化（均来自 FINAL 逐日流水真实统计）。" % (n_exp, n_hit, n_chg)
    c = ms.get('case')
    case_html = ("<div style='margin-top:10px;padding:10px 12px;background:#f8fafc;border-left:3px solid #2c5f8a;border-radius:6px;font-size:13px'>可追溯案例：<b>%s</b> %s 命中记忆（修正系数 %.3f），补货由 %.0f 件调整为 <b>%.0f 件</b>。</div>" % (c['name'], c['day'], c['factor'], c['off'], c['on'])) if c else ""
    sec3 = ("<div class='dn-card' style='margin-top:14px'><h3 style='margin-top:0'>③ 经营经验真的会影响后续决策吗？（Memory A/B）</h3><table class='dn'><tr><th>指标</th><th>Memory ON</th><th>Memory OFF</th><th>变化</th></tr>" + mrows + "</table>" + mem_cards + _howto(h3) + case_html + "</div>")
    sp = res.get('spoilage_ab', {})
    sp_on = sp.get('control_on', {})
    sp_off = sp.get('control_off', {})
    srows = "".join(_kv_delta(n, sp_on.get(k), sp_off.get(k), p, low) for n, k, p, low in [("损耗件数", "spoilage_qty", False, True), ("损耗成本（元）", "spoilage_cost", False, True), ("损耗率", "spoilage_rate", True, True), ("总体缺货率", "stockout_rate", True, True), ("累计毛利（元）", "cumulative_gross_margin", False, False)])
    _sp_keys = ['spoilage_qty', 'spoilage_cost', 'spoilage_rate', 'stockout_rate', 'cumulative_gross_margin']
    _same = all(abs(float(sp_on.get(k, 0) or 0) - float(sp_off.get(k, 0) or 0)) < 1e-9 for k in _sp_keys)
    h4 = ("当前 180 天基准环境下，未观察到损耗控制开关带来的可测增量（ON 与 OFF 各项一致）。" if _same else "ON 与 OFF 存在差异，见下表：")
    sec4 = ("<div class='dn-card' style='margin-top:14px'><h3 style='margin-top:0'>④ 损耗控制 A/B</h3><table class='dn'><tr><th>指标</th><th>ON</th><th>OFF</th><th>变化</th></tr>" + srows + "</table><div style='margin-top:8px;font-size:12px;color:#8b98a8'>若 ON 与 OFF 各项一致，说明损耗控制在该数据下未触发（如实显示，不做美化）。</div>" + _howto(h4) + "</div>")
    intro = ('<div class="dn-card" style="margin-top:14px"><div style="font-size:13px;color:#8a959e">实验问题</div>'
             '<div style="font-size:16px;font-weight:600;margin-top:4px">小满与传统补货方法有什么区别？R³ 与经营经验是否产生了真实影响？</div>'
             '<div style="font-size:14px;color:#33414f;margin-top:10px;line-height:1.9">下面四组结果回答这两个问题：先给结论，再看数据，实验设置放在最后。</div></div>')
    settings = ('<details style="margin-top:18px"><summary style="cursor:pointer;font-size:14px;color:#234E70">实验设置与可复现信息</summary><div style="margin-top:10px">' + cred + '</div></details>')
    return head + intro + sec1 + sec2 + sec3 + sec4 + settings
