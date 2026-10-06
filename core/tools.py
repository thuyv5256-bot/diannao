# -*- coding: utf-8 -*-
"""
店脑 · Agent 工具层（Tool Registry）

═══ 为什么要有这一层 ═══

传统的补货程序是「一条写死的流水线」：
    forecast() → allocate() → print()
代码怎么写的，就只能怎么跑。这不是 Agent。

Agent 的本质区别在于：它面对一个目标，**自己决定要调用哪些工具、
按什么顺序调用、调用几次，并根据返回结果决定下一步做什么**。

因此这里把门店的所有能力拆成独立的、可被 Agent 自主调用的工具：

    ┌─ 感知类（Perception）─────────────────────────────
    │   read_inventory      查当前货架剩多少
    │   scan_anomalies      扫出经营异常（断货/损耗/滞销）
    │   read_sales_history  查历史销量
    │   check_calendar      查今天是什么日子（节日/星期）
    │   audit_policy        审查策略参数是否漂移
    ├─ 分析类（Analysis）───────────────────────────────
    │   forecast_demand     预测某商品明天卖多少
    │   assess_traffic      评估民生缺货对客流的伤害
    │   rank_by_efficiency  按资金效率给商品排序
    ├─ 决策类（Decision）───────────────────────────────
    │   build_replenishment 生成一套候选补货方案
    │   simulate_plan       沙盘推演一套方案的结果
    │   compare_with_baseline 与传统算法做对照
    └──────────────────────────────────────────────────

每个工具都返回结构化结果 + 一句「说人话」的结论，
这样 Agent 的思考链才能被店主读懂 —— 这是本项目「轻量化普惠」的落点。
"""

import math
from datetime import date, datetime, timedelta

from . import analysis, forecast, memory, policy
from .config import (
    CURRENCY,
    DEFAULT_BUDGET,
    HOLIDAYS,
    LIVELIHOOD_MIN_COVER_DAYS,
    SPOILAGE_TRIGGER,
    STOCKOUT_TRIGGER,
)


# ════════════════════════════════════════════════════════════
# 工具注册表
# ════════════════════════════════════════════════════════════
class Tool:
    """一个 Agent 可调用的工具。"""

    def __init__(self, name: str, category: str, desc: str, fn,
                 cost: str = "低"):
        self.name = name
        self.category = category      # 感知 / 分析 / 决策 / 行动
        self.desc = desc
        self.fn = fn
        self.cost = cost              # 调用开销，Agent 会据此节约使用

    def __call__(self, **kwargs):
        return self.fn(**kwargs)


_REGISTRY: dict[str, Tool] = {}


def register(name: str, category: str, desc: str, cost: str = "低"):
    def deco(fn):
        _REGISTRY[name] = Tool(name, category, desc, fn, cost)
        return fn
    return deco


def get_tool(name: str) -> Tool | None:
    return _REGISTRY.get(name)


def all_tools() -> list[Tool]:
    return list(_REGISTRY.values())


# ════════════════════════════════════════════════════════════
# 感知类工具
# ════════════════════════════════════════════════════════════
@register("read_inventory", "感知",
          "读取当前货架上每样商品还剩多少，以及还能支撑几天",
          cost="低")
def read_inventory(plan_date: str = "", **_):
    products = memory.get_products()
    inv = memory.get_inventory()
    rows = []
    for p in products:
        recs = memory.get_sales(p["sku"], str(plan_date) or "9999-12-31", lookback=14)
        avg = (sum(r["qty_sold"] + r["qty_stockout"] for r in recs) / len(recs)
               if recs else 0.0)
        on_hand = inv.get(p["sku"], 0.0)
        rows.append({
            "sku": p["sku"], "name": p["name"], "unit": p["unit"],
            "is_livelihood": int(p["is_livelihood"]),
            "on_hand": round(on_hand, 1),
            "avg_daily": round(avg, 2),
            "cover_days": round(on_hand / avg, 1) if avg > 0 else 99.0,
        })
    n_low = sum(1 for r in rows if r["cover_days"] < 2.0)
    return {
        "rows": rows,
        "low_stock_count": n_low,
        "conclusion": (
            f"盘点完毕：{len(rows)} 样商品，其中 {n_low} 样快见底（不足 2 天）。"
        ),
    }


