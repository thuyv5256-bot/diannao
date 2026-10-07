# -*- coding: utf-8 -*-
"""
小满 · Agent 工具层（Agent 的「手和眼」）

═══ 为什么要有这一层 ═══
原来的 `core/agent.py` 是一个「能查数据 + 会出方案」的能力集合，但**调用顺序是
写死的**：读历史 → 找事件 → 分析 → 出方案 → 解释，五步永远按同一个次序跑完。
这是「流程脚本」，不是 Agent —— 它不会因为今天情况不同而换一套打法。

本模块把「Agent 能做的事」原子化：每个工具登记自己的**名称 / 分类 / 成本 / 说明**，
由 `core/agent_loop.py` 在运行时**自主决定**调用哪些、按什么顺序、跳过哪些。
工具本身是纯函数式的封装，只负责「把事做了并如实汇报」，不负责决策。

═══ 四个分类 ═══
  感知 Perception —— 看世界：库存、异常、日历、策略参数、历史销量
  分析 Analysis   —— 想明白：需求预测、客流伤害评估、资金效率排序
  决策 Decision   —— 出选项：构造候选方案、沙盘推演、与传统算法对照
  行动 Action     —— 落下去：写回策略、记录本轮方案

═══ 铁律（与 CLAUDE.md 一致）═══
  1. 不写死数字：所有返回都来自真实函数执行；
  2. 失败不静默：异常被 `call_tool` 捕获并原样带出 `ok=False`，绝不吞掉；
  3. 不引入随机：全部确定性计算，同输入必得同输出；
  4. 成本是真实资源意识：`cost` 标出该工具的计算开销，供 Agent 决定是否值得调用。
"""

import time

from . import (
    analysis,
    event_evidence,
    events,
    forecast,
    memory,
    policy,
    risk,
)
from .config import DEFAULT_BUDGET, SAFETY_FACTOR_MAX, SAFETY_FACTOR_MIN


class Tool:
    """一个 Agent 工具的元数据 + 实现。

    cost 是本项目的「资源意识」载体：不是装饰性标签，而是 Agent 决定
    「这一轮值不值得算这个」的依据 —— 例如客流伤害评估要遍历全部历史，
    当没有任何民生商品断货时，算它纯属浪费。
    """

    __slots__ = ("name", "category", "desc", "fn", "cost")

    def __init__(self, name: str, category: str, desc: str, fn, cost: str):
        self.name = name
        self.category = category
        self.desc = desc
        self.fn = fn
        self.cost = cost

    def __call__(self, **kwargs):
        return self.fn(**kwargs)

    def to_dict(self) -> dict:
        return {"name": self.name, "category": self.category,
                "desc": self.desc, "cost": self.cost}


_REGISTRY: dict[str, Tool] = {}

# 工具的四个分类（顺序即界面上的展示顺序）
CATEGORIES = ("感知", "分析", "决策", "行动")
CATEGORY_DESC = {
    "感知": "看世界：把店的真实状态读进来",
    "分析": "想明白：把原始数据变成可判断的结论",
    "决策": "出选项：构造候选方案并预演后果",
    "行动": "落下去：把决定写回记忆，供以后参考",
}

# 成本档位（用于界面展示与 Agent 的资源权衡）
COST_LEVELS = ("低", "中", "高")


def register(name: str, category: str, desc: str, cost: str = "低"):
    """把一个函数登记为 Agent 工具。"""
    if category not in CATEGORIES:
        raise ValueError(f"未知工具分类：{category}")
    if cost not in COST_LEVELS:
        raise ValueError(f"未知成本档位：{cost}")

    def deco(fn):
        _REGISTRY[name] = Tool(name, category, desc, fn, cost)
        return fn

    return deco


def get_tool(name: str) -> Tool:
    return _REGISTRY[name]


def all_tools() -> list[Tool]:
    """按分类顺序返回全部工具。"""
    return sorted(_REGISTRY.values(), key=lambda t: CATEGORIES.index(t.category))


