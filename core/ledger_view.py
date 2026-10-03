# -*- coding: utf-8 -*-
"""小满 · 「店里的老账本」经营档案页（UI v2，遵循 DESIGN.md）。

定位：小满长期了解这家店的依据 —— 商品、经营事件、店铺规律都在这里。
只用现有真实数据（memory_stats / 历史事件 / 商品经营档案 / 供应商 / 真实 Memory），
不写死、不虚构、不引用 FINAL 实验数据。

本模块只负责**页面表达**，不碰任何业务逻辑：
  · 经验是否真实存在、是否来自 demo-store，完全由 core.memory 决定；
  · 所有文案只描述代码当前真实具备的数据 —— demo-store 当前 experiences 为空时，
    页面如实显示「还没有形成经营经验」，不伪造记录、不引用 FINAL 的 739 条实验经验。
"""

from . import analysis, memory

LEDGER_CSS = """
/* 顶部紧凑 summary row（不是四张巨大 KPI 卡） */
.lb-sum { display:flex; flex-wrap:wrap; gap:var(--xm-space-xl);
  background:var(--xm-canvas); border:1px solid var(--xm-hairline);
  border-radius:var(--xm-radius-lg); padding:16px 22px; margin:14px 0 4px; }
.lb-sum-item { display:flex; flex-direction:column; gap:3px; min-width:108px; }
.lb-sum-item .v { font-size:22px; font-weight:700; color:var(--xm-ink);
  font-variant-numeric:tabular-nums; line-height:1.1; }
.lb-sum-item .k { font-size:13px; color:var(--xm-slate); }
/* 真实空状态（与 learn_view 同源风格，本地化避免耦合） */
.lb-empty { background:var(--xm-surface-soft); border:1px dashed var(--xm-hairline-strong);
  border-radius:var(--xm-radius-lg); padding:26px 22px; text-align:center; }
.lb-empty p { font-size:14px; color:var(--xm-slate); line-height:1.9; margin:6px 0; }
/* 底部承接流程线（monochrome，无 emoji / 动画） */
.lb-flow { display:flex; align-items:center; gap:10px; flex-wrap:wrap;
  margin-top:var(--xm-space-lg); padding-top:var(--xm-space-md);
  border-top:1px solid var(--xm-hairline-soft); font-size:14px; }
.lb-flow .step { color:var(--xm-charcoal); }
.lb-flow .arr { color:var(--xm-stone); font-weight:600; }
"""

# 历史事件类型 → 语义徽标（与 DESIGN.md §3 一致）
_EVENT_BADGE = {
    "高温": "xm-badge-orange",
    "暴雨": "xm-badge-orange",
    "节假日": "xm-badge-neutral",
    "供应商D断供": "xm-badge-red",
}


def render_head() -> str:
    return ('<div class="xm-page">'
            '<div class="xm-h1">店里的老账本</div>'
            '<div class="xm-sm" style="margin-top:6px">'
            '小满长期记住的商品、经营事件和店铺规律都在这里。</div>'
            '</div>')


def render_summary() -> str:
    """顶部紧凑 summary row：经营记录 · 商品档案 · 民生商品 · 历史事件。"""
    s = memory.memory_stats()
    evs = memory.get_events_summary()
    items = [
        ("%d" % s.get("累计覆盖天数", 0), "天经营记录"),
        ("%d" % s.get("商品数", 0), "种商品档案"),
        ("%d" % s.get("民生商品数", 0), "种民生商品"),
        ("%d" % len(evs), "类历史事件"),
    ]
    cells = "".join(
        '<div class="lb-sum-item"><span class="v">%s</span><span class="k">%s</span></div>'
        % (v, k) for v, k in items)
    return '<div class="lb-sum">%s</div>' % cells


def _event_badge(event: str) -> str:
    cls = _EVENT_BADGE.get(event, "xm-badge-neutral")
    return '<span class="xm-badge %s">%s</span>' % (cls, event)