@register("scan_anomalies", "感知",
          "扫描最近经营记录，找出断货 / 损耗 / 滞销等异常，并按严重度排序",
          cost="中")
def scan_anomalies(lookback_days: int = 14, ref_date: str = "", **_):
    ref = date.fromisoformat(str(ref_date)) if ref_date else date(2026, 9, 24)
    start = (ref - timedelta(days=lookback_days - 1)).isoformat()
    products = memory.get_products()
    anomalies = []
    for p in products:
        rows = memory.get_sales_range(p["sku"], start, ref.isoformat())
        if not rows:
            continue
        so = sum(r["qty_stockout"] for r in rows)
        sp = sum(r["qty_spoilage"] for r in rows)
        sold = sum(r["qty_sold"] for r in rows)
        potential = sold + so
        so_ratio = so / potential if potential > 0 else 0.0
        sp_ratio = sp / (sold + sp) if (sold + sp) > 0 else 0.0

        if so_ratio > STOCKOUT_TRIGGER:
            anomalies.append({
                "sku": p["sku"], "name": p["name"], "kind": "断货",
                "is_livelihood": int(p["is_livelihood"]),
                "severity": round(so_ratio * p["traffic_pull"], 4),
                "detail": f"{lookback_days} 天缺货 {so:.0f}{p['unit']}，"
                          f"缺货率 {so_ratio:.0%}",
            })
        elif sp_ratio > SPOILAGE_TRIGGER:
            anomalies.append({
                "sku": p["sku"], "name": p["name"], "kind": "积压损耗",
                "is_livelihood": int(p["is_livelihood"]),
                "severity": round(sp_ratio, 4),
                "detail": f"{lookback_days} 天报损 {sp:.0f}{p['unit']}，"
                          f"损耗率 {sp_ratio:.0%}",
            })
    anomalies.sort(key=lambda x: -x["severity"])
    n_so = sum(1 for a in anomalies if a["kind"] == "断货")
    n_sp = len(anomalies) - n_so
    return {
        "anomalies": anomalies,
        "stockout_count": n_so,
        "spoilage_count": n_sp,
        "conclusion": (
            f"近 {lookback_days} 天扫出 {len(anomalies)} 项异常："
            f"断货 {n_so} 项、积压损耗 {n_sp} 项。"
            if anomalies else f"近 {lookback_days} 天经营平稳，没有明显异常。"
        ),
    }


@register("check_calendar", "感知",
          "查明决策日是什么日子：星期几、是否临近节日，以及节日对不同品类的拉动",
          cost="低")
def check_calendar(plan_date: str, **_):
    d = date.fromisoformat(str(plan_date))
    wd_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][d.weekday()]
    notes = []
    for offset in range(0, 4):
        dd = (d + timedelta(days=offset)).isoformat()
        if dd in HOLIDAYS:
            notes.append({
                "offset": offset,
                "name": HOLIDAYS[dd],
                "when": "当天" if offset == 0 else f"{offset} 天后",
            })
    hit = notes[0] if notes else None
    if hit:
        concl = (f"{d.isoformat()} 是{wd_cn}，{hit['when']}是{hit['name']}，"
                 f"饮料、零食、生鲜等品类需求会被拉起。")
    else:
        concl = f"{d.isoformat()} 是{wd_cn}，不是节日，按日常节奏备货。"
    return {
        "weekday": wd_cn, "holidays": notes, "is_special": bool(notes),
        "conclusion": concl,
    }


@register("audit_policy", "感知",
          "审查当前策略参数：哪些商品的备货天数已被进化到边界、是否出现参数漂移",
          cost="中")