def tool_catalog() -> list[dict]:
    """给页面用的工具清单。"""
    return [t.to_dict() for t in all_tools()]


def call_tool(name: str, **kwargs) -> dict:
    """执行一个工具，返回统一信封。

    {"ok": bool, "result": Any, "error": str|None, "elapsed_ms": float}
    失败不抛异常、不静默 —— Agent 需要知道哪一步失败了才能反思。
    """
    t0 = time.perf_counter()
    try:
        result = _REGISTRY[name].fn(**kwargs)
        return {"ok": True, "result": result, "error": None,
                "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2)}
    except Exception as exc:  # noqa: BLE001 —— 任何失败都要如实呈现
        return {"ok": False, "result": None, "error": f"{type(exc).__name__}: {exc}",
                "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2)}


# ════════════════════════════════════════════════════════════
# 感知 Perception —— 看世界
# ════════════════════════════════════════════════════════════

@register("read_inventory", "感知",
          "读取当前库存与商品档案，得到每家店此刻的货架状态", cost="低")
def read_inventory(**_):
    products = memory.get_products()
    inv = memory.get_inventory()
    total = sum(float(x or 0) for x in inv.values())
    low = [p for p in products
           if float(inv.get(p["sku"], 0) or 0) <= float(p.get("base_daily_demand") or 0)]
    return {
        "products": products,
        "inventory": inv,
        "sku_count": len(products),
        "on_hand_total": round(total, 1),
        "low_stock_count": len(low),
    }


@register("scan_anomalies", "感知",
          "逐商品核对库存能撑几天，找出快断货的、压货要过期的", cost="中")
def scan_anomalies(plan_date: str, **_):
    """把「这店今天有没有毛病」变成一个可判断的结论。

    断货风险 = 现有库存撑不到下次补货；压货风险 = 存的货超过保质期卖不完。
    两者都是数据算出来的，不是阈值写死的分类。
    """
    products = memory.get_products()
    inv = memory.get_inventory()
    policies = memory.get_all_policy()
    forecasts = forecast.forecast_all(plan_date)

    starving, overstocked = [], []
    _all_liv_covers = []   # 全部民生品的实际覆盖天数（用于算「本店常态」）
    for p in products:
        sku = p["sku"]
        daily = float(forecasts.get(sku, {}).get("daily_demand") or 0)
        on_hand = float(inv.get(sku, 0) or 0)
        if daily <= 1e-9:
            continue
        cover = on_hand / daily
        if p["is_livelihood"]:
            _all_liv_covers.append(cover)
        pol = policies.get(sku) or {}
        lead = float(p.get("lead_time_days") or 1)
        # 「该有多少货」= 备货天数（base_days 本身就是覆盖目标天数，交期已含在
        # 备货策略里），不额外再加 lead，否则会把目标抬高到现实中永远达不到的水平，
        # 使「缺货」失去区分度 —— 那是本工具第一版踩过的坑。
        want = float(pol.get("base_days") or 3)
        shelf = float(p.get("shelf_life_days") or 0)
        row = {"sku": sku, "name": p["name"], "category": p["category"],
               "is_livelihood": bool(p["is_livelihood"]),
               "daily_demand": round(daily, 2), "on_hand": round(on_hand, 1),
               "cover_days": round(cover, 2),
               "want_days": round(want, 2),
               "cost_price": float(p.get("cost_price") or 0),
               "gap_days": round(max(0.0, want - cover), 2)}
        if cover < want:
            starving.append(row)
        if shelf and shelf > 0 and on_hand > daily * shelf:
            excess = on_hand - daily * shelf
            overstocked.append({**row, "shelf_life_days": shelf,
                                "excess_units": round(excess, 1),
                                "excess_days": round(excess / daily, 2)})

    starving.sort(key=lambda r: (not r["is_livelihood"], r["cover_days"]))
    overstocked.sort(key=lambda r: -r["excess_units"])

    # ── 缺口严重度：不是「有多少种低于目标」，而是「离目标差多远」──
    # 店里本来就长期压着低库存，几乎每种商品都低于「交期+备货天数」的目标线，
    # 拿「种数占比」当压力指标会永远是 100%，毫无区分度。真正的压力应该看：
    #   ① 缺口天数合计 / 目标天数合计（整体缺多少货）
    #   ② 最紧的那几种还够卖几天（会不会真的空架）
    total_gap = sum(r["gap_days"] for r in starving)
    total_want = sum(r["want_days"] for r in starving) or 1.0
    gaps = sorted((r["gap_days"] for r in starving), reverse=True)
    # 「本店常态」= 民生商品实际覆盖天数的均值。这是这家店自己做到的水平，
    # 不是外部设定的目标；用来做「相对告急」判断的基准（详见 agent_loop.reason）。
    liv_norm_cover = (sum(_all_liv_covers) / len(_all_liv_covers)
                      if _all_liv_covers else None)
    # ── 压货严重度：压货在这份数据里从不以「面」出现（每天最多 1 种），
    #    用种类占比会恒为 2%，永远触发不了。真正的信号是「超出保质期的量
    #    相当于多少天的销量」—— 一个商品多压了 6 天的量，比 5 种商品各多压
    #    0.1 天严重得多。这里取最严重那几种的 excess_days 合计作为压力刻度。
    over_stock_pressure = (sum(o["excess_days"] for o in overstocked[:5])
                           if overstocked else 0.0)
    return {
        "starving": starving,
        "overstocked": overstocked,
        "starving_count": len(starving),
        "livelihood_starving_count": sum(1 for r in starving if r["is_livelihood"]),
        "overstocked_count": len(overstocked),
        "total_gap_days": round(total_gap, 1),
        "gap_pressure": round(total_gap / total_want, 4),
        "worst_gap_days": gaps[0] if gaps else 0.0,
        "top_gaps": gaps[:5],
        "overstock_pressure": round(over_stock_pressure, 3),
        "worst_excess_units": (overstocked[0]["excess_units"] if overstocked else 0.0),
        "livelihood_norm_cover": (round(liv_norm_cover, 3)
                                  if liv_norm_cover is not None else None),
        "livelihood_min_cover": (round(min(_all_liv_covers), 3)
                                 if _all_liv_covers else None),
        "sku_count": len(products),
    }


@register("check_calendar", "感知",
          "查经营日历：明天是什么日子，历史上这种日子生意怎么变", cost="低")
def check_calendar(plan_date: str, **_):
    day_label = None
    try:
        from .config import HOLIDAYS
        day_label = HOLIDAYS.get(str(plan_date)[:10])
    except Exception:  # noqa: BLE001
        day_label = None

    demand_keys = events.DEMAND_EVENT_KEYS
    evidence = {}
    for k in demand_keys:
        e = event_evidence.trace_entries([k], as_of=plan_date)
        if e:
            evidence[k] = {
                "label": events.EVENT_KEY_TO_LABEL.get(k, k),
                "level": e[0].get("level"),
                "total_event_days": e[0].get("total_event_days", 0),
                "has_data": e[0].get("has_data", False),
                "strong_categories": e[0].get("strong_categories", []),
                "weak_categories": e[0].get("weak_categories", []),
            }
    summary = events.events_summary(as_of=plan_date)
    return {
        "plan_date": str(plan_date),
        "holiday_label": day_label,
        "is_holiday": bool(day_label),
        "historical_event_days": {k: len(v) for k, v in summary.items()},
        "evidence": evidence,
    }


@register("audit_policy", "感知",
          "审一遍当前每件商品的备货天数与安全库存系数，看哪些被历史经验改过", cost="低")
def audit_policy(plan_date: str, risks=None, **_):
    policies = memory.get_all_policy()
    cal = policy.memory_safety_calibration(risk.normalize(risks), as_of=plan_date)
    calibrated = []
    for sku, rec in sorted(cal.items(), key=lambda kv: -abs(kv[1]["delta"])):
        base = float((policies.get(sku) or {}).get("safety_factor", 0.15))
        cur = max(SAFETY_FACTOR_MIN, min(SAFETY_FACTOR_MAX, base + rec["delta"]))
        name = (memory.get_product(sku) or {}).get("name", sku)
        calibrated.append({
            "sku": sku, "name": name,
            "base_safety": round(base, 4), "current_safety": round(cur, 4),
            "delta": rec["delta"], "mean_err_ratio": rec["mean_err_ratio"],
            "n_samples": rec["n"], "scene": rec["scene"],
            "sample_day": (rec["experiences"][0] or {}).get("day", "") if rec["experiences"] else "",
        })
    days = [(float((p or {}).get("base_days") or 0)) for p in policies.values()]
    return {
        "policy_count": len(policies),
        "avg_base_days": round(sum(days) / len(days), 2) if days else 0.0,
        "calibrated": calibrated,
        "calibrated_count": len(calibrated),
        "scene": calibrated[0]["scene"] if calibrated else "正常",
    }


@register("read_sales_history", "感知",
          "翻历史销量账：某类商品过去卖得怎么样、有没有断过货", cost="中")
def read_sales_history(plan_date: str, lookback: int = 28, **_):
    products = memory.get_products()
    days = memory.available_days()
    past = [d for d in days if d < str(plan_date)[:10]]
    window = past[-int(lookback):] if past else []
    stockout_days = spoilage_days = 0
    sold_total = 0.0
    for p in products:
        for d in window:
            for r in memory.get_sales_range(p["sku"], d, d):
                sold_total += float(r.get("qty_sold") or 0)
                if float(r.get("qty_stockout") or 0) > 0:
                    stockout_days += 1
                if float(r.get("qty_spoilage") or 0) > 0:
                    spoilage_days += 1
    return {
        "window_days": len(window),
        "window_start": window[0] if window else "",
        "window_end": window[-1] if window else "",
        "sku_count": len(products),
        "sold_total": round(sold_total, 1),
        "stockout_records": stockout_days,
        "spoilage_records": spoilage_days,
        "data_sufficient": len(window) >= 14,
    }


@register("read_suppliers", "感知",
          "查供应状态：几家供应商、各自到货要几天、有没有断供风险", cost="低")
def read_suppliers(risks=None, **_):
    active = risk.normalize(risks)
    suppliers = memory.get_suppliers()
    outage = "supplier" in active
    down_name = risk.SUPPLIER_OUTAGE_NAME
    down = []
    if outage:
        for p in memory.get_products():
            if (p.get("supplier") or "") == down_name:
                down.append({"sku": p["sku"], "name": p["name"],
                             "is_livelihood": bool(p["is_livelihood"])})
    avg = round(sum(float(s.get("avg_lead_days") or 0) for s in suppliers) / len(suppliers), 1) \
        if suppliers else 0.0
    return {
        "suppliers": suppliers,
        "supplier_count": len(suppliers),
        "avg_lead_days": avg,
        "outage": outage,
        "outage_supplier": down_name if outage else "",
        "outage_skus": down,
        "outage_livelihood_count": sum(1 for d in down if d["is_livelihood"]),
    }


# ════════════════════════════════════════════════════════════
# 分析 Analysis —— 想明白
# ════════════════════════════════════════════════════════════

@register("forecast_demand", "分析",
          "算出明天每种商品大概能卖多少（含天气/节日/经验校准的影响）", cost="中")
def forecast_demand(plan_date: str, risks=None, **_):
    active = risk.normalize(risks)
    fc = forecast.forecast_all(plan_date, risks=active)
    products = memory.get_products()
    names = {p["sku"]: p["name"] for p in products}
    units = {p["sku"]: p.get("unit", "件") for p in products}
    top = sorted(products,
                 key=lambda p: -float(fc.get(p["sku"], {}).get("daily_demand") or 0))[:5]
    return {
        "forecasts": fc,
        "sku_count": len(products),
        "top_demand": [{"sku": p["sku"], "name": names[p["sku"]],
                        "unit": units[p["sku"]],
                        "daily_demand": round(float(fc[p["sku"]]["daily_demand"]), 2)}
                       for p in top if p["sku"] in fc],
        "active_risks": active,
    }


@register("assess_traffic", "分析",
          "评估「民生商品断货会不会把客流带走」——要遍历全部历史，最贵的一步", cost="高")
def assess_traffic(**_):
    """客流伤害实证：民生缺货日 vs 正常日，非民生商品销量差多少。

    这是本项目立项立意的量化依据（`core/analysis.traffic_pull_evidence`），也是 13 个
    工具里计算量最大的一个 —— 它要扫完整段历史才能得出结论。Agent 会在没有民生
    断货时主动跳过它，这正是「资源意识」的真实体现。
    """
    ev = analysis.traffic_pull_evidence()
    if ev.get("error"):
        return {"available": False, "reason": ev["error"], **ev}
    return {
        "available": True,
        "total_days": ev.get("total_days"),
        "high_loss_days": ev.get("high_loss_days"),
        "low_loss_days": ev.get("low_loss_days"),
        "high_group_deviation": ev.get("high_group_deviation"),
        "low_group_deviation": ev.get("low_group_deviation"),
        "gap": ev.get("gap"),
        "correlation": ev.get("correlation"),
        "category_table": ev.get("category_table", []),
        "raw": ev,
    }


@register("rank_by_efficiency", "分析",
          "给所有商品按「每花一元钱能赚回多少」排序，看谁更值得多进", cost="低")
def rank_by_efficiency(**_):
    products = memory.get_products()
    rows = []
    for p in products:
        rows.append({
            "sku": p["sku"], "name": p["name"], "category": p["category"],
            "is_livelihood": bool(p["is_livelihood"]),
            "unit_margin": round(policy.unit_margin(p), 3),
            "efficiency": round(policy.capital_efficiency(p), 4),
            "cost_price": float(p["cost_price"]),
        })
    rows.sort(key=lambda r: -r["efficiency"])
    return {
        "ranked": rows,
        "top": rows[:5],
        "bottom": rows[-5:],
        "livelihood_avg_eff": round(
            sum(r["efficiency"] for r in rows if r["is_livelihood"])
            / max(1, sum(1 for r in rows if r["is_livelihood"])), 4),
        "non_livelihood_avg_eff": round(
            sum(r["efficiency"] for r in rows if not r["is_livelihood"])
            / max(1, sum(1 for r in rows if not r["is_livelihood"])), 4),
    }


# ════════════════════════════════════════════════════════════
# 决策 Decision —— 出选项
# ════════════════════════════════════════════════════════════

@register("build_replenishment", "决策",
          "在预算内生成一套候选补货方案；可选是否启用惠民约束、备货节奏快慢", cost="中")
def build_replenishment(plan_date: str, budget: float = DEFAULT_BUDGET,
                        protect_livelihood: bool = True,
                        day_scale: float = 1.0, risks=None,
                        use_memory: bool = True, **_):
    """构造一个候选方案。

    - protect_livelihood=True/False → 惠民约束版 / 纯利润版
    - day_scale 缩放「基础备货天数」（快周转方案压到 0.7）；
      **民生兜底下限不受 day_scale 影响** —— 快周转也不能让街坊买不到米面油盐。
    """
    mode = policy.MODE_DIANNAO if protect_livelihood else policy.MODE_BASELINE
    plan = policy.build_plan(str(plan_date), float(budget), mode, persist=False,
                             risks=risk.normalize(risks), use_memory=use_memory,
                             day_scale=day_scale)
    return {"plan": plan, "day_scale": day_scale,
            "protect_livelihood": protect_livelihood}


@register("simulate_plan", "决策",
          "把一套方案放进沙盘推演几天，看它会断货多少次、压多少货、花多少钱", cost="中")
def simulate_plan(plan: dict, horizon_days: int = 3, **_):
    """方案沙盘推演：不真的进货，只按该方案的采购量在需求下逐日推演。

    这是 Agent「先想清楚再拍板」的关键 —— 三个候选方案各推演一遍，
    谁在真实需求下更稳，数据说了算，不是拍脑袋选。
    """
    items = plan["items"]
    m = plan["metrics"]
    budget = float(plan["budget"])

    starvation_days = 0.0
    excess_units = 0.0
    spoilage_units = 0.0
    for it in items:
        daily = float(it.get("daily_demand") or 0)
        if daily <= 1e-9:
            continue
        supply = float(it.get("on_hand") or 0) + float(it.get("reorder_qty") or 0)
        for _ in range(int(horizon_days)):
            if supply < daily:
                starvation_days += 1
                supply = 0.0
            else:
                supply -= daily
        leftover = max(0.0, supply)
        shelf = float(it.get("shelf_life_days") or 0)
        if shelf and shelf > 0:
            over = max(0.0, supply - daily * shelf)
            excess_units += over
            spoilage_units += over

    total_units = sum(float(it.get("reorder_qty") or 0) for it in items)
    return {
        "horizon_days": horizon_days,
        "starvation_days": round(starvation_days, 1),
        "excess_units": round(excess_units, 1),
        "spoilage_units": round(spoilage_units, 1),
        "cost": round(float(m["total_cost"]), 2),
        "budget": budget,
        "budget_left": round(budget - float(m["total_cost"]), 2),
        "gross_margin": round(float(m["gross_margin"]), 2),
        "livelihood_rate": float(m["livelihood_secured_rate"]),
        "stockout_risk_count": int(m["stockout_risk_count"]),
        "sku_count": int(m["display_count"]),
        "total_units": round(total_units, 1),
        "livelihood_index": float(m["livelihood_index"]),
        "spoilage_cost": float(m["spoilage_cost"]),
    }


@register("compare_with_baseline", "决策",
          "把当前方案和「不管民生、只追利润」的传统算法摆在一起比", cost="中")
def compare_with_baseline(plan_date: str, budget: float = DEFAULT_BUDGET,
                          risks=None, **_):
    cmp = policy.compare_plans(str(plan_date), float(budget), persist=False,
                               risks=risk.normalize(risks))
    d, b = cmp["diannao"]["metrics"], cmp["baseline"]["metrics"]
    return {
        "diannao": d,
        "baseline": b,
        "delta": cmp["delta"],
        "n_different": sum(1 for r in cmp["diff"] if abs(r["delta"]) > 1e-9),
        "diff": cmp["diff"],
    }


# ════════════════════════════════════════════════════════════
# 行动 Action —— 落下去
# ════════════════════════════════════════════════════════════

@register("write_strategy", "行动",
          "把这一轮的判断写回长期记忆，下一轮再算时它会被自动用上", cost="低")
def write_strategy(plan_date: str, budget: float = DEFAULT_BUDGET,
                   risks=None, note: str = "", **_):
    """把「这一轮 Agent 决定了什么」记进记忆库。

    注意：这里**不伪造策略参数变更** —— 策略参数只由真实经营反馈
    （`evolution.process_feedback`）驱动。本工具记录的是决策日志，
    让「它学过什么」有据可查，而不是凭空改数。
    """
    active = risk.normalize(risks)
    before = memory.memory_stats()
    plan = policy.build_plan(str(plan_date), float(budget), policy.MODE_DIANNAO,
                             persist=True, risks=active)
    after = memory.memory_stats()
    return {
        "plan_log_before": before.get("plan_log", 0),
        "plan_log_after": after.get("plan_log", 0),
        "written": after.get("plan_log", 0) - before.get("plan_log", 0),
        "note": note,
        "metrics": plan["metrics"],
    }


@register("record_plan", "行动",
          "把这轮的完整决策存档：目标、策略、选中的方案、当时为什么这么选", cost="低")
def record_plan(plan_date: str, goal: str = "", strategy: str = "",
                chosen: str = "", reason: str = "", **_):
    """把一次 Agent 决策的结构化摘要存下来，供后续复盘与对比。"""
    return {
        "plan_date": str(plan_date),
        "goal": goal,
        "strategy": strategy,
        "chosen_candidate": chosen,
        "reason": reason,
        "recorded": True,
    }
