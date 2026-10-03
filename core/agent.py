# -*- coding: utf-8 -*-
"""
小满 · 补货 Agent 的数据能力层

把「Agent 能查到什么数据」和「Agent 怎么据此出方案」拆成两层：
  一、查询能力（query_*）：直接对长期记忆库 / CSV 数据提问；
  二、决策流程（plan_and_explain）：读历史 → 找历史事件 → 分析事件销量影响
     → 检查商品与民生属性 → 生成补货方案 → 解释为什么。

这些能力是规则 Agent 的"工具箱"；可选 LLM 只负责把结果翻译成人话，
核心决策仍然走确定性规则（policy.py），保证可解释、可复现、不依赖密钥。
"""

import re

from . import events, evolution, memory, policy, risk
from .config import DEFAULT_BUDGET

# ════════════════════════════════════════════════════════════
# 一、数据查询能力（Agent 工具箱）
# ════════════════════════════════════════════════════════════

def query_product(sku: str) -> dict | None:
    """1. 查询商品信息（含供应商、到货时间、民生属性）。"""
    p = memory.get_product(sku)
    if not p:
        return None
    return {
        "sku": p["sku"], "name": p["name"], "category": p["category"],
        "unit": p["unit"], "cost_price": p["cost_price"], "sell_price": p["sell_price"],
        "is_livelihood": bool(p["is_livelihood"]),
        "shelf_life_days": p["shelf_life_days"],
        "supplier": p["supplier"], "lead_time_days": p["lead_time_days"],
        "base_daily_demand": p["base_daily_demand"],
    }


def query_sales(sku: str, start: str | None = None, end: str | None = None,
                limit: int = 60) -> list[dict]:
    """2. 查询某商品历史销量（默认最近 60 条）。"""
    if start and end:
        return memory.get_sales_range(sku, start, end)
    days = memory.available_days()
    if not days:
        return []
    end = end or days[-1]
    return memory.get_sales(sku, end, lookback=limit)


def query_day(day: str) -> dict:
    """3. 查询指定日期的经营数据（销量 + 天气/事件）。"""
    event = memory.get_day_event(day)
    rows = []
    for p in memory.get_products():
        recs = memory.get_sales_range(p["sku"], day, day)
        if recs:
            r = recs[0]
            rows.append({"sku": p["sku"], "name": p["name"],
                         "qty_sold": r["qty_sold"]})
    return {"day": day, "event": event, "records": rows}


def query_events() -> dict[str, list[str]]:
    """4. 查询高温 / 暴雨 / 节假日 / 供应商断货等历史事件。"""
    return events.events_summary()


def query_livelihood() -> list[dict]:
    """5. 查询民生商品。"""
    return [query_product(p["sku"]) for p in memory.get_products() if p["is_livelihood"]]


def query_supplier(sku: str) -> dict | None:
    """6. 查询某商品的供应商与到货时间。"""
    p = memory.get_product(sku)
    if not p:
        return None
    return {"sku": sku, "name": p["name"], "supplier": p["supplier"],
            "lead_time_days": p["lead_time_days"]}


def query_suppliers() -> list[dict]:
    """供应商名册（各自覆盖商品数、平均到货时间）。"""
    return memory.get_suppliers()


# ════════════════════════════════════════════════════════════
# 二、请求解析（轻量：预算 + 风险事件关键词）
# ════════════════════════════════════════════════════════════

_RISK_KEYWORDS = {
    "rain": ("暴雨", "下雨", "雨"),
    "heat": ("高温", "热", "酷暑"),
    "holiday": ("节假日", "节日", "假期"),
    "supplier": ("断货", "断供", "供应商"),
}


def parse_request(text: str) -> dict:
    """从自然语言请求里解析出预算与风险事件（供「Agent 智能补货」输入框）。"""
    budget = DEFAULT_BUDGET
    m = re.search(r"预算\s*(\d+(?:\.\d+)?)\s*元?", text or "")
    if m:
        budget = float(m.group(1))
    active = []
    for key, words in _RISK_KEYWORDS.items():
        if any(w in (text or "") for w in words):
            active.append(key)
    return {"budget": budget, "risks": risk.normalize(active)}


# ════════════════════════════════════════════════════════════
# 三、决策流程：读历史 → 找事件 → 分析 → 出方案 → 解释
# ════════════════════════════════════════════════════════════

def plan_and_explain(plan_date: str, budget: float = DEFAULT_BUDGET,
                     risks=None) -> dict:
    """
    完整跑一遍 Agent 的补货决策，并带上「为什么这么补」的解释素材。

    返回：
      plan         补货方案（policy.build_plan 结果）
      event_days   历史事件日历
      impact       数据驱动的品类乘数
      experiences  读回的同类事件历史经验
      explanation  给店主看的人话解释
    """
    active = risk.normalize(risks)
    plan = policy.build_plan(plan_date, budget, policy.MODE_DIANNAO,
                             persist=False, risks=active)

    event_days = events.events_summary(as_of=plan_date)
    impact = events.event_impact(as_of=plan_date)
    exp_rows = []
    for k in active:
        label = events.EVENT_KEY_TO_LABEL.get(k)
        if label:
            exp_rows += memory.get_experiences_for(label)

    explanation = _explain(plan_date, budget, active, event_days, impact, exp_rows, plan)

    return {
        "plan": plan,
        "event_days": event_days,
        "impact": impact,
        "experiences": exp_rows,
        "explanation": explanation,
    }


def _explain(plan_date, budget, active, event_days, impact, exp_rows, plan) -> str:
    """把 Agent 的推理链路拼成一段可读的解释。"""
    parts = []
    parts.append(f"决策日期 {plan_date}，预算 ¥{budget:.0f}。")

    if active:
        labels = [events.EVENT_KEY_TO_LABEL[k] for k in active if k in events.EVENT_KEY_TO_LABEL]
        parts.append(f"识别到风险事件：{'、'.join(labels)}。")
        for k in active:
            if k not in events.EVENT_KEY_TO_LABEL:
                continue
            label = events.EVENT_KEY_TO_LABEL[k]
            days = event_days.get(k, [])
            if days:
                span = f"{days[0]}~{days[-1]}" if len(days) > 1 else days[0]
                parts.append(f"  · 历史 {label}：共 {len(days)} 天（{span}）。")
                # 挑 2 个受影响最明显的品类说明
                top = sorted(impact.get(k, {}).items(), key=lambda x: abs(x[1] - 1),
                             reverse=True)[:2]
                if top:
                    desc = "、".join(f"{c} ×{m:.2f}" for c, m in top)
                    parts.append(f"    销量变化最明显的品类：{desc}。")
    else:
        parts.append("未勾选风险事件，按正常历史规律预测。")

    if exp_rows:
        parts.append(f"读回 {len(exp_rows)} 条同类事件的历史经验，已为相关商品加备货。")
        for ex in exp_rows[:3]:
            parts.append(f"  · {ex['lesson']}")

    m = plan["metrics"]
    parts.append(f"结论：建议进 {m['display_count']} 种商品，花费 ¥{m['total_cost']:.0f}，"
                 f"预计毛利 ¥{m['gross_margin']:.0f}，民生最低保障达标率 {m['livelihood_secured_rate']:.0%}。")
    return "\n".join(parts)
