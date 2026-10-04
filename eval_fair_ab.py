# -*- coding: utf-8 -*-
"""
小满 · 公平 A/B 对照实验框架（比赛级/ 可复现）
================================================================================
【设计原则】
  1. **不追求漂亮数字**：本框架只保证公平与可复现，不为任何算法调参。
  2. **不改生产算法**：R³ / Forecast / Memory / 民生权重 / DeepSeek /
     预算全部保持现状，本文件只做「实验编排」。
  3. **同一环境**：所有策略共用同一套批次库存 / FEFO / 到货 / 损耗 / 事件逻辑
     （复用 core/simulator.py 的环境函数，不修改它）。
  4. **统一潜在需求**：potential_demand 来自 180 天仿真 CSV 的 sales 字段，
     被明确解释为「仿真生成的潜在消费需求」。**不使用 CSV 里预生成的 stockout**
     （上一轮审计已确认它恒为 0，是数据缺失）。
  5. **缺货由各算法自己的库存决定**：
         sold     = FEFO_sell(batches, potential_demand)
         stockout = max(0, potential_demand − sold)
     决策层永远看不到 potential_demand（上帝视角）。

【与传统 baseline 的区别】
  上一轮审计发现 policy.MODE_BASELINE 只是「关掉 R³ + 关掉民生」的贪心，
  仍然共享 Forecast / 事件感知 / Memory 关闭等能力，评委无法理解「传统」是什么。
  本框架的 traditional 是**一条能被一句话讲清楚的传统补货规则**：
        目标库存 = 最近 N 天平均销量 × 固定覆盖天数
        下单量   = max(0, 目标库存 − 现有库存 − 在途)
        预算内按「毛利率」从高到低依次满足（这是传统门店的真实做法）
  它**不使用**：R³ / 民生优先 / Memory / DeepSeek / 未来需求 / 事件感知。

【口径声明（防止夸大）】
  本框架的「经营毛利」= Σ(实销 × (售价 − 成本)) − Σ(报损 × 成本)
  它**不是净利润**，不含资金占用成本、房租、人工、损耗以外的跌价。
  因此本框架**同时强制报告**：
        average_inventory_value  （平均库存资金占用）
        ending_inventory_value   （期末库存金额）
  防止「靠大量囤货刷高服务水平」的伪优势。

【sanity checks（不通过则实验判定 FAIL，不产出宣传结论）】
  SC1 永不补货   → 缺货率应极高（接近 100%）
  SC2 无限预算   → 服务水平应接近理论上限（缺货率≈0）
  SC3 同策略跑两次 → 结果必须逐位一致（可复现性）
"""
from __future__ import annotations

import io
import json
import math
import os
import random
import sys
import tempfile
import time
from collections import defaultdict
from datetime import date, timedelta

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core import dataset, policy, memory, metrics, events, event_evidence  # noqa: E402
from core import simulator as sim  # noqa: E402

# ══════════════════════════════════════════════════════════════
# 实验配置（所有策略共享，任何人都能看懂并复现）
# ══════════════════════════════════════════════════════════════
DAYS = None              # None = 用CSV 全部 180 天
BUDGET = sim.DEFAULT_SIM_BUDGET   # 每日采购预算（元），与现 180 天实验一致
SEED = sim.DEFAULT_SEED
INIT_INVENTORY_DAYS = sim.INIT_INVENTORY_DAYS

# 传统补货规则参数（刻意朴素，便于评委理解）
TRAD_N_DAYS = 7# 目标库存 = 最近 7 天平均销量 × 覆盖天数
TRAD_COVER_DAYS = 3.0   # 覆盖 3 天


# ══════════════════════════════════════════════════════════════
# 一、传统补货基线（可解释规则，不调用 policy.build_plan）
# ══════════════════════════════════════════════════════════════

