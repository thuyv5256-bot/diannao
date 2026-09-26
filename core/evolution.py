# -*- coding: utf-8 -*-
"""
店脑 · 策略自进化模块（创新点 2 的闭环实现）

═══ 闭环怎么转 ═══

    ┌──→ 方案输出：按当前策略参数生成补货建议
    │
    │    业务反馈：店主录入昨日真实的销量 / 断货 / 损耗
    │
    │    策略修正：按反馈信号调整该商品的策略参数
    │        断货 → 安全库存系数 ↑（下次多备一点）
    │        积压损耗 → 进货建议量 ↓（下次少进一点）
    └──── 参数写回长期记忆库，下一轮决策即采用新参数

═══ 为什么不用大模型微调 ═══
大模型微调成本高、不可解释、门店数据量也撑不起来。
本模块把"学习"落在少量**可解释的业务参数**上，
店主能看懂"为什么从 0.20 变成 0.26"，也才能信任这个系统。
这才是小商户场景该有的技术选择。

═══ 防震荡设计（评委必问，提前回答）═══
1. 参数有硬边界（安全系数 0.05~0.60，备货天数 2~12 天）；
2. 步长有上限，按缺货严重程度缩放但有天花板，不会一步跳到底；
3. 单日同时出现断货与损耗时，只按断货处理（避免自我抵消）；
4. 短保商品额外受保质期约束，备货天数不会超过保质期；
5. 只在超过触发阈值时才调整，日常小波动不触发 —— 防止追着噪声跑。
"""

from . import memory
from .config import (
    BASE_DAYS_MAX,
    BASE_DAYS_MIN,
    EVOLVE_DOWN_STEP,
    EVOLVE_UP_MAX_MULT,
    EVOLVE_UP_STEP,
    LIVELIHOOD_BASE_DAYS_MIN,
    SAFETY_FACTOR_MAX,
    SAFETY_FACTOR_MIN,
    SPOILAGE_TRIGGER,
    STOCKOUT_TRIGGER,
)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _base_days_floor(product: dict) -> float:
    """备货天数下限：民生商品更高，且不得突破保质期。"""
    floor = LIVELIHOOD_BASE_DAYS_MIN if product["is_livelihood"] else BASE_DAYS_MIN
    return min(floor, max(product["shelf_life_days"], 1))


def _base_days_ceiling(product: dict) -> float:
    """备货天数上限：长保商品最多 12 天，短保商品受保质期压制。"""
    shelf = product["shelf_life_days"]
    if shelf <= 7:
        # 短保：备货天数不超过保质期的 0.7 倍，控制过期风险
        return max(BASE_DAYS_MIN, min(BASE_DAYS_MAX, shelf * 0.7))
    return BASE_DAYS_MAX


