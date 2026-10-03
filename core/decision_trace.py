# -*- coding: utf-8 -*-
"""
小满 · 决策过程追踪（「今天该进什么货」页面的 Agent 决策过程展示）

把一次补货决策拆成六个明确的「工具调用」，逐步摊给店主看：
  ① Inventory Tool   读取当前库存
  ② Event Tool       检查当前经营环境（风险事件）
  ③ Memory Tool      检索历史经营经验（策略校准）
  ④ Forecast Tool    执行需求预测
  ⑤ Supplier Tool    检查供应状态
  ⑥ R³ Optimizer     惠民约束下的补货优化

这不是写死的文案：每一步的数据都来自程序真实执行结果。六个工具各有一个
真实函数（get_inventory / detect_events / retrieve_memory / forecast_demand /
check_suppliers / optimize_replenishment），由 build_decision_trace 统一调用，
不伪造 Tool Calling；任何一个工具失败都会如实显示，绝不静默跳过。

设计原则（与 app.py 一致）：数字说人话，可追问、可解释，30 秒看懂 Agent 做了什么。
"""

from . import event_evidence, events, forecast, memory, policy, risk
from .config import SAFETY_FACTOR_MAX, SAFETY_FACTOR_MIN

# 需求侧事件（会改变销量预测）；供应商断货属供给侧，走 Supplier Tool
_DEMAND_KEYS = ("rain", "heat", "holiday")


# ── 六个真实工具函数 ──────────────────────────────────────

def get_inventory() -> dict:
    """Inventory Tool：读取当前库存，返回 {sku: on_hand}。"""
    return memory.get_inventory()


def detect_events(plan_date, active) -> dict:
    """Event Tool：检查当前经营环境，返回生效风险与各事件的历史需求统计。"""
    return {
        "active": list(active),
        "plan_date": str(plan_date),
        "stats": {k: events.sku_event_stats(k, as_of=plan_date) for k in active if k in _DEMAND_KEYS},
    }


def retrieve_memory(active, as_of=None) -> dict:
    """Memory Tool：检索与当前场景匹配的经营经验，返回策略校准结果（只用决策日之前）。"""
    return policy.memory_safety_calibration(active, as_of=as_of)


def forecast_demand(plan_date, active) -> dict:
    """Forecast Tool：执行需求预测，返回 {sku: {daily_demand, ...}}。"""
    return forecast.forecast_all(plan_date, risks=active)


def check_suppliers(active) -> dict:
    """Supplier Tool：检查供应状态，返回 {suppliers, outage}。"""
    return {
        "suppliers": memory.get_suppliers(),
        "outage": "supplier" in active,
    }


def optimize_replenishment(plan_date, budget, active) -> dict:
    """R³ Optimizer：惠民约束下的最终补货优化，返回补货方案。"""
    return policy.build_plan(str(plan_date), budget, policy.MODE_DIANNAO,
                             persist=False, risks=active)


# ── 每一步的「人话摘要」 ───────────────────────────────────

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _inventory_detail(products, inv: dict) -> str:
    total = sum(float(x or 0) for x in inv.values())
    line = f"已读取 {len(products)} 种商品库存状态"
    if total > 0:
        line += f"，当前在库合计 {total:.0f} 件"
    return line + "。"


def _event_detail(active, name_of, as_of=None) -> str:
    if not active:
        return "当前无特殊风险事件，按正常经营环境决策。"
    lines = []
    for k in active:
        label = events.EVENT_KEY_TO_LABEL.get(k, k)
        if k == "supplier":
            lines.append(f"检测到{label}风险（详见供应商检查，断供不乘预测倍率）。")
            continue
        lines.append(_event_gate_line(k, label, as_of=as_of))
    return "<br>".join(lines)