class TraditionalPlanner:
    """传统补货规则：目标库存法 + 毛利优先分配预算。

    这是真实小店最常见的做法，规则简单到可以在答辩现场口述：
        1. 目标库存 = 最近 N 天平均销量 × 固定覆盖天数
        2. 需要补的量 = 目标库存 − 现有库存 − 在途
        3. 预算有限时，按毛利率从高到低依次满足

    明确不使用：R³ / 民生优先 / 经营记忆 / 大模型 / 未来需求 / 事件感知。
    """

    key = "traditional"
    label = "传统补货（目标库存法）"
    desc = ("目标库存 = 最近7天平均销量 × 3 天；预算内按毛利率从高到低补。"
            "不使用 R³ / 民生优先 / Memory / 大模型 / 事件感知。")
    # 传统补货不使用经营记忆：既不读也不写，避免污染隔离库
    uses_memory = False

    def __init__(self, n_days: int = TRAD_N_DAYS, cover_days: float = TRAD_COVER_DAYS):
        self.n_days = n_days
        self.cover_days = cover_days

    def plan(self, day: str, products, prod_map, batches, in_transit, budget: float) -> dict:
        """返回 {sku: reorder_qty}。只读今天以前的历史销量。"""
        # 最近 N 天实际销量（严格不含今天，避免未来信息泄漏）
        hist = {}
        for p in products:
            rows = memory.get_sales_range(p["sku"], _add_days(day, -self.n_days), _add_days(day, -1))
            sold = sum(float(r["qty_sold"] or 0.0) for r in rows)
            hist[p["sku"]] = sold / max(1, len(rows)) if rows else float(p["base_daily_demand"])

        need = {}
        for p in products:
            sku = p["sku"]
            target = hist[sku] * self.cover_days
            on_hand = sim._total_qty(batches[sku])
            # 在途：只有评估窗口内能到的才算可用（与主链路口径一致）
            arriving = sum(q for (d, q) in in_transit[sku]
                           if 0 <= (date.fromisoformat(d) - date.fromisoformat(day)).days <= p["lead_time_days"])
            gap = max(0.0, target - on_hand - arriving)
            if gap > 1e-9:
                need[sku] = gap

        # 预算内按毛利率从高到低补（传统门店的真实取舍：先补赚钱的）
        order = sorted(need, key=lambda s: (-(prod_map[s]["sell_price"] - prod_map[s]["cost_price"]), s))
        left = budget
        out = {}
        for sku in order:
            p = prod_map[sku]
            unit = float(p["cost_price"])
            qty = min(need[sku], left / unit) if unit > 1e-9 else need[sku]
            qty = max(0.0, qty)
            out[sku] = qty
            left -= qty * unit
        for sku in need:
            out.setdefault(sku, 0.0)
        return out


class PolicyPlanner:
    """把 policy.build_plan 包成与 TraditionalPlanner 相同的接口。

    mode / use_memory / use_events / protect_livelihood 由外部指定，
    用于主对比与消融，不做任何额外加工。
    """

    uses_memory = True          # 生产策略会读写经营记忆

    def __init__(self, key, label, desc, mode, use_memory, use_events,
                 protect_livelihood, restore_potential=True):
        self.key, self.label, self.desc = key, label, desc
        self.use_memory = use_memory
        self.mode = mode
        self.use_memory = use_memory
        self.use_events = use_events
        self.protect_livelihood = protect_livelihood
        self.restore_potential = restore_potential

    def plan(self, day, products, prod_map, batches, in_transit, budget):
        memory.set_inventory_bulk([(p["sku"], sim._total_qty(batches[p["sku"]]))
                                   for p in products])
        events.clear_impact_cache()
        event_evidence.clear_cache()
        risks = None
        if self.use_events:
            risks = sim._day_risk_keys(day, _EVENT_BY_DAY)
        on_hand_batches = {
            sku: [((date.fromisoformat(b["expiry"]) - date.fromisoformat(day)).days, b["qty"])
                  for b in batches[sku] if b["qty"] > 1e-9]
            for sku in batches
        }
        in_transit_map = {sku: list(lst) for sku, lst in in_transit.items()}
        result = policy.build_plan(
            day, budget, self.mode, persist=False,
            restore_potential=self.restore_potential,
            risks=risks if risks is not None else [],
            use_memory=self.use_memory,
            protect_livelihood=self.protect_livelihood,
            in_transit_map=in_transit_map, on_hand_batches=on_hand_batches,
            spoilage_control=True,
        )
        items = result["items"]
        sim._enforce_supplier_outage(day, _EVENT_BY_DAY, items)
        return ({it["sku"]: float(it["reorder_qty"]) for it in items},
                result["metrics"])