def audit_policy(ref_date: str = "", **_):
    products = {p["sku"]: p for p in memory.get_products()}
    policies = memory.get_all_policy()
    logs = memory.get_evolution_log(limit=500)
    touched = {}
    for lg in logs:
        touched[lg["sku"]] = touched.get(lg["sku"], 0) + 1

    extreme = []
    for sku, pol in policies.items():
        p = products.get(sku, {})
        if not p:
            continue
        bd = float(pol["base_days"])
        sf = float(pol["safety_factor"])
        if sf >= 0.55 or sf <= 0.06 or bd >= 11.5 or bd <= 2.1:
            extreme.append({
                "sku": sku, "name": p["name"],
                "base_days": round(bd, 2), "safety_factor": round(sf, 3),
            })
    return {
        "policy_count": len(policies),
        "evolved_sku_count": len(touched),
        "extreme_params": extreme,
        "conclusion": (
            f"审查 {len(policies)} 组策略参数，其中 {len(touched)} 组在历史进化中被调整过；"
            + (f"{len(extreme)} 组已贴近安全边界。"
               if extreme else "没有参数贴边，策略状态健康。")
        ),
    }


@register("read_sales_history", "感知",
          "查某样商品最近的实际销量与历史事件，用于验证对它的印象",
          cost="低")
def read_sales_history(sku: str, lookback_days: int = 28, ref_date: str = "", **_):
    p = memory.get_product(sku)
    if not p:
        return {"error": f"没有找到商品 {sku}", "conclusion": f"商品 {sku} 不存在。"}
    ref = date.fromisoformat(str(ref_date)) if ref_date else date(2026, 9, 24)
    start = (ref - timedelta(days=lookback_days - 1)).isoformat()
    rows = memory.get_sales_range(sku, start, ref.isoformat())
    sold = sum(r["qty_sold"] for r in rows)
    so = sum(r["qty_stockout"] for r in rows)
    sp = sum(r["qty_spoilage"] for r in rows)
    potential = sold + so
    return {
        "sku": sku, "name": p["name"], "days": len(rows),
        "total_sold": round(sold, 1), "total_stockout": round(so, 1),
        "total_spoilage": round(sp, 1),
        "avg_potential": round(potential / len(rows), 2) if rows else 0.0,
        "conclusion": (
            f"{p['name']} 近 {len(rows)} 天卖 {sold:.0f}{p['unit']}，"
            f"缺货 {so:.0f}{p['unit']}，报废 {sp:.0f}{p['unit']}；"
            f"还原后的真实日均需求约 {potential / len(rows):.1f}{p['unit']}。"
            if rows else f"{p['name']} 没有历史记录。"
        ),
    }


# ════════════════════════════════════════════════════════════
# 分析类工具
# ════════════════════════════════════════════════════════════
@register("forecast_demand", "分析",
          "预测决策日全部商品的需求量，并给出推导依据（星期效应 / 节日因子）",
          cost="中")
def forecast_demand(plan_date: str, **_):
    fc = forecast.forecast_all(plan_date)
    products = {p["sku"]: p for p in memory.get_products()}
    rows = []
    for sku, v in fc.items():
        p = products.get(sku, {})
        rows.append({
            "sku": sku, "name": p.get("name", sku),
            "is_livelihood": int(p.get("is_livelihood", 0)),
            "daily_demand": v["daily_demand"],
            "weekday_factor": v["weekday_factor"],
            "holiday_factor": v["holiday_factor"],
            "holiday_note": v.get("holiday_note", ""),
            "cold_start": v.get("cold_start", False),
        })
    rows.sort(key=lambda x: -x["daily_demand"])
    notes = sorted({r["holiday_note"] for r in rows if r["holiday_note"]})
    return {
        "rows": rows, "count": len(rows), "holiday_notes": notes,
        "conclusion": (
            f"完成 {len(rows)} 样商品的需求预测。"
            + (f"识别到节日因素：{'、'.join(notes)}，相关品类已上调。"
               if notes else "无节日因素，按常规星期效应预测。")
        ),
    }


@register("assess_traffic", "分析",
          "用门店自己的历史数据，量化「民生商品缺货」对整体客流的伤害",
          cost="高")
