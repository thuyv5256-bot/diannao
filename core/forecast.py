# -*- coding: utf-8 -*-
"""
小满 · 需求预测模块

设计要点（答辩重点）：
1. 断货日的历史销量是被"压扁"的 —— 顾客想买但没货，真实需求 > 记录销量。
   因此本模块用「潜在需求 = 实际销量 + 未满足的缺货量」作为学习目标，
   否则模型会一直低估需求，陷入"越缺货越不敢进货"的恶性循环。
2. 采用「指数衰减加权平均 + 趋势外推 + 星期效应 + 节日因子」的混合模型。
   参数少、可解释、不会震荡 —— 这正是面向小微商户该有的技术选择，
   而不是堆一个店主看不懂、还容易过拟合的深度模型。
3. 趋势项用最小二乘斜率做"向前一步"的外推，弥补 EMA 对持续上升/下降需求的
   滞后。
"""

from datetime import date, datetime, timedelta

from . import event_evidence, events, memory, risk
from .config import (
    DECAY_ALPHA,
    RESTORE_POTENTIAL,
    HOLIDAYS,
    LOOKBACK_DAYS,
    TREND_HORIZON,
    TREND_MIN_SAMPLES,
    TREND_MULT_MAX,
    TREND_MULT_MIN,
    USE_TREND,
)

# 节日对各品类的拉动系数：(节前系数, 节日当天系数)
HOLIDAY_FACTOR_BY_CATEGORY = {
    "饮料": (1.35, 1.28),
    "零食": (1.40, 1.30),
    "生鲜": (1.25, 1.18),
    "乳品": (1.22, 1.15),
    "粮油": (1.20, 1.10),
    "调味": (1.15, 1.08),
    "日用品": (1.18, 1.10),   # 修正：原键"日化"与数据品类名"日用品"不匹配，导致该品类掉到默认值
    "冷饮": (1.10, 1.05),
}
DEFAULT_HOLIDAY_FACTOR = (1.15, 1.08)

# 星期效应允许的波动区间（防止小样本下把噪声当成规律）
WEEKDAY_FACTOR_MIN, WEEKDAY_FACTOR_MAX = 0.65, 1.50


def _parse(d) -> date:
    if isinstance(d, date):
        return d
    return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()


def _potential(r: dict, restore_potential: bool = True) -> float:
    """单条记录的"学习目标销量"。

    restore_potential=True 时用「销量 + 缺货量」还原潜在需求（默认，也是本项目的
    核心设计）；False 时只用记录销量 —— 供消融实验验证"还原"这一步到底有没有用。
    """
    return r["qty_sold"] + (r["qty_stockout"] if restore_potential else 0.0)


def _risk_adjust(product: dict, active: list[str], as_of=None) -> tuple[float, list[str]]:
    """风险事件（需求侧三类：暴雨/高温/节假日）对销量的合成乘数与说明。

    旧版：检测到事件就直接乘一个系数（数据缺失时回退人工先验），样本不足仍会
    造成二次修正与预算错配。新版走 Event Evidence Gate（core/event_evidence.py）：
    先查历史证据、评估可信度，只有「Strong Evidence」才允许事件调整预测；
    Weak / Insufficient 一律保持基础预测、仅记风险提示。供应商断供属供给侧事件，
    不在此处理（由 policy 停采断供供应商）。

    as_of：决策截止日；事件证据只统计 as_of 之前的历史样本（防时间穿越）。
    """
    mult = 1.0
    notes = []
    for k in ("rain", "heat", "holiday"):
        if k not in active:
            continue
        label = events.EVENT_KEY_TO_LABEL[k]
        rec = event_evidence.evaluate_product(k, product, as_of=as_of)
        if rec["apply_to_forecast"]:
            f = max(events.MULT_MIN, min(events.MULT_MAX, rec["uplift"]))
            mult *= f
            scope = "商品" if rec["scope"] == "sku" else "品类"
            notes.append(
                f"{label} ×{f:.2f}（Strong证据：{rec['sample_count']}个{label}日，{scope}需求稳定）")
        elif rec["evidence_level"] == event_evidence.LEVEL_WEAK:
            notes.append(f"{label}（Weak证据，保持基础预测）")
        else:
            notes.append(f"{label}（Insufficient证据，不调整预测，仅提示）")
    return round(mult, 4), notes


def _holiday_factor(category: str, target: date) -> tuple[float, str]:
    """返回目标日期的节日系数与说明文字。"""
    day_str = target.strftime("%Y-%m-%d")
    pre = (target + timedelta(days=1)).strftime("%Y-%m-%d")
    pre2 = (target + timedelta(days=2)).strftime("%Y-%m-%d")
    mid = (target + timedelta(days=3)).strftime("%Y-%m-%d")

    pre_f, day_f = HOLIDAY_FACTOR_BY_CATEGORY.get(category, DEFAULT_HOLIDAY_FACTOR)

    if day_str in HOLIDAYS:
        return day_f, HOLIDAYS[day_str]
    if pre in HOLIDAYS:
        return pre_f, f"{HOLIDAYS[pre]}前一天"
    if pre2 in HOLIDAYS:
        # 节前 2 天小幅提前备货
        return 1.0 + (pre_f - 1.0) * 0.6, f"{HOLIDAYS[pre2]}前备货期"
    if mid in HOLIDAYS:
        return 1.0 + (day_f - 1.0) * 0.5, f"{HOLIDAYS[mid]}前预热"
    return 1.0, ""