class NeverRestockPlanner:
    """sanity check：永不补货。"""

    key, label = "never_restock", "【sanity check】永不补货"
    desc = "永远不下单。用于验证评价器能识别躺平策略。"
    uses_memory = False

    def plan(self, day, products, prod_map, batches, in_transit, budget):
        return {p["sku"]: 0.0 for p in products}


class UnlimitedBudgetPlanner:
    """sanity check：无限预算/无限库存上界。

    每天把货架填到能覆盖未来全部需求（用真实历史均值近似），
    用来验证评价器的理论上限。
    """

    key, label = "unlimited", "【sanity check】无限预算"
    desc = "预算无限、想要多少进多少。用于验证理论服务水平上界。"
    uses_memory = False

    def plan(self, day, products, prod_map, batches, in_transit, budget):
        out = {}
        for p in products:
            sku = p["sku"]
            rows = memory.get_sales_range(sku, _add_days(day, -7), _add_days(day, -1))
            avg = (sum(float(r["qty_sold"] or 0) for r in rows) / max(1, len(rows))
                   if rows else float(p["base_daily_demand"]))
            on_hand = sim._total_qty(batches[sku])
            target = avg * 7.0
            out[sku] = max(0.0, target - on_hand)
        return out


def _add_days(day: str, n: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=n)).isoformat()


# ══════════════════════════════════════════════════════════════
# 二、统一模拟环境（所有策略共用，逻辑与 core/simulator.py 一致）
# ══════════════════════════════════════════════════════════════
_EVENT_BY_DAY = {}


