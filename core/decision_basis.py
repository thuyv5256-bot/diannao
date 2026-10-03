# -*- coding: utf-8 -*-
"""小满 · 「为什么这样进货」—— 店脑（内部 Agent）的可解释决策链。

把单个 SKU 的真实决策中间结果（Event / Forecast / Memory / Inventory / R³）
转成六阶段人话说明；所有数值均取自当前真实决策，不写死、不虚构评分、不展示未来销量。
"""


def _sect(n, title, body):
    return ("<div style='margin:9px 0;padding:9px 12px;background:#f8fafc;"
            "border-left:3px solid #2c5f8a;border-radius:6px;'>"
            "<b style='color:#1f4e79;'>阶段%s · %s</b>"
            "<div style='margin-top:6px;line-height:1.85;color:#33414f;'>%s</div></div>"
            % (n, title, body))


def render_reorder_basis(it: dict) -> str:
    unit = it["unit"]
    name = it["name"]
    daily = float(it.get("daily_demand") or 0.0)
    on_hand = float(it.get("on_hand") or 0.0)
    elig = float(it.get("eligible_in_transit") or 0.0)
    intransit = float(it.get("in_transit") or 0.0)
    lead = float(it.get("lead_time_days") or 0.0)
    target = float(it.get("target_stock") or 0.0)
    raw = float(it.get("raw_reorder") or 0.0)
    qty = float(it.get("reorder_qty") or 0.0)
    cover_now = float(it.get("supply_cover_days") or 0.0)
    rf = float(it.get("risk_factor") or 1.0)
    md = float(it.get("memory_delta") or 0.0)
    liv = bool(it.get("is_livelihood"))
    floor_qty = float(it.get("floor_qty") or 0.0)
    margin = float(it.get("unit_margin") or 0.0)

    # ① 看环境（Event，真实字段）
    env = []
    if it.get("holiday_note"):
        env.append("节假日事件：<b>%s</b>（已按历史节假日销量调整该品类备货）" % it["holiday_note"])
    if abs(rf - 1.0) > 1e-9:
        env.append("天气/事件修正：<b>%s</b>（需求乘数 x%.2f）" % (it.get("risk_note") or "事件影响已计入预测", rf))
    env.append("供应商：%s%s" % (it.get("supplier", ""), "（今日断供，本次不可采购）" if it.get("supplier_down") else "（正常供货）"))
    env_affect = "是" if (abs(rf - 1.0) > 1e-9 or it.get("holiday_note") or it.get("supplier_down")) else "否（正常经营环境）"
    s1 = _sect("1", "看环境", "<br>".join(env) + "<br>是否影响本商品：<b>%s</b>" % env_affect)
    if abs(rf - 1.0) > 1e-9 and rf > 0:
        s2 = _sect("2", "算需求", "基础预测 %.1f -> 事件修正 x%.2f -> <b>最终预测 %.1f %s</b>（基于历史销量学习，不含未来销量）" % (daily / rf, rf, daily, unit))
    else:
        s2 = _sect("2", "算需求", "最终预测需求 = <b>%.1f %s</b>（无事件修正，基于历史销量学习，不含未来销量）" % (daily, unit))
    if abs(md) > 1e-9:
        direction = "上调" if md > 0 else "下调"
        s3 = _sect("3", "翻老账", "命中历史经验：<b>%s</b> 场景偏差，安全库存系数 %.2f -> %.2f（%s %.2f）" % (it.get("memory_scene") or "普通日", it.get("base_safety_factor", 0.0), it.get("safety_factor", 0.0), direction, abs(md)))
        mem_hit = "是"
    else:
        s3 = _sect("3", "翻老账", "本次没有相关历史经验参与修正。")
        mem_hit = "否"
    inv = "当前库存 %.0f %s ｜ 有效在途 %.0f %s ｜ 供应商交期 %.0f 天 ｜ 现有库存约可支撑 %.1f 天" % (on_hand, unit, elig, unit, lead, cover_now)
    if intransit > 0:
        inv += "（在途共 %.0f %s）" % (intransit, unit)
    ex = float(it.get("expected_excess_qty") or 0.0)
    if ex > 1e-9:
        inv += "<br>损耗提示：预计约 %.0f %s 存在积压/过期风险" % (ex, unit)
    s4 = _sect("4", "查库存", inv)
    gap = max(0.0, target - on_hand - elig)
    resp = ("民生商品：最低保障量 %.0f %s，当前%s" % (floor_qty, unit, "已满足" if qty >= floor_qty - 1e-9 else "未满足")) if liv else "非民生商品，不占用民生兜底额"
    r3 = ("<b>Revenue（赚得到）</b>：单件毛利 ¥%.2f x 建议进货 %.0f = 预计贡献毛利 <b>¥%.0f</b><br>"
          "<b>Resilience（扛得住）</b>：目标库存 %.0f - 现有 %.0f - 有效在途 %.0f = 缺口 <b>%.0f %s</b><br>"
          "<b>Responsibility（守得住）</b>：%s"
          % (margin, qty, margin * qty, target, on_hand, elig, gap, unit, resp))
    s5 = _sect("5", "做权衡（R³）", r3)
    if qty < raw - 1e-9:
        adj = "原始建议 %.0f → 受预算/多目标权衡压缩 %.0f → 最终 <b>%.0f %s</b>" % (raw, raw - qty, qty, unit)
    else:
        adj = "原始建议 %.0f → 未被预算压缩 → 最终 <b>%.0f %s</b>" % (raw, qty, unit)
    concl_parts = ["预计明日需求约 %.1f %s" % (daily, unit), ("现有库存充足" if cover_now >= 1.5 else "现有库存偏紧")]
    if abs(md) > 1e-9:
        concl_parts.append("历史相似场景偏差已纳入记忆修正")
    if liv:
        concl_parts.append("属民生商品，优先保障")
    concl = "；".join(concl_parts) + "，因此建议进货 %.0f %s。" % (qty, unit)
    s6 = _sect("6", "给结论", adj + "<br><b>结论：</b>" + concl)
    trace = ("<div style='margin-top:10px;font-size:12px;color:#8b98a8'>决策轨迹："
             "Event(%s) → Forecast(%.1f %s) → Memory(%s) → Inventory(%.0f) → R³(→ %.0f %s) → Order(%.0f %s)</div>"
             % (env_affect, daily, unit, mem_hit, on_hand + elig, qty, unit, qty, unit))
    return ("<div style='padding:2px 0'>" + s1 + s2 + s3 + s4 + s5 + s6 + trace + "</div>")