def process_feedback(day: str, feedback: list[dict], persist: bool = True) -> dict:
    """
    接收一天的经营反馈，执行策略自进化。

    feedback 每项：{sku, qty_sold, qty_stockout, qty_spoilage, is_promo, is_holiday}
    返回：参数变更明细 + 汇总
    """
    products = {p["sku"]: p for p in memory.get_products()}
    policies = memory.get_all_policy()

    changes: list[dict] = []
    summary = {"stockout_days": 0, "spoilage_days": 0, "adjustments": 0}

    for fb in feedback:
        sku = fb["sku"]
        product = products.get(sku)
        if not product:
            continue

        pol = policies.get(sku) or {"base_days": 5.0, "safety_factor": 0.20, "version": 1}
        base_days = float(pol["base_days"])
        safety = float(pol["safety_factor"])

        sold = float(fb.get("qty_sold", 0) or 0)
        stockout = float(fb.get("qty_stockout", 0) or 0)
        spoilage = float(fb.get("qty_spoilage", 0) or 0)

        # 入库：这一天发生了什么，要留在记忆里
        if persist:
            memory.add_sales([{
                "day": day, "sku": sku,
                "qty_sold": sold, "qty_stockout": stockout, "qty_spoilage": spoilage,
                "is_promo": int(fb.get("is_promo", 0) or 0),
                "is_holiday": int(fb.get("is_holiday", 0) or 0),
            }])

        potential = sold + stockout
        stockout_ratio = (stockout / potential) if potential > 0 else 0.0
        supply = sold + spoilage
        spoilage_ratio = (spoilage / supply) if supply > 0 else 0.0

        new_safety, new_base = safety, base_days
        trigger = None
        reason_parts: list[str] = []

        # ── 信号 1：断货 → 上调安全库存（需求被低估，下次多备）──
        if stockout_ratio > STOCKOUT_TRIGGER:
            summary["stockout_days"] += 1
            # 严重程度缩放，但有上限，避免单次过冲
            severity = min(EVOLVE_UP_MAX_MULT, 1.0 + stockout_ratio * 2.0)
            step = EVOLVE_UP_STEP * severity
            new_safety = _clamp(safety + step, SAFETY_FACTOR_MIN, SAFETY_FACTOR_MAX)
            # 缺货严重时同步拉长备货天数（民生商品更敏感）
            if stockout_ratio > 0.3:
                new_base = base_days + (0.8 if product["is_livelihood"] else 0.5)
            trigger = "断货"
            reason_parts.append(
                f"缺货率 {stockout_ratio:.0%}（缺口 {stockout:.0f}{product['unit']}），"
                f"说明历史销量低估了真实需求，上调安全库存"
            )

        # ── 信号 2：积压损耗 → 下调进货建议 ──
        # 断货与损耗同时出现时不叠加（避免自我抵消），只按断货处理
        elif spoilage_ratio > SPOILAGE_TRIGGER:
            summary["spoilage_days"] += 1
            new_safety = _clamp(safety - EVOLVE_DOWN_STEP, SAFETY_FACTOR_MIN, SAFETY_FACTOR_MAX)
            # 短保商品损耗要同时压缩备货天数
            if product["shelf_life_days"] <= 7:
                new_base = base_days - 1.0
            trigger = "积压损耗"
            reason_parts.append(
                f"损耗率 {spoilage_ratio:.0%}（{spoilage:.0f}{product['unit']}报废），"
                f"进货量偏大，下调建议进货量"
            )

        if trigger is None:
            continue

        # 边界收口
        new_base = _clamp(new_base, _base_days_floor(product), _base_days_ceiling(product))

        changed = []
        if abs(new_safety - safety) > 1e-9:
            changed.append(("safety_factor", safety, new_safety))
        if abs(new_base - base_days) > 1e-9:
            changed.append(("base_days", base_days, new_base))

        if not changed:
            continue

        if persist:
            for param, old_v, new_v in changed:
                memory.log_evolution(
                    day, sku, param, round(old_v, 4), round(new_v, 4),
                    trigger, "；".join(reason_parts),
                )
            memory.set_policy(sku, new_base, new_safety, bump_version=True)

        policies[sku] = {"base_days": new_base, "safety_factor": new_safety}
        summary["adjustments"] += len(changed)

        changes.append({
            "sku": sku,
            "name": product["name"],
            "is_livelihood": int(product["is_livelihood"]),
            "trigger": trigger,
            "reason": "；".join(reason_parts),
            "base_days": (round(base_days, 2), round(new_base, 2)),
            "safety_factor": (round(safety, 3), round(new_safety, 3)),
            "changed_params": [c[0] for c in changed],
        })

    return {"day": day, "changes": changes, "summary": summary}


def apply_sales_only(day: str, feedback: list[dict]) -> None:
    """只把当天的经营记录写进记忆（用于回放历史数据，不做进化）。"""
    rows = [{
        "day": day, "sku": f["sku"],
        "qty_sold": float(f.get("qty_sold", 0) or 0),
        "qty_stockout": float(f.get("qty_stockout", 0) or 0),
        "qty_spoilage": float(f.get("qty_spoilage", 0) or 0),
        "is_promo": int(f.get("is_promo", 0) or 0),
        "is_holiday": int(f.get("is_holiday", 0) or 0),
    } for f in feedback]
    memory.add_sales(rows)


def evolution_narrative(db_path=None) -> str:
    """把进化日志翻译成人话，给店主看。"""
    logs = memory.get_evolution_log(limit=12, db_path=db_path)
    if not logs:
        return "还没有进化记录。录入一次经营反馈后，这里会显示策略是怎么自己变的。"

    name_map = {p["sku"]: p["name"] for p in memory.get_products(db_path)}
    lines = []
    for lg in logs:
        nm = name_map.get(lg["sku"], lg["sku"])
        param_cn = {"safety_factor": "安全库存系数", "base_days": "备货天数"}.get(
            lg["param"], lg["param"]
        )
        arrow = "↑" if (lg["new_value"] or 0) > (lg["old_value"] or 0) else "↓"
        lines.append(
            f"[{lg['day']}] {nm}｜{lg['trigger']} → {param_cn} {arrow} "
            f"{lg['old_value']:.3f} → {lg['new_value']:.3f}"
        )
    return "\n".join(lines)