def assess_traffic(**_):
    ev = analysis.traffic_pull_evidence()
    if "error" in ev:
        return {"error": ev["error"], "conclusion": ev["error"]}
    gap = abs(ev["gap"]) * 100
    return {
        "high_loss_days": ev["high_loss_days"],
        "low_loss_days": ev["low_loss_days"],
        "gap_pct": round(gap, 2),
        "correlation": ev["correlation"],
        "conclusion": (
            f"数据说话：民生商品缺货的日子，非民生商品少卖 {gap:.1f}%"
            f"（{ev['high_loss_days']} 个缺货日 vs {ev['low_loss_days']} 个货齐日）。"
            f"这说明民生货品是客流入口，不能为了省毛利而砍。"
        ),
    }


@register("rank_by_efficiency", "分析",
          "按「单位资金预期毛利」给商品排序 —— 这是传统纯利润算法的内部逻辑",
          cost="低")
def rank_by_efficiency(plan_date: str = "", **_):
    products = memory.get_products()
    rows = []
    for p in products:
        eff = policy.capital_efficiency(p)
        rows.append({
            "sku": p["sku"], "name": p["name"],
            "is_livelihood": int(p["is_livelihood"]),
            "capital_eff": round(eff, 4),
            "unit_margin": round(policy.unit_margin(p), 2),
        })
    rows.sort(key=lambda x: -x["capital_eff"])
    liv_ranks = [i + 1 for i, r in enumerate(rows) if r["is_livelihood"]]
    return {
        "rows": rows,
        "livelihood_best_rank": min(liv_ranks) if liv_ranks else None,
        "conclusion": (
            f"按资金效率排序后，前 {len(rows) - len(liv_ranks)} 名全是高毛利非民生商品；"
            f"最好的民生商品也只排到第 {min(liv_ranks) if liv_ranks else '—'} 名。"
            f"纯利润算法会在预算紧张时优先砍掉排在后面的民生货品 —— "
            f"这正是本 Agent 要纠正的偏差。"
        ),
    }


# ════════════════════════════════════════════════════════════
# 决策类工具
# ════════════════════════════════════════════════════════════
@register("build_replenishment", "决策",
          "在预算约束下生成一套候选补货方案；可指定是否启用惠民约束、"
          "以及备货天数的缩放比例（用于构造快周转方案）",
          cost="中")
def build_replenishment(plan_date: str, budget: float = DEFAULT_BUDGET,
                        protect_livelihood: bool = True,
                        day_scale: float = 1.0, **_):
    mode = policy.MODE_DIANNAO if protect_livelihood else policy.MODE_BASELINE
    plan = policy.build_plan(plan_date, float(budget), mode, persist=False,
                             day_scale=day_scale)
    return {
        "plan": plan,
        "total_cost": plan["metrics"]["total_cost"],
        "gross_margin": plan["metrics"]["gross_margin"],
        "livelihood_index": plan["metrics"]["livelihood_index"],
        "stockout_risk_count": plan["metrics"]["stockout_risk_count"],
        "budget_tight": plan["meta"]["budget_tight"],
        "shortfall": plan["meta"]["shortfall"],
        "conclusion": (
            f"生成一套候选方案：花 {CURRENCY}{plan['metrics']['total_cost']:.0f}，"
            f"预计毛利 {CURRENCY}{plan['metrics']['gross_margin']:.0f}，"
            f"民生保障度 {plan['metrics']['livelihood_index']:.0%}，"
            f"仍有 {plan['metrics']['stockout_risk_count']} 样可能断货。"
        ),
    }


@register("simulate_plan", "决策",
          "沙盘推演一套候选方案：假装按它进了货，看看会缺什么、压什么",
          cost="中")