def _event_gate_line(event_key: str, label: str, as_of=None) -> str:
    """单条需求侧事件的可信度门控说明（数字来自 event_evidence 真实计算）。"""
    entries = event_evidence.trace_entries([event_key], as_of=as_of)
    e = entries[0] if entries else None
    if not e or not e["has_data"]:
        return ("✓ Event Tool：检测到" + label
                + "<br>历史有效样本不足<br>Evidence Level：Insufficient"
                + "<br>→ 本次不强制调整 Forecast，仅保留风险提示")
    head = f"✓ Event Tool：检测到{label}（历史 {e['total_event_days']} 个{label}日）"
    if e["strong_categories"]:
        cats = "、".join(e["strong_categories"])
        line = (head + f"<br>{cats} 需求方向稳定<br>Evidence Level：Strong"
                + "<br>→ Event 影响进入 Forecast")
        rest = "、".join(e["weak_categories"] + e["insufficient_categories"])
        if rest:
            line += f"<br>（{rest} 等品类证据不足/不稳，保持基础预测）"
        return line
    if e["weak_categories"]:
        return (head + "<br>需求方向不稳或效应太小<br>Evidence Level：Weak"
                + "<br>→ 本次不强制调整 Forecast，仅保留风险提示")
    return (head + "<br>历史有效样本不足<br>Evidence Level：Insufficient"
            + "<br>→ 本次不强制调整 Forecast，仅保留风险提示")


def _memory_detail(mem_cal, name_of, policies) -> str:
    if not mem_cal:
        return "当前没有匹配的有效经营经验，使用基础策略参数。"
    lines = []
    for sku, rec in sorted(mem_cal.items(), key=lambda kv: -abs(kv[1]["delta"])):
        nm = name_of.get(sku, sku)
        base = float((policies.get(sku) or {}).get("safety_factor", 0.15))
        cur = _clamp(base + rec["delta"], SAFETY_FACTOR_MIN, SAFETY_FACTOR_MAX)
        sample = rec["experiences"][0]
        day = sample.get("day", "")
        err = rec.get("mean_err_ratio", 0.0)
        direction = "预测偏低" if err >= 0 else "预测偏高"
        lines.append(
            f"检索到{nm}历史经营经验：{day}{direction}（平均残差 {err:+.0%}），"
            f"安全库存系数已由 {base:.2f} 校准至 {cur:.2f}"
        )
    return "<br>".join(lines)


def _forecast_detail(fc, products) -> str:
    names = {p["sku"]: p["name"] for p in products}
    units = {p["sku"]: p.get("unit", "件") for p in products}
    top = sorted(products,
                 key=lambda p: -float(fc.get(p["sku"], {}).get("daily_demand", 0)))[:3]
    ex = "；".join(
        f"{names[p['sku']]}预测需求：{float(fc[p['sku']]['daily_demand']):.1f}{units[p['sku']]}"
        for p in top if p["sku"] in fc
    )
    line = f"已完成 {len(products)} 种商品下一经营周期需求预测"
    if ex:
        line += f"。示例：{ex}"
    return line + "。"


def _supplier_detail(products, suppliers, outage: bool) -> str:
    if not outage:
        avg = (round(sum(s["avg_lead_days"] or 0 for s in suppliers) / len(suppliers), 1)
               if suppliers else 0.0)
        return f"当前供应商状态正常（{len(suppliers)} 家供应商，平均到货 {avg} 天）。"
    down = [p for p in products if p.get("supplier") == risk.SUPPLIER_OUTAGE_NAME]
    liv = [p for p in down if p["is_livelihood"]]
    return (f"检测到{risk.SUPPLIER_OUTAGE_NAME}断供：{len(down)} 种商品受影响"
            f"（其中民生商品 {len(liv)} 种），本次禁止向{risk.SUPPLIER_OUTAGE_NAME}生成采购。")


