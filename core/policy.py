# -*- coding: utf-8 -*-
"""
小满 · 补货决策模块（创新点 1 的技术实体：带惠民约束的 Agent 决策逻辑）

═══ 问题的本质 ═══
夫妻小店的进货预算有限。传统的"利润最大化"算法会怎么做？
它按「单位资金预期毛利」排序分配预算 —— 高毛利的薯片、巧克力、坚果排前面，
低毛利的食盐、大米、瓶装水排后面。预算一紧，砍掉的永远是民生商品。
结果：门店短期毛利好看了，但社区居民买不到平价米面油盐，
     客流被削掉，连带销售一起掉 —— 这是典型的"算法短视"。

═══ 小满的做法：三层惠民约束 ═══
  第 1 层｜民生兜底：民生商品先按最低覆盖天数（默认 3 天）锁定基础备货量，
        这一步不参与利润竞价，预算再紧也不许砍。
  第 2 层｜弹性分配：剩余预算按「单位资金预期毛利」分配给所有商品的增量需求，
        民生商品想多备、非民生商品想上架，在这里公平竞争。
  第 3 层｜极端保底：若预算连民生底线都覆盖不了，按「客流带动系数 × 缺口」
        排序保障 —— 优先保住最能引来客流的那几样。

于是，Agent 的优化目标从"单期毛利最大化"变成了
      「门店收益 + 社区便民价值」的双目标 —— 这正是本项目的立项立意。
"""

import math
from datetime import date, datetime, timedelta

from . import events, forecast, memory, metrics, risk
from .config import (
    DEFAULT_BUDGET,
    LIVELIHOOD_BASE_DAYS_MIN,
    LIVELIHOOD_MIN_COVER_DAYS,
    MEMORY_BIAS_GAIN,
    MEMORY_SAFETY_MAX_DELTA,
    R3_SOLVER_ENABLED,
    RESTORE_POTENTIAL,
    REVIEW_BUFFER_DAYS,
    SAFETY_FACTOR_MAX,
    SAFETY_FACTOR_MIN,
)

MODE_DIANNAO = "diannao"
MODE_BASELINE = "baseline"
#注意：MODE_DIANNAO 的值 "diannao" 是内部标识符（数据库/CSV/函数名都依赖它），
# 不可改动；这里改的只是用户能看到的显示标签。
MODE_LABELS = {
    MODE_DIANNAO: "小满（惠民约束版）",
    MODE_BASELINE: "传统算法（纯利润优先）",
}

# 短保商品阈值：保质期 ≤ 该天数才计入「预计损耗/过量库存风险」计算
PERISHABLE_SHELF_LIFE_DAYS = 30.0

# ── Memory 误差学习参数（有界、取均值，非连乘；增益在 config）──
MEMORY_BIAS_WINDOW = 5      # 每个 SKU 只学最近 N 条同场景经验（防陈旧/放大）


def _as_date(d) -> date:
    """把 ISO 字符串或 date 对象统一成 date。"""
    if isinstance(d, date):
        return d
    return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()


def _window_horizon(plan_date, window_days: float) -> date:
    """评估窗口的结束日（不含）：plan_date + ceil(window_days) 天。

    覆盖窗口 = 未来 window_days 天的需求；某天期初到货即可参与当天销售，
    因此「在窗口内到货」= 到货日 < 窗口结束日。
    """
    return _as_date(plan_date) + timedelta(days=int(math.ceil(window_days)))


def _eligible_in_transit(entries, plan_date, window_days: float) -> float:
    """在途订单中，能在评估窗口内真正到货的部分（件）——「有效在途库存」。

    entries: [(到货日 str, 数量 float), ...]；window_days: 评估窗口天数。
    规则：只有到货日 < plan_date + window_days 的在途才计入有效库存。
    晚于窗口结束才到货的在途，不能提前算进「窗口内」的缺货/覆盖评估里
    （例如评估明天起的短期风险时，5 天后才到的货不算可用库存）。
    """
    if not entries:
        return 0.0
    horizon = _window_horizon(plan_date, window_days)
    total = 0.0
    for arr, qty in entries:
        if _as_date(arr) < horizon:
            total += qty
    return total


# FEFO 前向模拟：现有批次(剩余保质期天数,数量) + 在途 + 一批「新采购」(到货 lead 天后、
# 寿命 shelf 天)，在未来逐日需求下，新采购最多能卖掉多少件 = free sellable capacity。
# 逐日最早到期先卖；到期批次售前移除；新批次仅在到货后可售；target 用于提前退出。
def _free_sellable_capacity(on_hand_batches, in_transit_entries, plan_date, daily, lead_days, shelf_life_days, target=None):
    if daily <= 1e-9:
        return 0.0
    S = max(1, int(round(float(shelf_life_days))))
    L = max(0, int(round(float(lead_days))))
    pool = []
    for rem, qty in (on_hand_batches or []):
        if qty > 1e-9:
            pool.append([0, int(round(rem)), float(qty), False])
    base = _as_date(plan_date)
    for arr, qty in (in_transit_entries or []):
        if qty <= 1e-9:
            continue
        off = (_as_date(arr) - base).days
        if off < 0:
            off = 0
        pool.append([off, off + S, float(qty), False])
    pool.append([L, L + S, float('inf'), True])
    new_sold = 0.0
    for t in range(0, L + S + 1):
        pool = [b for b in pool if b[1] > t]
        if not pool:
            break
        pool.sort(key=lambda b: (b[1], b[0]))
        need = daily
        for b in pool:
            if need <= 1e-12:
                break
            if t < b[0]:
                continue
            take = min(b[2], need)
            b[2] -= take
            need -= take
            if b[3]:
                new_sold += take
        if target is not None and new_sold >= target - 1e-9:
            break
    return new_sold


