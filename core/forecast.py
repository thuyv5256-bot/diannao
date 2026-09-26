# -*- coding: utf-8 -*-
"""
店脑 · 需求预测模块

设计要点（答辩重点）：
1. 断货日的历史销量是被"压扁"的 —— 顾客想买但没货，真实需求 > 记录销量。
   因此本模块用「潜在需求 = 实际销量 + 未满足的缺货量」作为学习目标，
   否则模型会一直低估需求，陷入"越缺货越不敢进货"的恶性循环。
2. 采用「指数衰减加权移动平均 + 星期效应 + 节日因子」的乘性模型。
   参数少、可解释、不会震荡 —— 这正是面向小微商户该有的技术选择，
   而不是堆一个店主看不懂、还容易过拟合的深度模型。
"""

from datetime import date, datetime, timedelta

from . import memory
from .config import DECAY_ALPHA, HOLIDAYS, LOOKBACK_DAYS

# 节日对各品类的拉动系数：(节前系数, 节日当天系数)
# 依据：节前是家庭集中采购期，饮料/零食类冲动消费弹性最大。
HOLIDAY_FACTOR_BY_CATEGORY = {
    "饮料": (1.35, 1.28),
    "零食": (1.40, 1.30),
    "生鲜": (1.25, 1.18),
    "乳品": (1.22, 1.15),
    "粮油": (1.20, 1.10),
    "调味": (1.15, 1.08),
    "日化": (1.18, 1.10),
    "酒饮": (1.30, 1.25),
    "冷饮": (1.10, 1.05),
}
DEFAULT_HOLIDAY_FACTOR = (1.15, 1.08)

# 星期效应允许的波动区间（防止小样本下把噪声当成规律）
WEEKDAY_FACTOR_MIN, WEEKDAY_FACTOR_MAX = 0.65, 1.50


def _parse(d) -> date:
    if isinstance(d, date):
        return d
    return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()


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


def weekday_profile(records: list[dict]) -> list[float]:
    """
    从历史记录里学出星期效应系数（7 维，周一→周日）。
    做法：先算全局日均潜在需求，再看各星期几相对它的平均偏离。
    均值自动归一化在 1.0 附近，因此不会改变整体需求水平。
    """
    potentials = []
    for r in records:
        potentials.append(r["qty_sold"] + r["qty_stockout"])
    if not potentials or sum(potentials) <= 0:
        return [1.0] * 7

    global_mean = sum(potentials) / len(potentials)
    if global_mean <= 0:
        return [1.0] * 7

    buckets: dict[int, list[float]] = {i: [] for i in range(7)}
    for r in records:
        wd = _parse(r["day"]).weekday()
        p = r["qty_sold"] + r["qty_stockout"]
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


def estimate_daily_demand(product: dict, plan_date, records: list[dict]) -> dict:
    """
    预测某商品在 plan_date 当天的需求量。

    返回结构包含完整推导链路，便于在界面上向店主展示"为什么是这个数"。
    """
    plan_date = _parse(plan_date)

    if not records:
        # 冷启动：用最小可用假设，避免直接摆烂
        return {
            "daily_demand": 1.0,
            "level": 1.0,
            "weekday_factor": 1.0,
            "holiday_factor": 1.0,
            "holiday_note": "",
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
        p = r["qty_sold"] + r["qty_stockout"]   # 还原潜在需求
        num += w * p
        den += w
        potential_total += p
    level = num / den if den > 0 else 0.0

    # 2) 星期效应
    profile = weekday_profile(records)
    wd_factor = profile[plan_date.weekday()]

    # 3) 节日因子
    h_factor, h_note = _holiday_factor(product["category"], plan_date)

    daily = max(0.0, level * wd_factor * h_factor)

    return {
        "daily_demand": round(daily, 2),
        "level": round(level, 2),
        "weekday_factor": round(wd_factor, 3),
        "holiday_factor": round(h_factor, 3),
        "holiday_note": h_note,
        "potential_total": round(potential_total, 1),
        "recent_days": n,
        "cold_start": False,
    }


def forecast_all(plan_date, lookback: int = LOOKBACK_DAYS) -> dict[str, dict]:
    """对全部商品做一次需求预测。"""
    products = memory.get_products()
    out = {}
    for p in products:
        records = memory.get_sales(p["sku"], str(plan_date), lookback=lookback)
        out[p["sku"]] = estimate_daily_demand(p, plan_date, records)
    return out
