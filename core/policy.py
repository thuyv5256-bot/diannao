# -*- coding: utf-8 -*-
"""
店脑 · 补货决策模块（创新点 1 的技术实体：带惠民约束的 Agent 决策逻辑）

═══ 问题的本质 ═══
夫妻小店的进货预算有限。传统的"利润最大化"算法会怎么做？
它按「单位资金预期毛利」排序分配预算 —— 高毛利的薯片、巧克力、坚果排前面，
低毛利的食盐、大米、瓶装水排后面。预算一紧，砍掉的永远是民生商品。
结果：门店短期毛利好看了，但社区居民买不到平价米面油盐，
     客流被削掉，连带销售一起掉 —— 这是典型的"算法短视"。

═══ 店脑的做法：三层惠民约束 ═══
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

from . import forecast, memory
from .config import (
    DEFAULT_BUDGET,
    LIVELIHOOD_BASE_DAYS_MIN,
    LIVELIHOOD_MIN_COVER_DAYS,
)

MODE_DIANNAO = "diannao"
MODE_BASELINE = "baseline"
MODE_LABELS = {
    MODE_DIANNAO: "店脑（惠民约束版）",
    MODE_BASELINE: "传统算法（纯利润优先）",
}


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


def _prepare_items(plan_date, policies: dict, products: list[dict]) -> tuple[list[dict], dict]:
    """算出每个商品的补货需求，并单独标出民生商品的"兜底量"。"""
    forecasts = forecast.forecast_all(plan_date)
    inventory = memory.get_inventory()

    items = []
    for p in products:
        sku = p["sku"]
        pol = policies.get(sku) or {"base_days": 3.0, "safety_factor": 0.15}
        fc = forecasts.get(sku) or {"daily_demand": 0.0, "holiday_note": ""}

        daily = fc["daily_demand"]
        base_days = float(pol["base_days"])
        safety = float(pol["safety_factor"])

        # 期望备货水平 = 基准备货天数 ×(1 + 安全库存系数)
        cover_days = base_days * (1.0 + safety)

        # ── 惠民约束：民生商品的期望备货水平有下限（不许被压得太低）──
        floor_day_applied = False
        if p["is_livelihood"] and cover_days < LIVELIHOOD_MIN_COVER_DAYS:
            cover_days = LIVELIHOOD_MIN_COVER_DAYS
            floor_day_applied = True

        # 备货天数不能超过保质期
        cover_days = min(cover_days, max(p["shelf_life_days"], 1.5))

        on_hand = inventory.get(sku, 0.0)
        target_stock = daily * cover_days
        need = max(0.0, target_stock - on_hand)
        raw_reorder = _ceil_to_pack(need, p["pack_size"])

        # ── 惠民约束第 1 层：算出"兜底量"（只在预算紧张时启用）──
        floor_days = min(cover_days, LIVELIHOOD_MIN_COVER_DAYS)
        if p["is_livelihood"]:
            floor_stock = daily * floor_days
            floor_need = max(0.0, min(floor_stock, target_stock) - on_hand)
            floor_qty = min(_ceil_to_pack(floor_need, p["pack_size"]), raw_reorder)
        else:
            floor_qty = 0.0

        items.append({
            "sku": sku,
            "name": p["name"],
            "category": p["category"],
            "unit": p["unit"],
            "is_livelihood": int(p["is_livelihood"]),
            "cost_price": p["cost_price"],
            "sell_price": p["sell_price"],
            "pack_size": p["pack_size"],
            "shelf_life_days": p["shelf_life_days"],
            "traffic_pull": p["traffic_pull"],
            "daily_demand": round(daily, 2),
            "base_days": round(base_days, 2),
            "safety_factor": round(safety, 3),
            "target_cover_days": round(cover_days, 2),
            "floor_days": round(floor_days, 2),
            "floor_day_applied": floor_day_applied,
            "holiday_note": fc.get("holiday_note", ""),
            "target_stock": round(target_stock, 1),
            "on_hand": round(on_hand, 1),
            "need_qty": round(need, 1),
            "raw_reorder": raw_reorder,
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
    }
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
        # 民生内部优先级：客流带动系数 × 缺口，最能引客流的先保
        liv_sorted = sorted(
            liv,
            key=lambda x: (-(x["traffic_pull"] * max(x["need_qty"], 0.001)), x["capital_eff"]),
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

        floor_total = sum(x["floor_cost"] for x in liv)
        meta["livelihood_locked_cost"] = round(locked, 2)
        meta["livelihood_floor_secured"] = (
            round(min(1.0, locked / floor_total), 3) if floor_total > 0 else 1.0
        )

    # ── 惠民约束第 2 层：剩余额度按资金效率分配给增量需求 ──
    increments = []
    for it in items:
        gap = it["raw_reorder"] - it["reorder_qty"]
        if gap > 0:
            increments.append((it, gap, round(gap * it["cost_price"], 2)))
    increments.sort(key=lambda t: -t[0]["capital_eff"])

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


def evaluate_plan(items: list[dict], meta: dict) -> dict:
    """对一份补货方案做双目标评估：门店收益 + 社区便民价值。"""
    gross_margin = 0.0
    total_cost = 0.0
    margin_positive = 0.0
    liv_weight_num = liv_weight_den = 0.0
    traffic_score = 0.0
    stockout_risk = 0

    for it in items:
        total_cost += it["cost"]
        gross_margin += it["reorder_qty"] * it["unit_margin"]
        if it["unit_margin"] > 0:
            margin_positive += it["unit_margin"]

        supply = it["on_hand"] + it["reorder_qty"]
        cover = supply / it["daily_demand"] if it["daily_demand"] > 0 else 99.0
        it["final_cover_days"] = round(cover, 2)

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

    return {
        "total_cost": round(total_cost, 2),
        "gross_margin": round(gross_margin, 2),
        "margin_rate": round(gross_margin / total_cost, 4) if total_cost > 0 else 0.0,
        "livelihood_index": round(livelihood_index, 4),
        "traffic_score": round(traffic_score, 2),
        "stockout_risk_count": stockout_risk,
        "display_count": sum(1 for it in items if it["reorder_qty"] > 0),
        "budget": meta["budget"],
        "budget_used_rate": round(total_cost / meta["budget"], 4) if meta["budget"] > 0 else 0.0,
    }


def build_plan(plan_date, budget: float = DEFAULT_BUDGET, mode: str = MODE_DIANNAO,
               persist: bool = True) -> dict:
    """
    生成补货方案。

    mode = "diannao"   → 带惠民约束（本项目方案）
    mode = "baseline"  → 传统纯利润算法（对照组，用于体现差异）
    """
    products = memory.get_products()
    policies = memory.get_all_policy()

    items, prep = _prepare_items(plan_date, policies, products)
    meta = _allocate(items, budget, protect_livelihood=(mode == MODE_DIANNAO))
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
    }


def compare_plans(plan_date, budget: float = DEFAULT_BUDGET, persist: bool = False) -> dict:
    """
    同一天、同一预算下，对比"店脑"与"传统纯利润算法"的两份方案。
    这是现场演示与答辩最有说服力的一张对比表。
    """
    diannao = build_plan(plan_date, budget, MODE_DIANNAO, persist=persist)
    baseline = build_plan(plan_date, budget, MODE_BASELINE, persist=persist)

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
        "diannao": diannao,
        "baseline": baseline,
        "diff": diff,
        "delta": {
            "gross_margin": round(m_d["gross_margin"] - m_b["gross_margin"], 2),
            "livelihood_index": round(m_d["livelihood_index"] - m_b["livelihood_index"], 4),
            "livelihood_gap": round(1.0 - m_b["livelihood_index"], 4),
            "stockout_risk_count": m_d["stockout_risk_count"] - m_b["stockout_risk_count"],
            # 商户为便民价值付出的直接毛利代价 —— 坦诚展示，主动回应"凭什么用"
            "margin_cost_of_livelihood": round(m_b["gross_margin"] - m_d["gross_margin"], 2),
        },
    }