def run_strategy(planner, gt: dict, budget: float, seed: int,
                 days: list[str] | None = None,
                 use_memory_writes: bool = True) -> dict:
    """在完全相同的环境里经营一个策略，返回统一口径的指标。

    环境（对所有策略逐位相同）：
      · 初始库存    = base_daily_demand × INIT_INVENTORY_DAYS（第一天到货）
      · 批次与保质期 = _make_batch（expiry = arrival + shelf_life_days）
      · 销售        = FEFO（最早到期先卖）
      · 缺货        = max(0, potential_demand − sold)，由自己的库存决定
      · 到货        = 下单后按 lead_time_days 到达
      · 断供        = 供应商D 断供日强制拦截
      · 损耗        = 到期批次整体报损（售前）
      · 潜在需求    = CSV sales 字段（上帝视角，决策层不可见）
    """
    random.seed(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except Exception:
        pass

    products = gt["products"]
    prod_map = gt["prod_map"]
    demand_map = gt["demand_map"]
    event_by_day = gt["event_by_day"]
    day_list = days or gt["day_list"]

    db_path = sim._fresh_db()
    sim._setup_isolated_db(db_path, products, gt["day_events_rows"])
    old = memory.DB_PATH
    memory.DB_PATH = str(db_path)
    events.clear_impact_cache()
    event_evidence.clear_cache()

    acc = defaultdict(float)
    inv_values = []
    daily_rows = []
    memory_experiences = 0

    try:
        first = day_list[0]
        batches = {p["sku"]: [sim._make_batch(
            first, math.ceil(p["base_daily_demand"] * INIT_INVENTORY_DAYS),
            p["shelf_life_days"])] for p in products}
        in_transit = {p["sku"]: [] for p in products}
        liv_rates = []

        for day in day_list:
            # ① 到货
            for p in products:
                sku = p["sku"]
                arrived, remain = 0.0, []
                for (d, q) in in_transit[sku]:
                    if d == day:
                        arrived += q
                    else:
                        remain.append((d, q))
                in_transit[sku] = remain
                if arrived > 1e-9:
                    batches[sku].append(sim._make_batch(day, arrived, p["shelf_life_days"]))

            # ② 决策
            got = planner.plan(day, products, prod_map, batches, in_transit, budget)
            if isinstance(got, tuple):
                reorder, plan_metrics = got
            else:
                reorder, plan_metrics = got, None

            # ③ 下单进在途
            for p in products:
                q = float(reorder.get(p["sku"], 0.0))
                if q > 1e-9:
                    lead = max(1, int(p["lead_time_days"] or 1))
                    in_transit[p["sku"]].append((_add_days(day, lead), q))
                    acc["purchase_amount"] += q * float(p["cost_price"])
                    acc["budget_spent"] += q * float(p["cost_price"])

            if plan_metrics is not None:
                liv_rates.append(float(plan_metrics.get("livelihood_secured_rate", 0.0)))

            # ④ 结算：需求 → 销售 → 缺货 → 损耗 → 库存
            day_sold = day_demand = day_stockout = day_spoil = 0.0
            fb = []
            for p in products:
                sku = p["sku"]
                demand = demand_map.get((day, sku), 0.0)   # 潜在需求（上帝视角）
                spoil = sim._expire_batches(batches[sku], day)
                sold = sim._fefo_sell(batches[sku], demand)
                stockout = max(0.0, demand - sold)
                closing = sim._total_qty(batches[sku])

                acc["demand"] += demand
                acc["sold"] += sold
                acc["stockout"] += stockout
                acc["spoiled"] += spoil
                acc["revenue"] += sold * float(p["sell_price"])
                acc["gross"] += (sold * (float(p["sell_price"]) - float(p["cost_price"]))
                                 - spoil * float(p["cost_price"]))
                acc["spoilage_cost"] += spoil * float(p["cost_price"])
                acc["ending_inv_value"] = closing * float(p["cost_price"])  # 末条即期末
                inv_values.append(closing * float(p["cost_price"]))
                if p["is_livelihood"]:
                    acc["liv_demand"] += demand
                    acc["liv_stockout"] += stockout
                    acc["liv_sold"] += sold
                day_sold += sold
                day_demand += demand
                day_stockout += stockout
                day_spoil += spoil
                # 当天商品级结算结果，供 Memory 学习使用（与策略无关）
                fb.append({"sku": sku, "qty_sold": sold,
                           "qty_stockout": stockout, "qty_spoilage": spoil})

            daily_rows.append({"day": day, "sold": day_sold, "demand": day_demand,
                               "stockout": day_stockout, "spoil": day_spoil})

            # ⑤ 记忆学习：与生产系统完全相同的入口（sanity check 不需要）
            # 只有「声明会用 Memory 的策略」才写经营记忆。
            # 传统补货明确不用 Memory（uses_memory=False），sanity check 同理——
            # 否则会给隔离库写入上千条无用经验，既污染又拖慢速度。
            if use_memory_writes and getattr(planner, "uses_memory", False):
                from core import evolution
                # 与 simulator 同理：此处 persist 保持默认 True 是**必要的**——
                # 反馈要写进隔离库供次日预测使用。安全性由本函数开头的
                # memory.DB_PATH 切换到 _fresh_db() 临时库 + finally 里的删除保证，
                # 绝不会落到正式 store_memory.db。
                evolution.process_feedback(day, fb)
        memory_experiences = len(memory.get_experiences(limit=99999))
    finally:
        memory.DB_PATH = old
        for suffix in ("", "-wal", "-shm"):
            p = str(db_path) + suffix
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

    n = len(day_list) or 1
    demand = acc["demand"]
    liv_demand = acc["liv_demand"]
    avg_inv = (sum(inv_values) / len(inv_values)) if inv_values else 0.0

    return {
        "key": planner.key,
        "label": planner.label,
        "desc": getattr(planner, "desc", ""),
        "days": n,
        # ── 收入与利润 ──
        "revenue": round(acc["revenue"], 2),
        "gross_profit": round(acc["gross"], 2),          # 经营毛利（非净利润）
        "purchase_amount": round(acc["purchase_amount"], 2),
        "budget_spent": round(acc["budget_spent"], 2),
        "budget_used_rate": round(acc["budget_spent"] / (budget * n), 6) if budget > 0 else 0.0,
        # ── 缺货 ──
        "unmet_demand": round(acc["stockout"], 1),
        "stockout_rate": round(acc["stockout"] / demand, 6) if demand > 0 else 0.0,
        # ── 民生 ──
        "liv_unmet_demand": round(acc["liv_stockout"], 1),
        "liv_stockout_rate": round(acc["liv_stockout"] / liv_demand, 6) if liv_demand > 0 else 0.0,
        "liv_fill_rate": round(acc["liv_sold"] / liv_demand, 6) if liv_demand > 0 else 0.0,
        "liv_secured_rate": round(sum(liv_rates) / len(liv_rates), 6) if liv_rates else 0.0,
        # ── 损耗 ──
        "spoilage_qty": round(acc["spoiled"], 1),
        "spoilage_cost": round(acc["spoilage_cost"], 2),
        "spoilage_rate": round(acc["spoiled"] / (acc["sold"] + acc["spoiled"]), 6)
        if (acc["sold"] + acc["spoiled"]) > 0 else 0.0,
        # ── 库存（防囤货伪优势）──
        "average_inventory_value": round(avg_inv, 2),
        "ending_inventory_value": round(acc["ending_inv_value"], 2),
        "inventory_turnover": round(metrics.inventory_turnover(
            acc["sold"] * 0 + acc["gross"], avg_inv), 4) if avg_inv > 0 else 0.0,
        "sold_qty": round(acc["sold"], 1),
        "demand_qty": round(demand, 1),
        "memory_experiences": memory_experiences,
    }


# ══════════════════════════════════════════════════════════════
# 三、策略清单
# ══════════════════════════════════════════════════════════════

def build_strategies() -> list:
    trad = TraditionalPlanner()
    return [
        # ── 主实验：只放两条真正可比的策略 ──
        trad,
        PolicyPlanner("diannao", "小满（完整）",
                      "Forecast + 风险事件 + 民生约束 + R³（生产系统原样）",
                      policy.MODE_DIANNAO, True, True, True),
        # ── 消融实验（不进主结论）──
        PolicyPlanner("forecast_only", "Forecast only（无R³ / 无民生 / 无事件）",
                      "仅需求预测 + 贪心分配，不含 R³ / 民生 / 事件",
                      policy.MODE_BASELINE, False, False, False,
                      restore_potential=False),
        PolicyPlanner("forecast_r3", "Forecast + R³（无民生 / 无事件）",
                      "含 R³ 多目标求解，不含民生兜底与事件感知",
                      policy.MODE_DIANNAO, False, False, False),
        PolicyPlanner("forecast_r3_liv", "Forecast + R³ + 民生约束（无事件 / 无Memory）",
                      "含 R³ 与民生兜底，不含事件感知与经营记忆",
                      policy.MODE_DIANNAO, False, True, True),
        PolicyPlanner("diannao_no_memory", "小满 − Memory",
                      "去掉经营记忆，其余同完整小满",
                      policy.MODE_DIANNAO, False, True, True),
        # ── sanity check ──
        NeverRestockPlanner(),
        UnlimitedBudgetPlanner(),
    ]


# ══════════════════════════════════════════════════════════════
# 四、报告输出
# ══════════════════════════════════════════════════════════════

METRICS = [
    ("revenue", "总销售收入", "元", "high"),
    ("gross_profit", "经营毛利（非净利润）", "元", "high"),
    ("purchase_amount", "总采购金额", "元", "low"),
    ("unmet_demand", "未满足需求量", "件", "low"),
    ("stockout_rate", "总缺货率", "比例", "low"),
    ("liv_unmet_demand", "民生未满足需求量", "件", "low"),
    ("liv_stockout_rate", "民生商品缺货率", "比例", "low"),
    ("liv_secured_rate", "民生保障率（方案口径）", "比例", "high"),
    ("spoilage_qty", "损耗数量", "件", "low"),
    ("spoilage_cost", "损耗成本", "元", "low"),
    ("average_inventory_value", "平均库存金额（资金占用）", "元", "low"),
    ("ending_inventory_value", "期末库存金额", "元", "low"),
    ("budget_used_rate", "预算使用率", "比例", "info"),
]


def print_main_table(res: dict, a_key: str, b_key: str) -> None:
    """a_key = 基准（传统），b_key = 对照（小满）。delta = B − A = 小满 − 传统。"""
    A, B = res[a_key], res[b_key]
    print()
    print("=" * 112)
    print("主实验：%s（基准）  vs  %s      （%d 天 · 每日预算 ¥%.0f · seed=%d）"
          % (A["label"], B["label"], A["days"], BUDGET, SEED))
    print("  变化方向 = 小满 − 传统；正数表示小满该数值更大，负数表示更小")
    print("=" * 112)
    print("  %-28s %14s %14s %13s %11s %s"
          % ("指标", A["label"][:12], B["label"][:12], "变化(小满-传统)", "相对变化", "谁更优"))
    print("  " + "─" * 108)
    for key, name, unit, better in METRICS:
        a, b = A.get(key), B.get(key)
        if a is None or b is None:
            continue
        delta = b - a
        if abs(a) > 1e-9:
            rel = "%+.2f%%" % (delta / abs(a) * 100)
        else:
            rel = "—"
        if better == "info":
            win = "—"
        elif abs(delta) < 1e-9:
            win = "持平"
        elif better == "high":
            win = "小满" if delta > 0 else "传统"
        else:
            win = "小满" if delta < 0 else "传统"
        print("  %-28s %14.2f %14.2f %+13.2f %11s %s"
              % (name, a, b, delta, rel, win))
    print("  " + "─" * 108)
    print("  说明：「经营毛利」= Σ(实销×(售价−成本)) − Σ(报损×成本)。")
    print("        它**不是净利润**，不含资金占用/房租/人工，因此必须同时看")
    print("        「平均库存金额」与「期末库存金额」—— 囤货能刷高服务水平但吃现金。")
    print("        「民生保障率」是方案口径（小满有/传统无），不作为算法优劣依据；")
    print("        民生缺货率是真实结算口径，才是可比的。")


def print_condition_checklist(gt: dict) -> None:
    """逐项输出实验条件核对表（用户要求全部 SAME 才算公平）。"""
    print()
    print("=" * 108)
    print("实验条件逐项核对表（A/B 必须全部 SAME）")
    print("=" * 108)
    rows = [
        ("时间窗口", "SAME", "%s ~ %s（%d 天）" % (gt["day_list"][0], gt["day_list"][-1], len(gt["day_list"]))),
        ("商品数", "SAME", "%d 个 SKU" % len(gt["products"])),
        ("潜在需求", "SAME", "同一份 demand_map（CSV sales，上帝视角，决策层不可见）"),
        ("初始库存", "SAME", "base_daily_demand × %s 天，作为首日��货批次" % INIT_INVENTORY_DAYS),
        ("每日采购预算", "SAME", "¥%.0f" % BUDGET),
        ("售价 / 成本", "SAME", "同一份 products 档案"),
        ("保质期 shelf life", "SAME", "同一份 products 档案，FEFO 批次管理"),
        ("到货提前期 lead time", "SAME", "同一份 products 档案"),
        ("供应商可用性", "SAME", "同一份 day_events（供应商D 断供日统一拦截）"),
        ("天气 / 节日 / 事件序列", "SAME", "同一份 day_events"),
        ("到货规则", "SAME", "下单后按 lead_time 到达，独立新批次"),
        ("损耗规则", "SAME", "到期批次整体报损（售前），规则与 core/simulator 一致"),
        ("缺货定义", "SAME", "max(0, potential_demand − FEFO实际销量)"),
        ("随机种子", "SAME", "seed=%d（仅用于事件冲击的随机化，需求本身确定）" % SEED),
        ("决策可见信息", "SAME", "决策层只读「今天以前」的历史销量 + 今天已知事件"),
    ]
    print("  %-24s %-8s %s" % ("条件", "判定", "说明"))
    print("  " + "─" * 104)
    for name, verdict, why in rows:
        print("  %-24s %-8s %s" % (name, verdict, why))
    print("  " + "─" * 104)
    diff = [r for r in rows if r[1] != "SAME"]
    print("  → %s" % ("PASS 全部 SAME，环境公平" if not diff
                     else "FAIL 存在 DIFFERENT：%s" % [r[0] for r in diff]))


def print_ablation(res: dict, order: list) -> None:
    print()
    print("=" * 108)
    print("消融实验（拆解各设计点的贡献；不作为主结论）")
    print("=" * 108)
    keys = ["stockout_rate", "liv_stockout_rate", "liv_secured_rate",
            "gross_profit", "revenue", "average_inventory_value"]
    print("  %-42s %10s %10s %10s %10s %10s %10s"
          % ("策略", "缺货率", "民生缺货", "民生保障", "经营毛利", "收入", "均库存"))
    print("  " + "─" * 106)
    for k in order:
        if k not in res:
            continue
        r = res[k]
        print("  %-42s %9.2f%% %9.2f%% %9.1f%% %10.0f %10.0f %10.0f"
              % (r["label"][:40], r["stockout_rate"] * 100, r["liv_stockout_rate"] * 100,
                 r["liv_secured_rate"] * 100, r["gross_profit"], r["revenue"],
                 r["average_inventory_value"]))


def main() -> int:
    global _EVENT_BY_DAY
    gt = sim.load_ground_truth()
    _EVENT_BY_DAY = gt["event_by_day"]

    print("=" * 108)
    print("小满 · 公平 A/B 对照实验")
    print("=" * 108)
    print("  时间窗口   : %s ~ %s（%d 天）" % (gt["day_list"][0], gt["day_list"][-1], len(gt["day_list"])))
    print("  商品数: %d    每日预算: ¥%.0f    seed: %d" % (len(gt["products"]), BUDGET, SEED))
    print("  潜在需求定义: CSV 的 sales 字段被解释为「仿真生成的潜在消费需求」")
    print("缺货由各算法自己的库存决定，不使用 CSV 里预生成的 stockout（它恒为 0）。")
    print()
    print_condition_checklist(gt)

    strategies = build_strategies()
    results = {}
    main_keys = []
    print()
    print("=" * 108)
    print("运行中…（每条策略 180 天逐日经营，请稍候）")
    print("=" * 108)
    for s in strategies:
        t0 = time.time()
        r = run_strategy(s, gt, BUDGET, SEED)
        r["wall_sec"] = round(time.time() - t0, 1)
        results[s.key] = r
        if not isinstance(s, (NeverRestockPlanner, UnlimitedBudgetPlanner)):
            main_keys.append(s.key)
        print("  ✓ %-46s %6.1fs  缺货率 %5.2f%%  民生缺货 %5.2f%%  毛利 %9.0f  均库存 %9.0f"
              % (r["label"][:44], r["wall_sec"], r["stockout_rate"] * 100,
                 r["liv_stockout_rate"] * 100, r["gross_profit"], r["average_inventory_value"]))

    # ── 主实验 ──
    trad_key = "traditional"
    dn_key = "diannao"
    if trad_key in results and dn_key in results:
        print_main_table(results, trad_key, dn_key)

    # ── 消融 ──
    print_ablation(results, ["traditional", "forecast_only", "forecast_r3",
                             "forecast_r3_liv", "diannao_no_memory", "diannao"])

    # ── sanity checks ──
    print()
    print("=" * 108)
    print("sanity checks（任一不符预期 → 实验判定 FAIL，不产出宣传结论）")
    print("=" * 108)
    checks = []

    # SC1 永不补货
    nr = results.get("never_restock")
    if nr:
        ok = nr["stockout_rate"] > 0.5
        checks.append(("SC1 永不补货 → 严重缺货", ok,
                       "缺货率 %.2f%%（应 > 50%%）" % (nr["stockout_rate"] * 100)))
    # SC2 无限预算 → 接近上限
    ul = results.get("unlimited")
    base = results.get(trad_key)
    if ul and base:
        ok = ul["stockout_rate"] < base["stockout_rate"]
        checks.append(("SC2 无限预算 → 服务水平高于传统", ok,
                       "无限预算缺货率 %.2f%% vs 传统 %.2f%%"
                       % (ul["stockout_rate"] * 100, base["stockout_rate"] * 100)))
    # SC3 可复现：同策略跑两次
    print()
    print("  SC3 可复现性检验（重跑「小满（完整）」并逐位比对）…")
    t0 = time.time()
    again = run_strategy(
        PolicyPlanner("diannao", "小满（完整）", "", policy.MODE_DIANNAO, True, True, True),
        gt, BUDGET, SEED)
    orig = results[dn_key]
    diffs = []
    for k in ("revenue", "gross_profit", "stockout_rate", "unmet_demand",
              "liv_stockout_rate", "spoilage_qty", "average_inventory_value",
              "ending_inventory_value", "purchase_amount"):
        if abs(float(orig.get(k, 0)) - float(again.get(k, 0))) > 1e-6:
            diffs.append("%s: %.4f → %.4f" % (k, orig.get(k, 0), again.get(k, 0)))
    checks.append(("SC3 同策略跑两次 → 结果一致", not diffs,
                   "全部指标逐位一致" if not diffs else "不一致：" + "; ".join(diffs)))
    print("    重跑耗时 %.1fs" % (time.time() - t0))

    print()
    for name, ok, detail in checks:
        print("  %-44s %-6s %s" % (name, "PASS" if ok else "FAIL", detail))
    all_ok = all(ok for _, ok, _ in checks)
    print()
    print("  → 实验判定：%s" % ("PASS（可产出结论）" if all_ok
                                else "★ FAIL（不得产出任何宣传结论）"))

    # ── 落盘 ──
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "eval", "fair_ab_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    payload = {
        "config": {
            "days": len(gt["day_list"]),
            "start": gt["day_list"][0],
            "end": gt["day_list"][-1],
            "n_sku": len(gt["products"]),
            "daily_budget": BUDGET,
            "seed": SEED,
            "init_inventory_days": INIT_INVENTORY_DAYS,
            "traditional_rule": "目标库存 = 最近%d天平均销量 × %.1f天；预算内按毛利率降序"
                               % (TRAD_N_DAYS, TRAD_COVER_DAYS),
            "demand_semantics": "CSV sales 视为仿真潜在需求；缺货由各算法库存决定",
            "gross_profit_formula": "Σ(实销×(售价−成本)) − Σ(报损×成本)  【经营毛利，非净利润】",
        },
        "results": results,
        "sanity_checks": [{"name": n, "pass": bool(o), "detail": d} for n, o, d in checks],
        "experiment_verdict": "PASS" if all_ok else "FAIL",
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print()
    print("  结果已写入：%s" % out_path)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