def render_events() -> str:
    evs = memory.get_events_summary()
    if not evs:
        return ('<div class="xm-sec"><div class="xm-sec-title">历史经营事件</div>'
                '<div class="xm-card xm-card-tint"><div class="xm-sm">'
                '还没有记录到特殊经营事件。</div></div></div>')
    rows = "".join(
        '<tr><td>%s</td><td>%d 天</td><td class="xm-cap">%s ~ %s</td></tr>'
        % (_event_badge(e["event"]), e["days"], e["first_day"], e["last_day"])
        for e in evs)
    return ('<div class="xm-sec"><div class="xm-sec-title">历史经营事件</div>'
            '<table class="xm-table">'
            '<tr><th>事件</th><th>持续天数</th><th>起止日期</th></tr>%s</table>'
            '<div class="xm-cap" style="margin-top:8px">高温、暴雨、节假日、供应商断供等'
            '真实发生过的经营事件，都按发生天数和起止日期留在这里。</div>'
            '</div>' % rows)


def render_products() -> str:
    """商品档案：默认只展示店主/评委易懂的重要字段；
    供应商、到货时间、断货/损耗明细等次级技术字段收进展开区域。"""
    health = analysis.sku_health_report()
    prods = {p["sku"]: p for p in memory.get_products()}
    main = []
    detail = []
    for h in health:
        sku = h["sku"]
        p = prods.get(sku, {})
        live = ('<span class="xm-badge xm-badge-green">民生</span>'
                if h.get("is_livelihood") else "—")
        main.append('<tr><td class="xm-name">%s</td><td>%s</td><td>%s</td>'
                    '<td>%.1f</td><td>%.0f</td><td>%.1f 天</td></tr>'
                    % (h["name"], h["category"], live, h["avg_daily"],
                       h["on_hand"], h["cover_days"]))
        detail.append('<tr><td class="xm-cap">%s</td><td>%s</td><td>%s</td>'
                      '<td>%s</td><td>%d 天 / %.0f</td><td>%d 天 / %.0f</td></tr>'
                      % (sku, h["name"], p.get("supplier", "—"),
                         p.get("lead_time_days", "—"),
                         h["stockout_days"], h["stockout_qty"],
                         h["spoilage_days"], h["spoilage_qty"]))
    # 50 行表格默认收起（Direction A：长表格不要一次铺满整屏），需要时一键展开
    return ('<div class="xm-sec"><div class="xm-sec-title">商品档案</div>'
            '<details class="xm-fold"><summary>全部 %d 种商品'
            '<span class="xm-fold-meta">日均销量 · 当前库存 · 可支撑天数</span></summary>'
            '<div class="xm-fold-body"><table class="xm-table">'
            '<tr><th>商品</th><th>类别</th><th>民生</th>'
            '<th class="xm-num">日均销量</th><th class="xm-num">当前库存</th>'
            '<th class="xm-num">可支撑天数</th></tr>%s</table>'
            '<details class="xm-acc" style="margin-top:14px"><summary>查看完整商品字段'
            '（供应商、到货时间、断货 / 损耗明细）</summary>'
            '<table class="xm-table" style="margin-top:10px">'
            '<tr><th>编号</th><th>商品</th><th>供应商</th><th class="xm-num">到货天数</th>'
            '<th class="xm-num">曾断货</th><th class="xm-num">曾损耗</th></tr>%s</table>'
            '</details></div></details></div>'
            % (len(health), "".join(main), "".join(detail)))


def render_suppliers() -> str:
    sups = memory.get_suppliers()
    if not sups:
        return ('<div class="xm-sec"><div class="xm-sec-title">供应与到货</div>'
                '<div class="xm-card xm-card-tint"><div class="xm-sm">'
                '还没有供应商信息。</div></div></div>')
    rows = "".join(
        '<tr><td>%s</td><td class="xm-num">%d 种</td><td class="xm-num">%.1f 天</td></tr>'
        % (s["supplier"], s["sku_count"], s["avg_lead_days"]) for s in sups)
    return ('<div class="xm-sec"><div class="xm-sec-title">供应与到货</div>'
            '<table class="xm-table">'
            '<tr><th>供应商</th><th>覆盖商品</th><th>平均到货时间</th></tr>%s</table>'
            '</div>' % rows)