def _optimizer_detail(plan) -> str:
    m = plan["metrics"]
    sv = (plan.get("meta") or {}).get("solver") or {}
    res_ = sv.get("resilience") or {}
    resp = sv.get("responsibility") or {}
    n_skus = sv.get("n_skus", 0)

    if sv.get("used_milp"):
        head = f"R³ Optimizer（MILP / {sv.get('name', 'HiGHS')}）"
        return (
            f"{head}"
            f"<br>· 决策变量：{n_skus} 个 SKU 的采购整包数（非负整数）"
            f"<br>· 预算约束：¥{plan['budget']:.0f}"
            f"<br>· 收益目标（Revenue）：参与优化，预计毛利 ¥{m['gross_margin']:.0f}"
            f"<br>· 库存韧性（Resilience）：断货缺口参与优化"
            f"（相对目标库存缺口 {res_.get('shortfall_units', 0):.0f} 件）"
            f"<br>· 民生保障（Responsibility）：最低保障约束参与优化，"
            f"保障率 {m['livelihood_secured_rate']:.1%}"
            f"<br>· Solver Status：{sv.get('status', 'Optimal')}"
            f"<br>最终采购金额：¥{m['total_cost']:.0f}"
        )
    return (
        f"R³ Optimizer（{sv.get('name', '规则/贪心')}）"
        f"<br>· Solver Status：{sv.get('status', 'Fallback')}"
        f"<br>· 已回退到规则/贪心分配，保证方案仍可生成"
        f"<br>· 预算：¥{plan['budget']:.0f}"
        f"<br>· 预计收益（毛利）：¥{m['gross_margin']:.0f}"
        f"<br>· 库存韧性：可能断货商品 {m['stockout_risk_count']} 种"
        f"<br>· 民生最低保障约束已参与计算：民生最低保障达标率 {m['livelihood_secured_rate']:.1%}"
        f"<br>最终采购金额：¥{m['total_cost']:.0f}"
    )


def _final_detail(plan) -> str:
    m = plan["metrics"]
    return (
        f"建议采购：{m['display_count']} 种商品"
        f"<br>预计采购金额：¥{m['total_cost']:.0f}"
        f"<br>民生最低保障达标率：{m['livelihood_secured_rate']:.1%}"
        f"<br>可能断货商品：{m['stockout_risk_count']} 种"
    )


# ── 组装 ─────────────────────────────────────────────────

def _run(tool_name: str, fn) -> dict:
    """执行一个工具并包装成步骤；失败不静默，把失败原因如实带出。"""
    try:
        return {"tool": tool_name, "ok": True, "detail": fn(), "done": False}
    except Exception as exc:  # noqa: BLE001 —— 任何失败都要如实呈现
        return {"tool": tool_name, "ok": False, "detail": str(exc), "done": False}


def build_decision_trace(plan_date, budget: float, risks=None) -> dict:
    """按真实决策顺序调用六个工具，收集每一步的可解释数据。

    返回 {"steps": [...], "plan": {...}}：
      steps[i] = {"tool": 工具名, "ok": 是否成功, "detail": 人话摘要, "done": 是否最后一步}
      plan     = 最终补货方案（MODE_DIANNAO，persist=False），供页面直接渲染
    """
    active = risk.normalize(risks)
    products = memory.get_products()
    name_of = {p["sku"]: p["name"] for p in products}
    policies = memory.get_all_policy()

    steps: list[dict] = []
    plan = None

    # ① Inventory Tool —— 读取当前库存
    steps.append(_run("Inventory Tool", lambda: _inventory_detail(products, get_inventory())))

    # ② Event Tool —— 检查当前经营环境
    steps.append(_run("Event Tool", lambda: _event_detail(active, name_of, as_of=plan_date)))

    # ③ Memory Tool —— 检索历史经营经验（策略校准）
    def _memory_step():
        return _memory_detail(retrieve_memory(active, as_of=plan_date), name_of, policies)
    steps.append(_run("Memory Tool", _memory_step))

    # ④ Forecast Tool —— 执行需求预测
    steps.append(_run("Forecast Tool",
                      lambda: _forecast_detail(forecast_demand(plan_date, active), products)))

    # ⑤ Supplier Tool —— 检查供应状态
    def _supplier_step():
        sup = check_suppliers(active)
        return _supplier_detail(products, sup["suppliers"], sup["outage"])
    steps.append(_run("Supplier Tool", _supplier_step))

    # ⑥ R³ Optimizer —— 执行最终补货优化
    def _optimize_step():
        nonlocal plan
        plan = optimize_replenishment(plan_date, budget, active)
        return _optimizer_detail(plan)
    steps.append(_run("R³ Optimizer", _optimize_step))

    # ⑦ 最终补货方案
    if plan:
        steps.append({"tool": "最终补货方案", "ok": True,
                      "detail": _final_detail(plan), "done": True})
    else:
        steps.append({"tool": "最终补货方案", "ok": False,
                      "detail": "未能生成最终补货方案。", "done": True})

    return {"steps": steps, "plan": plan}