def _ceil_to_pack(qty: float, pack_size: int) -> float:
    """进货按最小包装单位向上取整 —— 补货只能整箱整包地补。"""
    if qty <= 0:
        return 0.0
    if pack_size <= 1:
        return math.ceil(qty)
    return math.ceil(qty / pack_size) * pack_size


def _floor_to_pack(money: float, cost_price: float, pack_size: int) -> float:
    """
    在给定金额内最多能买多少个整包。
    预算裁剪必须用向下取整，否则会算出超预算的方案 —— 这是原型能不能
    真跑起来的关键细节。
    """
    if cost_price <= 0 or money <= 0:
        return 0.0
    units = math.floor(money / cost_price + 1e-9)
    if pack_size <= 1:
        return max(0, units)
    return max(0, (units // pack_size) * pack_size)


def unit_margin(p: dict) -> float:
    """单件毛利额（元）。"""
    return p["sell_price"] - p["cost_price"]


def capital_efficiency(p: dict) -> float:
    """
    单位资金预期毛利 = 毛利额 / 进价。
    这是"纯利润算法"唯一的排序依据，也是它砍掉民生货品的根因。
    """
    if p["cost_price"] <= 0:
        return 0.0
    return unit_margin(p) / p["cost_price"]


def memory_safety_calibration(active, db_path=None, as_of=None) -> dict[str, dict]:
    """基于经营反馈的策略自适应（在线策略校准）。

    学习对象 = Forecast/Event 未能解释的残差，而非再次学习事件本身：
        err_ratio = (实际潜在需求 − 原预测) / 原预测
    只按「同场景（event_type 匹配）」聚合最近 MEMORY_BIAS_WINDOW 条经验，取
    均值 × MEMORY_BIAS_GAIN，再夹紧到 ±MEMORY_SAFETY_MAX_DELTA：
      · 有界 + 取均值（非连乘）→ 不会因多次误差乘法放大；
      · 用残差而非事件全效应 → 不重复学习 Event/Forecast 已解释的天气/节假日。

    「场景」= 当前生效风险事件的标签；普通日匹配 event_type == 正常。
    as_of：决策日，只统计 < as_of 的经验 → 不读取当天及未来结果。
    返回 {sku: {delta, factor, mean_err_ratio, n, scene, experiences}}。
    """
    labels = {events.EVENT_KEY_TO_LABEL[k] for k in active
              if k in events.EVENT_KEY_TO_LABEL}
    scene = "、".join(sorted(labels)) if labels else "正常"
    if not labels:
        labels = {"正常"}

    as_of_s = str(as_of)[:10] if as_of is not None else None
    out: dict[str, dict] = {}
    for ex in memory.get_experiences(limit=2000, db_path=db_path):
        sku = ex.get("sku")
        if sku is None or ex.get("event_type") not in labels:
            continue
        if as_of_s is not None and str(ex.get("day", "")) >= as_of_s:
            continue
        rec = out.get(sku)
        if rec is None:
            rec = {"errs": [], "experiences": [], "scene": scene}
            out[sku] = rec
        if len(rec["errs"]) >= MEMORY_BIAS_WINDOW:
            continue
        fq = float(ex.get("forecast_qty") or 0.0)
        if fq <= 1e-9:
            continue
        actual = float(ex.get("qty_sold") or 0.0) + float(ex.get("qty_stockout") or 0.0)
        rec["errs"].append((actual - fq) / fq)
        rec["experiences"].append(ex)

    result: dict[str, dict] = {}
    for sku, rec in out.items():
        if not rec["errs"]:
            continue
        mean_err = sum(rec["errs"]) / len(rec["errs"])
        delta = max(-MEMORY_SAFETY_MAX_DELTA,
                           min(MEMORY_SAFETY_MAX_DELTA, mean_err * MEMORY_BIAS_GAIN))
        result[sku] = {"delta": round(delta, 4), "factor": round(1.0 + delta, 4), "mean_err_ratio": round(mean_err, 4), "n": len(rec["errs"]), "scene": scene, "experiences": rec["experiences"]}
    return result


def _prepare_items(plan_date, policies: dict, products: list[dict],
                   restore_potential: bool = RESTORE_POTENTIAL, risks=None,
                   use_memory: bool = True,
                   in_transit_map: dict[str, list[tuple[str, float]]] | None = None,
                   on_hand_batches: dict[str, list[tuple[float, float]]] | None = None,
                   spoilage_control: bool = True,
                   ai_factors: dict | None = None,
                   day_scale: float = 1.0) -> tuple[list[dict], dict]:
    """算出每个商品的补货需求，并单独标出民生商品的"兜底量"。

    use_memory=False 时跳过经营记忆校准——传统纯利润算法对照组不使用小满的
    记忆学习能力，确保两种算法唯一的差别是「决策目标」而非「学没学过」。

    in_transit_map：各商品的在途订单，值为 [(到货日, 数量), ...]。给定时参与
    「建议进货 = 目标库存 − 当前库存 − 有效在途库存」与民生兜底量计算，
    其中「有效在途」= 在对应评估窗口内能真正到货的部分（见 _eligible_in_transit），
    晚到的在途不会被提前算作可用库存；缺省 None = 无在途（原单日决策行为）。

    ai_factors：AI 事件理解（core/ai_events.py）给出的品类级需求先验修正，
    透传给 forecast 层。None（默认）= 不接入，数值行为与旧版逐位一致。

    day_scale：备货节奏缩放（Agent 构造快周转候选方案用）。1.0 = 原行为；
    <1 表示少备勤补，>1 表示多备少跑。**民生兜底下限不随之缩放**。
    """
    day_scale = float(day_scale or 1.0)
    if day_scale <= 0:
        day_scale = 1.0
    active = risk.normalize(risks)
    # 只在真的有 AI 因子时才透传该参数 —— 不接入时forecast_all 的调用形态与旧版逐字相同，
    # 既保证数值零变化，也避免打破外部按旧签名封装的调用方（如测试里的 stub）。
    _fcast = {"restore_potential": restore_potential, "risks": active}
    if ai_factors:
        _fcast["ai_factors"] = ai_factors
    forecasts = forecast.forecast_all(plan_date, **_fcast)
    inventory = memory.get_inventory()
    in_transit_map = in_transit_map or {}
    on_hand_batches = on_hand_batches or {}

    # ── 基于经营反馈的策略校准：同场景、同商品的经验 → 安全系数校准量 ──
    memory_cal = memory_safety_calibration(active, as_of=plan_date) if use_memory else {}

    # ── 真实商品配置里的「品类 → 供应商」映射，用于断供时判断替代供应来源 ──
    supplier_by_category: dict[str, set[str]] = {}
    for p in products:
        supplier_by_category.setdefault(p["category"], set()).add(p.get("supplier") or "")

    items = []
    for p in products:
        sku = p["sku"]
        pol = policies.get(sku) or {"base_days": 3.0, "safety_factor": 0.15}
        fc = forecasts.get(sku) or {"daily_demand": 0.0, "holiday_note": ""}

        daily = fc["daily_demand"]
        base_days = float(pol["base_days"])
        # 基础策略参数（数据集/初始设定）→ 叠加场景匹配的经营反馈校准 → 当前策略参数
        base_safety = float(pol["safety_factor"])
        mem = memory_cal.get(sku)
        memory_delta = mem["delta"] if mem else 0.0
        memory_adjustment_factor = mem["factor"] if mem else 1.0
        safety = max(SAFETY_FACTOR_MIN, min(SAFETY_FACTOR_MAX, base_safety + memory_delta))
        lead_days = float(p.get("lead_time_days") or 0)

        # ── 目标覆盖天数：综合供应商交期 + 民生保障 + 风险环境动态计算 ──
        # ① 基础覆盖 = 供应商交期 + 补货缓冲（下次检查/补货的间隔）
        base_cover = lead_days + REVIEW_BUFFER_DAYS
        # ② 民生保障缓冲：不低于民生最低覆盖（下限，不再无条件固定 4 天）
        livelihood_buffer = 0.0
        if p["is_livelihood"] and base_cover < LIVELIHOOD_MIN_COVER_DAYS:
            livelihood_buffer = LIVELIHOOD_MIN_COVER_DAYS - base_cover
        floor_day_applied = livelihood_buffer > 1e-9
        # ③ 事件对需求的影响已由 forecast._risk_adjust 乘进 daily（唯一入口）。
        #    这里不再叠加「风险缓冲天数」，否则同一事件系数会对需求作用两次（重复计算）。
        #    供应商断供走下方的断供停止采购逻辑，节假日已在预测侧处理。
        risk_buffer = 0.0
        risk_buffer_notes = []
        # ③.5 备货节奏缩放（day_scale）：<1 表示「少备一点、多进几次」的快周转风格，
        #     >1 表示「多备一点、少跑几趟」。**只作用于非民生部分的备货节奏**，
        #     民生兜底窗口（floor_days）不受影响 —— 见下方第 1 层惠民约束。
        #     这是 Agent 构造「快周转避险候选方案」的手段，缺省 1.0 = 原行为逐位不变。
        scaled_cover = base_cover * day_scale
        target_cover_days = scaled_cover + livelihood_buffer
        # ④ 保质期上限：覆盖天数不能超过保质期允许的合理范围
        target_cover_days = min(target_cover_days, max(p["shelf_life_days"], 1.5))

        # ── 供应商断货风险：断供供应商名下的商品本次「不可采购」 ──
        # 不再对全部商品一律加安全缓冲；断供只影响断供供应商自己的货，
        # 其它供应商照常采购。
        supplier_down = ("supplier" in active) and (
            p.get("supplier") == risk.SUPPLIER_OUTAGE_NAME)
        # 替代供应来源：从真实商品配置里找「同品类、不同供应商」的可用来源；
        # 数据里没有就如实为空，绝不凭空编造「XX 可以替代」。
        alternative_suppliers = []
        if supplier_down:
            alternative_suppliers = sorted(
                s for s in supplier_by_category.get(p["category"], set())
                if s and s != risk.SUPPLIER_OUTAGE_NAME
            )

        # ── 安全库存（加法项，每个来源都可解释，绝不与预测需求重复乘）──
        # 安全缓冲天数 = 目标覆盖天数 × 安全库存系数。若长期记忆里有「同场景、同商品」
        # 的经营反馈，则用校准后的安全系数（在线策略校准）真正参与计算，而非只展示。
        base_safety_days = target_cover_days * base_safety
        safety_days = target_cover_days * safety
        if memory_delta > 1e-9:
            safety_sources = [
                f"基础安全系数 {base_safety:.2f} × 覆盖 {target_cover_days:.1f} 天 = {base_safety_days:.2f} 天",
                f"经营反馈校准：{mem['scene']}下预测偏低，安全系数 {base_safety:.2f} → {safety:.2f}（+{memory_delta:.2f}）",
            ]
        elif memory_delta < -1e-9:
            safety_sources = [
                f"基础安全系数 {base_safety:.2f} × 覆盖 {target_cover_days:.1f} 天 = {base_safety_days:.2f} 天",
                f"经营反馈校准：{mem['scene']}下预测偏高，安全系数 {base_safety:.2f} → {safety:.2f}（{memory_delta:.2f}）",
            ]
        else:
            safety_sources = [
                f"安全系数 {safety:.2f} × 覆盖 {target_cover_days:.1f} 天 = {base_safety_days:.2f} 天"
            ]
        safety_stock = daily * safety_days

        on_hand = inventory.get(sku, 0.0)
        # 现有批次（剩余保质期天数, 数量）：长期仿真传入真实批次；单日决策缺省 None →
        # 把 on_hand 视为「刚入库、剩余寿命 = 保质期」的单个批次（保守，不夸大积压）。
        batches = on_hand_batches.get(sku)
        if batches is None:
            batches = [(p["shelf_life_days"], on_hand)] if on_hand > 1e-9 else []
        # 在途库存：单日决策缺省为 0（供应商交期已由目标覆盖天数吸收）；
        # 长期仿真由 simulator 传入带「到货日」的在途订单，避免重复下单。
        entries = in_transit_map.get(sku) or []
        in_transit = sum(q for _, q in entries)              # 总在途（展示用）
        # 有效在途：只在「目标覆盖窗口」内能到货的部分才计入补货需求/韧性缺口
        eligible_in_transit = _eligible_in_transit(entries, plan_date, target_cover_days)

        # ── 目标库存 = 预测需求 × 目标覆盖天数 + 安全库存 ──
        target_stock = daily * target_cover_days + safety_stock
        # ── 建议进货 = max(0, 目标库存 - 当前库存 - 有效在途库存) ──
        need = max(0.0, target_stock - on_hand - eligible_in_transit)
        raw_reorder = _ceil_to_pack(need, p["pack_size"])

        # 现有库存能撑几天（供断供预警使用）
        supply_cover_days = on_hand / daily if daily > 0 else 99.0

        # ── 惠民约束第 1 层：算出"兜底量"（只在预算紧张时启用）──
        # 注意：兜底天数由**未缩放**的基础覆盖与民生下限决定，快周转方案（day_scale<1）
        # 也不许把民生商品的兜底压到买不到米面油盐 —— 这是本项目的硬底线。
        floor_days = min(base_cover + livelihood_buffer, LIVELIHOOD_MIN_COVER_DAYS)
        if p["is_livelihood"]:
            floor_stock = daily * floor_days
            # 兜底窗口更短（≤ 目标覆盖窗口），单独按兜底窗口筛有效在途
            eligible_in_transit_floor = _eligible_in_transit(entries, plan_date, floor_days)
            floor_need = max(0.0, min(floor_stock, target_stock) - on_hand - eligible_in_transit_floor)
            floor_qty = min(_ceil_to_pack(floor_need, p["pack_size"]), raw_reorder)
        else:
            floor_qty = 0.0

        # ── 损耗风险控制（第4.2步）：短保商品采购上限（约束，不改 R³ 目标）──
        raw_reorder_uncapped = raw_reorder
        if spoilage_control:
            free_sellable_capacity = _free_sellable_capacity(
                batches, entries, plan_date, daily, lead_days, p["shelf_life_days"],
                target=raw_reorder_uncapped)
            effective_cap = max(floor_qty, free_sellable_capacity)
            raw_reorder = min(raw_reorder_uncapped, _ceil_to_pack(effective_cap, p['pack_size']))
        else:
            free_sellable_capacity = raw_reorder_uncapped
        expected_excess_qty = max(0.0, raw_reorder_uncapped - free_sellable_capacity)
        expected_spoilage_cost = expected_excess_qty * p['cost_price']
        spoilage_capped = raw_reorder < raw_reorder_uncapped - 1e-9

        # ── 断供商品本次不可采购：需求与库存照算，补货量归零 ──
        if supplier_down:
            raw_reorder = 0.0
            floor_qty = 0.0
            expected_excess_qty = 0.0
            expected_spoilage_cost = 0.0
            spoilage_capped = False

        risk_note = fc.get("risk_note", "")
        if supplier_down:
            sup = f"{risk.SUPPLIER_OUTAGE_NAME}断供，本次不可采购"
            risk_note = f"{risk_note}；{sup}" if risk_note else sup

        items.append({
            "sku": sku,
            "name": p["name"],
            "category": p["category"],
            "supplier": p["supplier"],
            "alternative_suppliers": alternative_suppliers,
            "has_alternative": bool(alternative_suppliers),
            "unit": p["unit"],
            "is_livelihood": int(p["is_livelihood"]),
            "cost_price": p["cost_price"],
            "sell_price": p["sell_price"],
            "pack_size": p["pack_size"],
            "shelf_life_days": p["shelf_life_days"],
            "traffic_pull": p["traffic_pull"],
            "daily_demand": round(daily, 2),
            "base_days": round(base_days, 2),
            "base_safety_factor": round(base_safety, 3),
            "safety_factor": round(safety, 3),
            "memory_delta": round(memory_delta, 4),
            "memory_adjustment_factor": round(memory_adjustment_factor, 4),
            "memory_scene": (mem["scene"] if mem else ""),
            "target_cover_days": round(target_cover_days, 2),
            "lead_time_days": round(lead_days, 1),
            "review_buffer_days": round(REVIEW_BUFFER_DAYS, 1),
            "livelihood_buffer_days": round(livelihood_buffer, 2),
            "risk_buffer_days": round(risk_buffer, 2),
            "risk_buffer_note": "；".join(risk_buffer_notes),
            "safety_stock": round(safety_stock, 1),
            "safety_stock_days": round(safety_days, 2),
            "safety_note": "；".join(safety_sources),
            "in_transit": round(in_transit, 1),
            "eligible_in_transit": round(eligible_in_transit, 1),
            "floor_days": round(floor_days, 2),
            "floor_day_applied": floor_day_applied,
            "holiday_note": fc.get("holiday_note", ""),
            "promo_note": fc.get("promo_note", ""),
            "risk_note": risk_note,
            "risk_factor": round(fc.get("risk_factor", 1.0), 3),
            "target_stock": round(target_stock, 1),
            "on_hand": round(on_hand, 1),
            "supply_cover_days": round(supply_cover_days, 1),
            "supplier_down": supplier_down,
            "need_qty": round(need, 1),
            "raw_reorder": raw_reorder,
            "raw_reorder_uncapped": raw_reorder_uncapped,
            "spoilage_capped": spoilage_capped,
            "sellable_capacity": round(daily * p["shelf_life_days"], 1),
            "free_sellable_capacity": round(free_sellable_capacity, 1),
            "expected_excess_qty": round(expected_excess_qty, 1),
            "expected_spoilage_cost": round(expected_spoilage_cost, 2),
            "raw_cost": round(raw_reorder * p["cost_price"], 2),
            "floor_qty": floor_qty,
            "floor_cost": round(floor_qty * p["cost_price"], 2),
            "unit_margin": round(unit_margin(p), 2),
            "capital_eff": round(capital_efficiency(p), 4),
        })

    meta = {
        "total_need_cost": round(sum(it["raw_cost"] for it in items), 2),
        "livelihood_need_cost": round(
            sum(it["raw_cost"] for it in items if it["is_livelihood"]), 2),
        "livelihood_floor_cost": round(
            sum(it["floor_cost"] for it in items if it["is_livelihood"]), 2),
        "expected_spoilage_cost": round(
            sum(it["expected_spoilage_cost"] for it in items), 2),
    }

    # ── 断供供应商的受影响商品清单（供界面与决策过程展示）──
    # 替代供应来源：读取真实商品配置，判断是否有其他供应商供应同类商品；
    # 数据里没有就如实为空，绝不为了展示效果凭空编造「XX 可以替代」。
    outage_items = [it for it in items if it["supplier_down"]]
    meta["supplier_outage"] = {
        "supplier": risk.SUPPLIER_OUTAGE_NAME,
        "affected_count": len(outage_items),
        "livelihood_count": sum(1 for it in outage_items if it["is_livelihood"]),
        "has_alternative": any(it["has_alternative"] for it in outage_items),
        "products": [
            {
                "sku": it["sku"], "name": it["name"], "category": it["category"],
                "is_livelihood": it["is_livelihood"], "unit": it["unit"],
                "supplier": it["supplier"],
                "on_hand": it["on_hand"], "daily_demand": it["daily_demand"],
                "cover_days": it["supply_cover_days"],
                "alternative_suppliers": it["alternative_suppliers"],
                "has_alternative": it["has_alternative"],
            }
            for it in outage_items
        ],
    }
    # 备货节奏缩放写进 meta，供页面与 Agent 决策台如实展示（1.0 = 未缩放）
    meta["day_scale"] = day_scale
    return items, meta


def _allocate(items: list[dict], budget: float, protect_livelihood: bool) -> dict:
    """在预算约束下分配进货额度，返回分配元信息。"""
    for it in items:
        it["reorder_qty"] = 0.0
        it["cost"] = 0.0
        it["trimmed"] = False
        it["trim_note"] = ""
        it["floor_secured"] = None

    total_need = sum(it["raw_cost"] for it in items)
    meta = {
        "budget": round(budget, 2),
        "total_need_cost": round(total_need, 2),
        "budget_tight": total_need > budget + 1e-6,
        "shortfall": round(max(0.0, total_need - budget), 2),
        "livelihood_floor_secured": None,
        "livelihood_locked_cost": 0.0,
        "overflow": 0.0,
    }

    remaining = budget

    # ── 惠民约束第 1 层：先锁民生兜底量 ──
    if protect_livelihood:
        liv = [it for it in items if it["is_livelihood"] and it["floor_qty"] > 0]
        # 民生内部优先级：客流带动系数 × 缺口，同分按 SKU 字典序（确定性，与遍历顺序无关）
        liv_sorted = sorted(
            liv,
            key=lambda x: (-(x["traffic_pull"] * max(x["need_qty"], 0.001)), x["capital_eff"], x["sku"]),
        )
        locked = 0.0
        for it in liv_sorted:
            want = it["floor_cost"]
            if want <= remaining + 1e-6:
                it["reorder_qty"] = it["floor_qty"]
                it["cost"] = want
                it["floor_secured"] = True
                remaining -= it["cost"]
                locked += it["cost"]
            else:
                # ── 惠民约束第 3 层：预算实在不够，能买多少买多少 ──
                qty = _floor_to_pack(remaining, it["cost_price"], it["pack_size"])
                qty = min(qty, it["floor_qty"])
                it["reorder_qty"] = qty
                it["cost"] = round(qty * it["cost_price"], 2)
                it["floor_secured"] = qty >= it["floor_qty"] - 1e-6
                it["trimmed"] = True
                it["trim_note"] = "预算不足，已按惠民底线优先保障"
                remaining -= it["cost"]
                locked += it["cost"]

        meta["livelihood_locked_cost"] = round(locked, 2)
        # 保障率口径统一为按 SKU 计数（与 calculate_essential_coverage / MILP 一致）
        all_liv = [it for it in items if it["is_livelihood"]]
        secured_cnt = sum(1 for it in all_liv if it["reorder_qty"] >= it["floor_qty"] - 1e-6)
        meta["livelihood_floor_secured"] = (
            round(secured_cnt / len(all_liv), 3) if all_liv else 1.0
        )

    # ── 惠民约束第 2 层：剩余额度按资金效率分配给增量需求 ──
    increments = []
    for it in items:
        gap = it["raw_reorder"] - it["reorder_qty"]
        if gap > 0:
            increments.append((it, gap, round(gap * it["cost_price"], 2)))
    increments.sort(key=lambda t: (-t[0]["capital_eff"], t[0]["sku"]))

    for it, gap, gap_cost in increments:
        if gap_cost <= remaining + 1e-6:
            it["reorder_qty"] += gap
            it["cost"] = round(it["cost"] + gap_cost, 2)
            remaining -= gap_cost
        elif remaining > 0:
            qty = _floor_to_pack(remaining, it["cost_price"], it["pack_size"])
            qty = min(qty, gap)
            if qty > 0:
                it["reorder_qty"] += qty
                it["cost"] = round(it["cost"] + qty * it["cost_price"], 2)
                it["trimmed"] = True
                it["trim_note"] = it["trim_note"] or "预算受限，部分满足"
                remaining -= qty * it["cost_price"]

    meta["overflow"] = round(max(0.0, remaining), 2)
    return meta


def _allocate_plan(items: list[dict], budget: float, mode: str,
                   solver: bool | None = None,
                   protect_livelihood: bool | None = None) -> dict:
    """最终采购分配入口：优先走 R³ MILP，关闭/不可用/失败时回退贪心。

    无论走哪条路，都保证改写出与 _allocate 完全一致的 item 字段
    （reorder_qty / cost / trimmed / trim_note / floor_secured），并在 meta 里带上
    solver 信息，供「小满 Agent 决策过程」第 6 步与页面真实展示。

    protect_livelihood=None 时沿用 mode 语义（diannao=True / baseline=False）；
    显式传入可覆盖 —— 供长期仿真的消融实验「小满 − R³责任目标」使用
    （仍走 MILP 的收益+韧性阶段，只是不锁民生兜底，而非退回纯贪心）。
    """
    is_diannao = mode == MODE_DIANNAO
    protect = is_diannao if protect_livelihood is None else bool(protect_livelihood)
    use_milp = is_diannao and (R3_SOLVER_ENABLED if solver is None else bool(solver))
    # 降级原因：用于 meta.solver.degraded_reason，让「本次没走 MILP」这件事
    # 在数据层可追溯（不改变任何 UI，也不改变补货数字）。
    degraded_reason = None
    if use_milp:
        try:
            from . import r3_optimizer
            if r3_optimizer.available():
                return r3_optimizer.solve(items, budget, protect_livelihood=protect)
            degraded_reason = "solver_unavailable"
        except Exception as exc:  # noqa: BLE001
            # 求解器异常 → 回退原贪心，绝不崩；但**记录原因**，
            # 避免「静默降级」变成无法追溯的黑盒。
            degraded_reason = f"{type(exc).__name__}: {exc}"[:200]
    elif is_diannao and not use_milp:
        degraded_reason = "disabled_by_config"

    meta = _allocate(items, budget, protect_livelihood=protect)
    meta.setdefault("solver", {
        "used_milp": False,
        "name": "规则/贪心（fallback）",
        "status": "Fallback",
    })
    if degraded_reason:
        meta["solver"]["degraded_reason"] = degraded_reason
    return meta


def calculate_essential_coverage(items: list[dict]) -> dict:
    """民生最低保障达标率（全站唯一口径，所有页面组件必须读这里的结果，禁止另算）。

    定义：达到最低保障库存要求的民生 SKU 数 ÷ 全部民生 SKU 数 × 100%。
    「达到」= 补货后的可用库存（on_hand + reorder_qty）达到 floor_qty 这个
    最低保障补货量；floor_qty 本身由「最低保障库存量 - 现有库存」向上取整到
    整件得出，因此它等价于「补货后库存 ≥ 最低保障库存量」，只是用整件口径表达。

    同时给出「距离 100% 还需要增加的钱」= 未达标商品的缺口整件 × 进价，
    这个缺口不是写死的，而是从真实成本 / 缺口数量 / 最低保障量实时算出来的。
    """
    total = secured = 0
    shortfall = 0.0
    for it in items:
        if not it["is_livelihood"]:
            continue
        total += 1
        gap = it["floor_qty"] - it["reorder_qty"]
        if gap > 1e-6:
            # 还没补到最低保障量：缺口整件 × 进价 = 距离 100% 还需要增加的钱
            shortfall += gap * it["cost_price"]
        else:
            secured += 1
    return {
        "secured_count": secured,
        "total_count": total,
        "rate": round(metrics.livelihood_secured_rate(secured, total), 4),
        "shortfall_cost": round(shortfall, 2),
    }


def evaluate_plan(items: list[dict], meta: dict) -> dict:
    """对一份补货方案做双目标评估：门店收益 + 社区便民价值。"""
    gross_margin = 0.0
    total_cost = 0.0
    margin_positive = 0.0
    liv_weight_num = liv_weight_den = 0.0
    traffic_score = 0.0
    stockout_risk = 0
    demand_units = 0.0        # 补货周期内预期总需求（件）——缺货率的分母
    stockout_units = 0.0      # 预计缺货数量（件）= 覆盖不足的需求缺口
    spoilage_cost = 0.0       # 预计损耗金额（元）= 短保商品超出保质期可售量的库存

    for it in items:
        total_cost += it["cost"]
        gross_margin += it["reorder_qty"] * it["unit_margin"]
        if it["unit_margin"] > 0:
            margin_positive += it["unit_margin"]

        supply = it["on_hand"] + it.get("eligible_in_transit", 0.0) + it["reorder_qty"]
        cover = supply / it["daily_demand"] if it["daily_demand"] > 0 else 99.0
        it["final_cover_days"] = round(cover, 2)

        # ── 缺货缺口（件）与损耗风险（元）：两种算法同口径、纯数据驱动 ──
        if it["daily_demand"] > 0:
            horizon_need = it["daily_demand"] * it["target_cover_days"]
            demand_units += horizon_need
            shortfall = horizon_need - supply
            if shortfall > 1e-9:
                stockout_units += shortfall
            shelf = float(it.get("shelf_life_days") or 0.0)
            if 0 < shelf <= PERISHABLE_SHELF_LIFE_DAYS:
                over = supply - it["daily_demand"] * shelf
                if over > 1e-9:
                    spoilage_cost += metrics.expected_spoilage_cost(over, it["cost_price"])

        if it["is_livelihood"]:
            # 便民达成度：覆盖天数相对惠民底线（3 天）的达成比例
            ratio = min(1.0, cover / LIVELIHOOD_MIN_COVER_DAYS)
            weight = max(it["daily_demand"], 0.5) * it["traffic_pull"]
            liv_weight_num += ratio * weight
            liv_weight_den += weight
            traffic_score += ratio * it["traffic_pull"]

        if it["daily_demand"] > 0 and cover < 2.0:
            stockout_risk += 1
            it["stockout_risk"] = True
        else:
            it["stockout_risk"] = False

    livelihood_index = (liv_weight_num / liv_weight_den) if liv_weight_den > 0 else 1.0
    coverage = calculate_essential_coverage(items)

    return {
        "total_cost": round(total_cost, 2),
        "gross_margin": round(gross_margin, 2),
        "margin_rate": round(gross_margin / total_cost, 4) if total_cost > 0 else 0.0,
        "livelihood_index": round(livelihood_index, 4),
        "livelihood_secured_rate": coverage["rate"],
        "livelihood_secured_count": coverage["secured_count"],
        "livelihood_total_count": coverage["total_count"],
        "livelihood_floor_shortfall": coverage["shortfall_cost"],
        "traffic_score": round(traffic_score, 2),
        "stockout_risk_count": stockout_risk,
        "stockout_units": round(stockout_units, 1),
        "stockout_rate": round(metrics.expected_stockout_rate(stockout_units, demand_units), 4),
        "spoilage_cost": round(spoilage_cost, 2),
        "display_count": sum(1 for it in items if it["reorder_qty"] > 0),
        "budget": meta["budget"],
        "budget_used_rate": round(total_cost / meta["budget"], 4) if meta["budget"] > 0 else 0.0,
    }


def build_plan(plan_date, budget: float = DEFAULT_BUDGET, mode: str = MODE_DIANNAO,
               persist: bool = True, restore_potential: bool = RESTORE_POTENTIAL, risks=None,
               solver: bool | None = None, use_memory: bool = True,
               protect_livelihood: bool | None = None,
               in_transit_map: dict[str, list[tuple[str, float]]] | None = None,
               on_hand_batches: dict[str, list[tuple[float, float]]] | None = None,
               spoilage_control: bool = True,
               ai_factors: dict | None = None,
               day_scale: float = 1.0) -> dict:
    """
    生成补货方案。

    mode = "diannao"   → 带惠民约束（本项目方案）
    mode = "baseline"  → 传统纯利润算法（对照组，用于体现差异）
    risks               → 生效的风险事件键列表（暴雨/高温/节假日/供应商断货）
    solver              → 是否用 R³ MILP 求解器升级分配层；None 表示跟随全局开关
                          （config.R3_SOLVER_ENABLED）。求解器不可用/失败时自动回退贪心。
    use_memory          → 是否启用经营记忆校准（安全库存系数学习）；传统算法对照组传 False。
    protect_livelihood  → None 时沿用 mode 语义；显式传入可覆盖民生兜底开关（消融实验用）。
    in_transit_map      → 各商品在途订单 [(到货日, 数量), ...]（长期仿真用）；
                          缺省 None = 无在途（原单日行为）。
    ai_factors          → AI 事件理解给出的品类级需求先验修正（core/ai_events.py）。
                          **只影响需求预测侧，不决定补货数量**；None = 不接入，
                          此时输出与未接入 AI 逐位一致（降级保证，见 ARD T-AI-04）。
    day_scale           → 备货节奏缩放（Agent 构造快周转候选方案用）。1.0 = 原行为，
                          <1 = 少备勤补（快周转），>1 = 多备少跑。**不影响民生兜底下限**。
    """
    products = memory.get_products()
    policies = memory.get_all_policy()
    active = risk.normalize(risks)

    items, prep = _prepare_items(plan_date, policies, products, restore_potential,
                                 risks=active, use_memory=use_memory,
                                 in_transit_map=in_transit_map, on_hand_batches=on_hand_batches,
                                 spoilage_control=spoilage_control, ai_factors=ai_factors,
                                 day_scale=day_scale)
    meta = _allocate_plan(items, budget, mode, solver=solver,
                          protect_livelihood=protect_livelihood)
    meta.update({k: v for k, v in prep.items() if k not in meta})
    metrics = evaluate_plan(items, meta)

    if persist:
        memory.log_plan(
            str(plan_date), mode,
            [{
                "sku": it["sku"],
                "forecast_daily": it["daily_demand"],
                "target_cover_days": it["target_cover_days"],
                "target_stock": it["target_stock"],
                "on_hand": it["on_hand"],
                "reorder_qty": it["reorder_qty"],
                "cost": it["cost"],
                "is_livelihood": it["is_livelihood"],
                "trimmed": int(it["trimmed"]),
            } for it in items],
        )

    return {
        "date": str(plan_date),
        "budget": budget,
        "mode": mode,
        "mode_label": MODE_LABELS[mode],
        "items": items,
        "meta": meta,
        "metrics": metrics,
        "risks": active,
        "risk_summary": risk.summary(active),
        # AI 决策中枢：本轮实际生效的品类级修正（None = 未接入，供页面区分展示）
        "ai_factors": dict(ai_factors) if ai_factors else None,
    }


def compare_plans(plan_date, budget: float = DEFAULT_BUDGET, persist: bool = False,
                  restore_potential: bool = RESTORE_POTENTIAL, risks=None) -> dict:
    """
    同一天、同一预算下，对比"小满"与"传统纯利润算法"的两份方案。
    这是现场演示与答辩最有说服力的一张对比表。
    """
    active = risk.normalize(risks)
    diannao = build_plan(plan_date, budget, MODE_DIANNAO, persist=persist,
                         restore_potential=restore_potential, risks=active,
                         use_memory=True)
    baseline = build_plan(plan_date, budget, MODE_BASELINE, persist=persist,
                          restore_potential=restore_potential, risks=active,
                          use_memory=False)

    by_sku_b = {it["sku"]: it for it in baseline["items"]}
    diff = []
    for it in diannao["items"]:
        b = by_sku_b.get(it["sku"], {})
        diff.append({
            "sku": it["sku"],
            "name": it["name"],
            "category": it["category"],
            "unit": it["unit"],
            "is_livelihood": it["is_livelihood"],
            "daily_demand": it["daily_demand"],
            "diannao_qty": it["reorder_qty"],
            "baseline_qty": b.get("reorder_qty", 0.0),
            "delta": round(it["reorder_qty"] - b.get("reorder_qty", 0.0), 1),
            "diannao_cover": it.get("final_cover_days", 0),
            "baseline_cover": b.get("final_cover_days", 0),
            "diannao_cost": it["cost"],
            "baseline_cost": b.get("cost", 0.0),
        })

    m_d, m_b = diannao["metrics"], baseline["metrics"]
    return {
        "date": str(plan_date),
        "budget": budget,
        "risks": active,
        "risk_summary": risk.summary(active),
        "diannao": diannao,
        "baseline": baseline,
        "diff": diff,
        "delta": {
            "gross_margin": round(m_d["gross_margin"] - m_b["gross_margin"], 2),
            "livelihood_index": round(m_d["livelihood_index"] - m_b["livelihood_index"], 4),
            "livelihood_gap": round(1.0 - m_b["livelihood_index"], 4),
            "stockout_risk_count": m_d["stockout_risk_count"] - m_b["stockout_risk_count"],
            "stockout_units": round(m_d["stockout_units"] - m_b["stockout_units"], 1),
            "stockout_rate": round(m_d["stockout_rate"] - m_b["stockout_rate"], 4),
            "inventory_capital": round(m_d["total_cost"] - m_b["total_cost"], 2),
            "spoilage_cost": round(m_d["spoilage_cost"] - m_b["spoilage_cost"], 2),
            # 商户为便民价值付出的直接毛利代价 —— 坦诚展示，主动回应"凭什么用"
            "margin_cost_of_livelihood": round(m_b["gross_margin"] - m_d["gross_margin"], 2),
        },
    }