def render_experiences() -> str:
    """经营经验：只读 demo-store 真实 Memory。当前无经验 → 真实空状态。

    明确与 FINAL 实验数据隔离：这里只调 memory.get_experiences()（experiences 表），
    绝不读 eval/ 下的 739 条实验经验。
    """
    exps = memory.get_experiences(limit=200)
    if not exps:
        return ('<div class="xm-sec"><div class="xm-sec-title">经营经验</div>'
                '<div class="lb-empty">'
                '<div class="xm-h3" style="margin:0 0 8px;color:var(--xm-ink)">'
                '还没有形成经营经验</div>'
                '<p>老账本已经记下了这家店的商品、事件和规律；等你记录几天的真实断货或损耗，'
                '小满会慢慢总结出经营经验，并显示在这里。</p>'
                '<p class="xm-cap">到「今天生意怎么样」录一次反馈，'
                '再到「它学会了什么」看看学到的结果。</p>'
                '</div></div>')
    cards = "".join(_render_exp(e) for e in exps[:20])
    return ('<div class="xm-sec"><div class="xm-sec-title">经营经验</div>'
            '<div class="xm-cap" style="margin:-2px 0 10px">'
            '来自 demo-store 真实经营反馈，共 %d 条。</div>%s</div>'
            % (len(exps), cards))


def _render_exp(e: dict) -> str:
    sig = e.get("signal") or ""
    sold = float(e.get("qty_sold") or 0)
    if sig == "断货":
        happen = "实际卖出 %.0f，断货 %.0f" % (sold, float(e.get("qty_stockout") or 0))
    else:
        happen = "实际卖出 %.0f，报损 %.0f" % (sold, float(e.get("qty_spoilage") or 0))
    badge = ('<span class="xm-badge xm-badge-red">断货</span>' if sig == "断货"
             else '<span class="xm-badge xm-badge-orange">积压损耗</span>')
    lesson = e.get("lesson") or sig
    adjust = e.get("adjustment") or ""
    return ('<div class="lx-exp">'
            '<div class="lx-exp-h"><span class="lx-exp-name">%s</span>%s'
            '<span class="lx-exp-day">%s</span></div>'
            '<div class="lx-exp-rows">'
            '<div><span class="k">当时发生了什么：</span>%s</div>'
            '<div><span class="k">小满记住了什么：</span>%s</div>'
            '<div><span class="k">以后会怎样参考：</span>%s</div>'
            '</div></div>'
            % (e.get("sku", ""), badge, e.get("day", ""), happen, lesson, adjust))


def render_flow() -> str:
    """页面底部：一句流程，说明本页在闭环里的位置（不堆卡片）。"""
    return ('<div class="lb-flow">'
            '<span class="step">今天生意怎么样</span><span class="arr">→</span>'
            '<span class="step">真实结果记进老账本</span><span class="arr">→</span>'
            '<span class="step">它学会了什么</span><span class="arr">→</span>'
            '<span class="step">影响以后补货</span>'
            '</div>')


def render_ledger() -> str:
    """完整页面：顶部 summary + 经营记录 / 历史经营事件 / 商品档案 / 供应与到货 / 经营经验。"""
    body = (render_summary()
            + '<div class="xm-sec"><div class="xm-sec-title">经营记录</div>'
              '<div class="xm-card"><div class="xm-sm">老账本里留下了这家店 %d 天的真实经营记录，'
              '共 %d 条销量明细，覆盖 %d 种商品每天的实际卖出、断货和损耗。'
              '这些是之后所有补货建议和历史复盘的依据。</div></div></div>'
            % (memory.memory_stats().get("累计覆盖天数", 0),
               memory.memory_stats().get("销量记录条数", 0),
               memory.memory_stats().get("商品数", 0))
            + render_events()
            + render_products()
            + render_suppliers()
            + render_experiences())
    return render_head() + body + render_flow()