def weekday_profile(records: list[dict], restore_potential: bool = True) -> list[float]:
    """
    从历史记录里学出星期效应系数（7 维，周一→周日）。
    做法：先算全局日均潜在需求，再看各星期几相对它的平均偏离。
    均值自动归一化在 1.0 附近，因此不会改变整体需求水平。
    """
    potentials = [_potential(r, restore_potential) for r in records]
    if not potentials or sum(potentials) <= 0:
        return [1.0] * 7

    global_mean = sum(potentials) / len(potentials)
    if global_mean <= 0:
        return [1.0] * 7

    buckets: dict[int, list[float]] = {i: [] for i in range(7)}
    for r in records:
        wd = _parse(r["day"]).weekday()
        p = _potential(r, restore_potential)
        buckets[wd].append(p / global_mean)

    profile = []
    for i in range(7):
        if buckets[i]:
            v = sum(buckets[i]) / len(buckets[i])
            # 收缩到 1.0，样本少时更保守
            conf = min(1.0, len(buckets[i]) / 4.0)
            v = 1.0 + (v - 1.0) * conf
        else:
            v = 1.0
        profile.append(max(WEEKDAY_FACTOR_MIN, min(WEEKDAY_FACTOR_MAX, v)))
    return profile


def _trend(records: list[dict], restore_potential: bool = True) -> tuple[float, float]:
    """最小二乘线性斜率 → 趋势调整倍数，返回 (slope, multiplier)。

    思想：EMA 反映"近期平均水平"，但对持续上升/下降的需求有滞后。
    用回归斜率把水平向未来外推 TREND_HORIZON 天，可提前跟上趋势。
    样本少时向 1.0 收缩，避免把噪声当趋势。
    """
    n = len(records)
    if not USE_TREND or n < TREND_MIN_SAMPLES:
        return 0.0, 1.0
    ys = [_potential(r, restore_potential) for r in records]
    mean = sum(ys) / n
    if mean <= 0:
        return 0.0, 1.0
    mx = (n - 1) / 2.0
    num = sum((i - mx) * (y - mean) for i, y in enumerate(ys))
    den = sum((i - mx) ** 2 for i in range(n))
    slope = num / den if den > 0 else 0.0
    rel = slope / mean                       # 每日相对增速
    conf = min(1.0, (n - TREND_MIN_SAMPLES) / 12.0)   # 样本越多越可信
    mult = 1.0 + rel * conf * TREND_HORIZON
    mult = max(TREND_MULT_MIN, min(TREND_MULT_MAX, mult))
    return slope, mult


def estimate_daily_demand(product: dict, plan_date, records: list[dict],
                          restore_potential: bool = RESTORE_POTENTIAL, risks=None) -> dict:
    """
    预测某商品在 plan_date 当天的需求量。

    risks：生效的风险事件键列表（见 core/risk.py）。勾选的暴雨/高温/节假日
    会作为前瞻性信息乘进预测；供应商断货不在此处处理（由 policy 停止采购断供商品）。

    返回结构包含完整推导链路，便于在界面上向店主展示"为什么是这个数"。
    """
    plan_date = _parse(plan_date)
    active = risk.normalize(risks)
    risk_mult, risk_notes = _risk_adjust(product, active, as_of=plan_date)

    if not records:
        # 冷启动：用商品配置里的基础日均需求兜底（CSV 提供），缺失时再退回 1
        base = float(product.get("base_daily_demand") or 1.0)
        return {
            "daily_demand": round(max(0.0, base * risk_mult), 2),
            "level": 1.0,
            "weekday_factor": 1.0,
            "holiday_factor": 1.0,
            "holiday_note": "",
            "trend_multiplier": 1.0,
            "trend_slope": 0.0,
            "risk_factor": risk_mult,
            "risk_note": "；".join(risk_notes),
            "potential_total": 0.0,
            "recent_days": 0,
            "cold_start": True,
        }

    # 1) 指数衰减加权平均（越近的日期权重越高）
    num = den = 0.0
    potential_total = 0.0
    n = len(records)
    for idx, r in enumerate(records):
        age = n - 1 - idx  # 0 表示最新
        w = (1 - DECAY_ALPHA) ** age
        p = _potential(r, restore_potential)
        num += w * p
        den += w
        potential_total += p
    level = num / den if den > 0 else 0.0

    # 2) 星期效应
    profile = weekday_profile(records, restore_potential)
    wd_factor = profile[plan_date.weekday()]

    # 3) 节日因子
    # 当「节假日」风险已激活时，节日效应改由风险路径（逐商品历史系数）计入，
    # 这里不再叠加日历节日因子 —— 否则同一节日会被乘两次。
    if "holiday" in active:
        h_factor, h_note = 1.0, ""
    else:
        h_factor, h_note = _holiday_factor(product["category"], plan_date)

    # 4) 趋势外推
    slope, trend_mult = _trend(records, restore_potential)

    base = max(0.0, level * trend_mult)
    daily = max(0.0, base * wd_factor * h_factor)
    daily = max(0.0, daily * risk_mult)

    return {
        "daily_demand": round(daily, 2),
        "level": round(level, 2),
        "weekday_factor": round(wd_factor, 3),
        "holiday_factor": round(h_factor, 3),
        "holiday_note": h_note,
        "trend_multiplier": round(trend_mult, 3),
        "trend_slope": round(slope, 3),
        "risk_factor": risk_mult,
        "risk_note": "；".join(risk_notes),
        "potential_total": round(potential_total, 1),
        "recent_days": n,
        "cold_start": False,
    }


def forecast_all(plan_date, lookback: int = LOOKBACK_DAYS,
                 restore_potential: bool = RESTORE_POTENTIAL, risks=None) -> dict[str, dict]:
    """对全部商品做一次需求预测。"""
    products = memory.get_products()
    out = {}
    for p in products:
        records = memory.get_sales(p["sku"], str(plan_date), lookback=lookback)
        out[p["sku"]] = estimate_daily_demand(p, plan_date, records, restore_potential,
                                              risks=risks)
    return out