def simulate_plan(plan: dict, horizon_days: int = 3, **_):
    """不写入记忆库的推演：用方案里的覆盖天数，判断未来几天的风险。"""
    if not plan:
        return {"error": "没有可推演的方案", "conclusion": "方案为空。"}
    risk_liv, risk_pro, overstock = [], [], []
    for it in plan["items"]:
        cover = it.get("final_cover_days", 0)
        if it["daily_demand"] <= 0:
            continue
        if cover < horizon_days:
            (risk_liv if it["is_livelihood"] else risk_pro).append({
                "name": it["name"], "cover": round(cover, 1),
                "gap_days": round(horizon_days - cover, 1),
            })
        # 压货风险：备货远超保质期能承受的水平
        shelf = it.get("shelf_life_days", 365)
        if shelf <= 30 and cover > shelf * 0.8:
            overstock.append({
                "name": it["name"], "cover": round(cover, 1), "shelf": shelf,
            })
    risk_liv.sort(key=lambda x: x["cover"])
    risk_pro.sort(key=lambda x: x["cover"])
    overstock.sort(key=lambda x: -x["cover"])
    total = len(risk_liv) + len(risk_pro)
    return {
        "horizon_days": horizon_days,
        "risk_livelihood": risk_liv,
        "risk_profit": risk_pro,
        "overstock": overstock,
        "risk_total": total,
        "conclusion": (
            f"推演未来 {horizon_days} 天：{total} 样商品会出现缺口"
            f"（其中民生 {len(risk_liv)} 样、高毛利 {len(risk_pro)} 样），"
            f"{len(overstock)} 样存在压货风险。"
            if total or overstock else f"推演未来 {horizon_days} 天：方案稳健，无缺口与压货风险。"
        ),
    }


@register("compare_with_baseline", "决策",
          "把当前方案与传统纯利润算法并排对照，量化惠民约束的收益与代价",
          cost="高")
def compare_with_baseline(plan_date: str, budget: float = DEFAULT_BUDGET, **_):
    cmp = policy.compare_plans(plan_date, float(budget), persist=False)
    d = cmp["delta"]
    md, mb = cmp["diannao"]["metrics"], cmp["baseline"]["metrics"]
    return {
        "cmp": cmp,
        "delta": d,
        "liv_gain": round(md["livelihood_index"] - mb["livelihood_index"], 4),
        "margin_cost": d["margin_cost_of_livelihood"],
        "conclusion": (
            f"对照结果：店脑的民生保障度比纯利润算法高 "
            f"{(md['livelihood_index'] - mb['livelihood_index']) * 100:.1f} 个百分点，"
            f"直接代价是毛利少 {CURRENCY}{d['margin_cost_of_livelihood']:.0f}。"
            f"但结合客流数据，这笔钱会在其他品类上赚回来。"
        ),
    }


@register("write_strategy", "行动",
          "把 Agent 决定采用的策略参数写回门店长期记忆库（会改变明天的建议）",
          cost="中")
def write_strategy(adjustments: list[dict], reason: str = "", **_):
    """
    adjustments: [{sku, base_days, safety_factor}, ...]
    这是 Agent 少有的**有副作用**的动作，因此被单独标为「行动」类，
    且在思考链中会显式声明「这一步会改变门店记忆」。
    """
    if not adjustments:
        return {"written": 0, "conclusion": "无需写入，本轮沿用现有策略参数。"}
    for adj in adjustments:
        memory.set_policy(adj["sku"], adj["base_days"], adj["safety_factor"],
                          bump_version=True)
    return {
        "written": len(adjustments),
        "conclusion": f"已把 {len(adjustments)} 组调整后的策略参数写回长期记忆库。"
                      + (f"理由：{reason}" if reason else ""),
    }


@register("record_plan", "行动",
          "把最终采纳的方案存入历史方案库，作为下次决策的参考依据",
          cost="低")
def record_plan(plan: dict, **_):
    if not plan:
        return {"logged": 0, "conclusion": "方案为空，未留痕。"}
    memory.log_plan(
        str(plan["date"]), plan["mode"],
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
        } for it in plan["items"]],
    )
    return {"logged": 1, "conclusion": f"方案已存入历史方案库（{plan['date']}）。"}


def tool_catalog() -> list[dict]:
    """工具清单，用于在界面上展示「这个 Agent 手里有什么工具」。"""
    return [{
        "name": t.name, "category": t.category,
        "desc": t.desc, "cost": t.cost,
    } for t in _REGISTRY.values()]
