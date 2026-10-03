# -*- coding: utf-8 -*-
"""
小满 · Digital Store 180 天长期经营仿真器（创新点 1 的长期验证）

把「小满 R³ 策略」与「传统纯利润策略」放到**完全相同**的经营环境里连续经营 180 天，
量化两种决策策略在长时间尺度上的真实差异。与「今天该进什么货 → 和传统算法比一比」的
单日对比不同，本模块回答的是：如果让小店用同一种策略连续经营半年，长期结果差在哪。

═══ 实验公平性（三处硬保证）═══
1. 同一套真实需求序列：180 天的每日真实需求 = data/shopmind_180days_50sku.csv 的 sales 列，
   两个策略逐天面对完全相同的需求与天气/节假日/供应商断供事件。
2. 同一套初始条件：初始库存 = base_daily_demand × 3（与 seed_data 同口径），策略参数
   同为初始温和值，供应商交期、进价、售价、保质期完全相同。
3. 唯一差别 = 补货决策策略：
      · 小满 R³   —— R³ 多目标 MILP（Revenue + Resilience + Responsibility）+ 经营记忆；
      · 传统算法 —— 按「单位资金毛利」从高到低的纯利润贪心，无惠民约束、无经营记忆。

═══ 无未来数据泄漏（逐日因果）═══
第 t 天做补货决策时，决策层只能读到「第 t 天以前」写入 sales 表的经营记录（含潜在需求
还原），外加第 t 天当天「已知」的天气/节假日/供应商状态（来自 day_events）。真实需求只
以「上帝视角」保存在 Python 字典里供结算使用，绝不喂给决策层 —— 结算与决策分两条通道。

═══ 逐日经营流程 ═══
  昨日批次库存 → 商品到货(在途库存, 按供应商交期, 到货生成新批次) → Agent/算法补货决策(下在途单)
  → 到期批次报损(售前) → 当日真实需求发生 → FEFO 销售(优先最早到期批次)
  → 缺货 = 需求 − 销量 → 计毛利 → 更新批次库存 → 写经营反馈(供次日预测与记忆学习) → 次日
"""

import csv
import json
import math
import os
import random
import tempfile
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from . import dataset, event_evidence, events, evolution, memory, metrics, policy, risk
from .config import BASE_DIR, CURRENCY, RESTORE_POTENTIAL

# ── 长期仿真预算（单日进货预算上限，两策略相同）──────────────
# 数据里 180 天日均需求成本约 ¥1835、峰值约 ¥2303（高温日）。
# 预算取 ¥1800：普通日足够周转，高温等需求峰值日偏紧，逼出「预算一紧，
# 纯利润先砍民生」的取舍 —— 这正是要验证的差异；预算设成谁都买得起会退化成一团。
DEFAULT_SIM_BUDGET = 1800.0

# 固定随机种子：本仿真全程确定性（需求来自固定 CSV，无随机），种子仅用于复现与存档。
DEFAULT_SEED = 42

EVAL_DIR = BASE_DIR / "eval"

# 初始库存 = 基础日均需求 × 该倍数（与 dataset.INIT_INVENTORY_DAYS 一致）
INIT_INVENTORY_DAYS = 3.0


# ════════════════════════════════════════════════════════════
# 策略定义
# ════════════════════════════════════════════════════════════
def _strategy_specs() -> dict:
    """返回全部策略的配置（主对比 2 个 + 消融 5 个，去重后共 5 个不同配置）。

    公平性：所有策略共用同一 _simulate_strategy 环境（同需求 / 天气 / 供应商 /
    交期 / 保质期 / FEFO / 损耗 / 预算 / 初始库存 / 成本）。策略间只允许三处
    「决策能力」差异：mode（R³ MILP vs 纯利润贪心）、protect_livelihood（民生兜底）、
    use_memory（经营记忆）。因此主对比 diannao vs baseline 同时含这三处差异，
    解读时应结合消融（diannao_no_memory / diannao_no_responsibility）拆分归因。
    """
    return {
        "diannao": {
            "key": "diannao", "label": "小满 R³（完整）",
            "mode": policy.MODE_DIANNAO, "use_memory": True,
            "use_events": True, "protect_livelihood": True,
            "desc": "R³多目标 + 经营记忆 + 事件感知 + 民生兜底",
        },
        "baseline": {
            "key": "baseline", "label": "传统算法（纯利润）",
            "mode": policy.MODE_BASELINE, "use_memory": False,
            "use_events": True, "protect_livelihood": False,
            "desc": "纯利润贪心，无惠民约束、无经营记忆",
        },
        "diannao_no_memory": {
            "key": "diannao_no_memory", "label": "小满 − Memory",
            "mode": policy.MODE_DIANNAO, "use_memory": False,
            "use_events": True, "protect_livelihood": True,
            "desc": "去掉经营记忆/策略自进化，其余同完整小满",
        },
        "diannao_no_event": {
            "key": "diannao_no_event", "label": "小满 − Event",
            "mode": policy.MODE_DIANNAO, "use_memory": True,
            "use_events": False, "protect_livelihood": True,
            "desc": "去掉天气/节假日/断供事件感知，其余同完整小满",
        },
        "diannao_no_responsibility": {
            "key": "diannao_no_responsibility", "label": "小满 − R³责任目标",
            "mode": policy.MODE_DIANNAO, "use_memory": True,
            "use_events": True, "protect_livelihood": False,
            "desc": "去掉惠民约束（MILP 只留收益+韧性），其余同完整小满",
        },
    }


MAIN_STRATEGIES = ["diannao", "baseline"]
ABLATION_STRATEGIES = ["diannao", "diannao_no_memory", "diannao_no_event",
                       "diannao_no_responsibility", "baseline"]


# ════════════════════════════════════════════════════════════
# 仿真基础
# ════════════════════════════════════════════════════════════
def _add_days(day: str, n: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=n)).isoformat()


def _make_batch(arrival: str, qty: float, shelf_life_days) -> dict:
    """创建一个库存批次。

    expiry_date = arrival + shelf_life_days（ISO 日期相加，天数向上取整为整日）。
    统一语义：批次在 [arrival, expiry_date) 内可售，即最后可售日 = expiry_date − 1 天；
    expiry_date 当天凌晨起视为过期，必须报损下架，不再参与销售。
    因此 shelf_life_days = 可售天数（含到货当天），避免 off-by-one。
    """
    shelf = max(1, int(round(float(shelf_life_days))))
    return {"arrival": arrival, "expiry": _add_days(arrival, shelf), "qty": float(qty)}


def _total_qty(batches: list[dict]) -> float:
    """批次队列的总可售数量 —— 即与 Policy / R³ 接口兼容的 on_hand 标量视图。"""
    return sum(b["qty"] for b in batches)


def _expire_batches(batches: list[dict], day: str) -> float:
    """到期报损：expiry_date <= day 的批次整体报废并移除，返回报损件数。

    保证：每个批次只报损一次（报损即从队列删除）；报损后不可再销售；
    新到货不会恢复已报损库存。
    """
    expired = 0.0
    alive = []
    for b in batches:
        if b["expiry"] <= day:
            expired += b["qty"]
        else:
            alive.append(b)
    batches[:] = alive
    return expired


def _fefo_sell(batches: list[dict], demand: float) -> float:
    """FEFO 销售：优先卖最早到期批次（First Expired, First Out），返回实际销量。

    就地扣减各批次数量，售罄批次移除；缺货部分由调用方用 max(0, demand − sold) 计算。
    """
    batches.sort(key=lambda b: (b["expiry"], b["arrival"]))
    remaining = max(0.0, demand)
    sold = 0.0
    for b in batches:
        if remaining <= 1e-12:
            break
        take = min(b["qty"], remaining)
        b["qty"] -= take
        sold += take
        remaining -= take
    batches[:] = [b for b in batches if b["qty"] > 1e-12]
    return sold


def load_ground_truth() -> dict:
    """读取 CSV 经营数据，返回「上帝视角」的真实需求与环境（决策层永不接触）。"""
    products = dataset.read_products()
    sales_rows, day_events_rows = dataset.read_sales()
    return {
        "products": products,
        "prod_map": {p["sku"]: p for p in products},
        "demand_map": {(r["day"], r["sku"]): float(r["qty_sold"]) for r in sales_rows},
        "day_list": sorted({r["day"] for r in sales_rows}),
        "event_by_day": {e["day"]: e["event"] for e in day_events_rows},
        "day_events_rows": day_events_rows,
    }


def _day_risk_keys(day: str, event_by_day: dict) -> list[str]:
    """把某天的经营事件映射成补货时的风险键（与 app.py 的 _day_risks 同口径）。"""
    label = event_by_day.get(day, "正常")
    key = events.LABEL_TO_EVENT_KEY.get(label)
    return [key] if key else []


def _enforce_supplier_outage(day: str, event_by_day: dict,
                             items: list[dict]) -> list[str]:
    """环境强制执行「供应商断供」：断供日对断供供应商的商品下单全部拦截（置零）。

    这是「外部世界真的断供」的环境约束，与 Agent 是否知晓无关：
      · Event-Aware（已知晓断供）本就不下单（reorder=0），这里是 no-op；
      · Event-Blind（不知晓断供）仍会下单，环境在此拦截，从而保证两个世界面对
        完全相同的真实供给环境 —— 区别只在于 Agent 能否提前感知并调整。
    返回被拦截的 SKU 列表（供仿真日志与测试观察）。
    """
    if event_by_day.get(day, "正常") != events.EVENT_KEY_TO_LABEL["supplier"]:
        return []
    blocked = []
    for it in items:
        if it["supplier"] == risk.SUPPLIER_OUTAGE_NAME and it["reorder_qty"] > 1e-9:
            it["reorder_qty"] = 0.0
            it["cost"] = 0.0
            blocked.append(it["sku"])
    return blocked


def _setup_isolated_db(db_path, products: list[dict], day_events_rows: list[dict]) -> None:
    """在隔离库上重建「商品档案 + 初始策略参数 + 每日经营事件」，sales 从零开始。"""
    memory.init_db(db_path)
    memory.reset_all(db_path)
    memory.upsert_products(products, db_path)
    for p in products:
        base_days = 4.0 if p["is_livelihood"] else 3.0
        memory.set_policy(p["sku"], base_days, 0.15, db_path=db_path)
    memory.upsert_day_events(day_events_rows, db_path)


def _fresh_db() -> Path:
    fd, path = tempfile.mkstemp(suffix=".db", prefix="diannao_sim_")
    os.close(fd)
    return Path(path)


# ════════════════════════════════════════════════════════════
# 单策略仿真
# ════════════════════════════════════════════════════════════
def _simulate_strategy(spec: dict, gt: dict, budget: float, seed: int,
                       keep_daily: bool = True) -> dict:
    """在隔离记忆库上把某策略连续经营 180 天，返回逐日/逐 SKU 日志与长期汇总。

    只有补货决策与记忆学习写进隔离库；真实需求始终来自 gt（上帝视角），不写回库。
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
    day_list = gt["day_list"]
    event_by_day = gt["event_by_day"]

    db_path = _fresh_db()
    _setup_isolated_db(db_path, products, gt["day_events_rows"])

    old_path = memory.DB_PATH
    memory.DB_PATH = str(db_path)
    events.clear_impact_cache()
    event_evidence.clear_cache()

    daily_logs = []
    daily_series = []          # 逐日聚合：{day, gross_margin, stockout, demand, livelihood, inventory}
    daily_livelihood = []      # 逐日民生最低保障达标率（= 当日 plan.metrics.livelihood_secured_rate）

    # —— 汇总累加器（全部由仿真日志真实计算）——
    total_sold = total_demand = total_stockout = total_spoiled = 0.0
    total_revenue = total_purchase = total_gross = total_cogs = 0.0
    total_spoilage_cost = 0.0
    total_livelihood_demand = 0.0
    total_livelihood_stockout = 0.0
    total_livelihood_sold = 0.0
    stockout_sku = set()
    stockout_occurrences = 0
    inventory_value_list = []
    mem_exp_count = 0

    try:
        # 批次库存：每 SKU 一个批次队列（dict: arrival/expiry/qty）。
        # 初始库存统一作为 day_list[0] 的「当日到货批次」——仿真简化假设：无真实采购历史年龄。
        first_day = day_list[0]
        batches = {p["sku"]: [_make_batch(first_day,
                                          math.ceil(p["base_daily_demand"] * INIT_INVENTORY_DAYS),
                                          p["shelf_life_days"])]
                   for p in products}
        in_transit = {p["sku"]: [] for p in products}  # 每 SKU 的 [(到货日, 数量)]

        for day in day_list:
            # ① 商品到货：处理在途库存（供应商交期 → 到货），到货创建独立新批次，绝不刷新旧批次
            arrivals = {}
            for p in products:
                sku = p["sku"]
                arrived = 0.0
                remaining = []
                for (arr_day, qty) in in_transit[sku]:
                    if arr_day == day:
                        arrived += qty
                    else:
                        remaining.append((arr_day, qty))
                in_transit[sku] = remaining
                if arrived > 1e-9:
                    batches[sku].append(_make_batch(day, arrived, p["shelf_life_days"]))
                arrivals[sku] = arrived

            # ② 补货决策：只读「今天以前」的 sales + 今天已知的事件；下单按交期到货
            # 决策层只看到标量库存（批次求和），保持 Policy / R³ 接口不变
            memory.set_inventory_bulk([(p["sku"], _total_qty(batches[p["sku"]]))
                                       for p in products])
            events.clear_impact_cache()  # 事件乘数需反映「截至今天」的历史，故逐日重算
            event_evidence.clear_cache()  # 事件证据门控同样需反映「截至今天」的历史
            risks = _day_risk_keys(day, event_by_day) if spec["use_events"] else []
            # 在途库存带「到货日」传给策略层，供其按评估窗口筛出「有效在途」（口径一致）
            in_transit_map = {sku: list(lst) for sku, lst in in_transit.items()}
            on_hand_batches = {sku: [((date.fromisoformat(b['expiry']) - date.fromisoformat(day)).days, b['qty']) for b in batches[sku] if b['qty'] > 1e-9] for sku in batches}
            _min_rem = {sku: min((r for r, q in on_hand_batches[sku]), default=0) for sku in on_hand_batches}
            _near_exp = {sku: sum(q for r, q in on_hand_batches[sku] if r <= 2) for sku in on_hand_batches}
            plan = policy.build_plan(
                day, budget, spec["mode"], persist=False,
                restore_potential=RESTORE_POTENTIAL, risks=risks,
                use_memory=spec["use_memory"],
                protect_livelihood=spec["protect_livelihood"],
                in_transit_map=in_transit_map, on_hand_batches=on_hand_batches, spoilage_control=spec.get("spoilage_control", True),
            )
            items = plan["items"]
            by_sku = {it["sku"]: it for it in items}
            # 结算层环境约束：断供日供应商D的商品下单被强制拦截（Agent 是否知晓无关）。
            # Event-Aware 已知晓故 reorder 本就为 0（no-op）；Event-Blind 下单在此被拦，
            # 使两个世界的真实供给环境完全一致。
            _enforce_supplier_outage(day, event_by_day, items)
            for p in products:
                sku = p["sku"]
                qty = by_sku[sku]["reorder_qty"]
                if qty > 1e-9:
                    lead = max(1, int(p["lead_time_days"] or 1))
                    in_transit[sku].append((_add_days(day, lead), qty))

            daily_livelihood.append(plan["metrics"]["livelihood_secured_rate"])

            # ③–⑤ 需求 → 销售 → 缺货 → 损耗 → 更新库存
            day_gross = day_stockout = day_demand = 0.0
            day_inventory_value = 0.0
            feedback = []
            for p in products:
                sku = p["sku"]
                it = by_sku[sku]
                demand = demand_map.get((day, sku), 0.0)
                opening = _total_qty(batches[sku])          # 期初有效库存（到货后、报损前）
                spoil = _expire_batches(batches[sku], day)  # 售前到期报损
                sold = _fefo_sell(batches[sku], demand)     # FEFO 销售（最早到期优先）
                stockout = max(0.0, demand - sold)
                closing = _total_qty(batches[sku])

                margin = p["sell_price"] - p["cost_price"]
                revenue = sold * p["sell_price"]
                purchase = it["reorder_qty"] * p["cost_price"]
                gross = sold * margin - spoil * p["cost_price"]

                # —— 汇总 ——
                total_sold += sold
                total_demand += demand
                total_stockout += stockout
                if p["is_livelihood"]:
                    total_livelihood_demand += demand
                    total_livelihood_stockout += stockout
                    total_livelihood_sold += sold
                total_spoiled += spoil
                total_revenue += revenue
                total_purchase += purchase
                total_gross += gross
                total_cogs += sold * p["cost_price"]
                total_spoilage_cost += spoil * p["cost_price"]
                day_gross += gross
                day_stockout += stockout
                day_demand += demand
                day_inventory_value += closing * p["cost_price"]
                if stockout > 0.5:
                    stockout_sku.add(sku)
                    stockout_occurrences += 1

                if keep_daily:
                    daily_logs.append({
                        "strategy": spec["key"], "day": day, "sku": sku,
                        "name": p["name"], "category": p["category"],
                        "is_livelihood": int(p["is_livelihood"]),
                        "event": event_by_day.get(day, "正常"),
                        "opening_inventory": round(opening, 2),
                        "arrivals": round(arrivals[sku], 2),
                        "forecast_demand": round(it["daily_demand"], 2),
                        "actual_demand": round(demand, 2),
                        "reorder_qty": round(it["reorder_qty"], 2),
                        "sold_qty": round(sold, 2),
                        "stockout_qty": round(stockout, 2),
                        "spoilage_qty": round(spoil, 2),
                        "closing_inventory": round(closing, 2),
                        "revenue": round(revenue, 2),
                        "purchase_cost": round(purchase, 2),
                        "gross_margin": round(gross, 2), "spoilage_capped": int(it.get("spoilage_capped", False)), "raw_reorder_uncapped": round(it.get("raw_reorder_uncapped", 0.0), 2), "free_sellable_capacity": round(it.get("free_sellable_capacity", 0.0), 1), "expected_excess_qty": round(it.get("expected_excess_qty", 0.0), 1), "min_remaining_shelf": int(_min_rem.get(sku, 0)), "near_expiry_qty": round(_near_exp.get(sku, 0.0), 2), "memory_adjustment_factor": round(it.get("memory_adjustment_factor", 1.0), 4), "memory_delta": round(it.get("memory_delta", 0.0), 4),
                    })
                feedback.append({"sku": sku, "qty_sold": sold,
                                 "qty_stockout": stockout, "qty_spoilage": spoil})

            inventory_value_list.append(day_inventory_value)
            daily_series.append({
                "day": day,
                "gross_margin": day_gross,
                "stockout_qty": day_stockout,
                "demand_qty": day_demand,
                "livelihood_rate": plan["metrics"]["livelihood_secured_rate"],
                "inventory_value": day_inventory_value,
                "event": event_by_day.get(day, "正常"),
            })

            # ⑥ 经营反馈写回：销量/断货/报损入 sales（供次日预测），记忆学习按策略开关
            evolution.apply_sales_only(day, feedback)
            if spec["use_memory"]:
                plan_context = {it["sku"]: {"forecast_qty": it["daily_demand"],
                                            "reorder_qty": it["reorder_qty"]}
                                for it in items}
                evolution.process_feedback(day, feedback, plan_context=plan_context)

        mem_exp_count = len(memory.get_experiences(limit=100000))

    finally:
        memory.DB_PATH = old_path
        events.clear_impact_cache()
        event_evidence.clear_cache()
        try:
            db_path.unlink(missing_ok=True)
        except Exception:
            pass

    # —— 长期指标（全部由日志真实计算，公式见 docstring 与页面说明）——
    n_days = len(daily_series)
    avg_inventory_capital = metrics.avg_inventory_capital(inventory_value_list)
    summary = {
        "strategy": spec["key"],
        "label": spec["label"],
        "desc": spec["desc"],
        # 累计毛利 = Σ(实销×毛利额) − Σ(损耗×进价)
        "cumulative_gross_margin": round(total_gross, 2),
        "revenue": round(total_revenue, 2),
        "purchase_cost": round(total_purchase, 2),
        "cogs": round(total_cogs, 2),
        # 缺货率 = 缺货件数 ÷ 真实需求件数
        "stockout_rate": round(metrics.stockout_rate(total_stockout, total_demand), 6),
        "stockout_qty": round(total_stockout, 1),
        "stockout_sku_count": len(stockout_sku),
        "stockout_occurrences": stockout_occurrences,
        # 民生最低保障达标率 = 180 天平均的每日民生最低保障达标率（沿用 policy.calculate_essential_coverage 口径）
        "livelihood_secured_rate": round(sum(daily_livelihood) / n_days, 6) if n_days else 0.0,
        # 民生商品实际缺货（真实结算口径，由逐日仿真日志动态累计，禁止硬编码）：
        #   实际缺货件数 = Σ 民生 SKU max(0, 真实需求 − 实际销量)
        #   实际缺货率   = 实际缺货件数 ÷ 民生 SKU 真实需求件数
        "livelihood_stockout_qty": round(total_livelihood_stockout, 1),
        "livelihood_stockout_rate": round(metrics.livelihood_stockout_rate(total_livelihood_stockout, total_livelihood_demand), 6),
        "livelihood_fill_rate": round(metrics.livelihood_fill_rate(total_livelihood_sold, total_livelihood_demand), 6),

        # 损耗率 = 报损件数 ÷ 可供销售总件数（销量+报损，metrics.spoilage_rate）
        "spoilage_rate": round(metrics.spoilage_rate(total_spoiled, total_sold), 6),

        # 原始指标（更直观，避免被大分母稀释）：过期报损总件数 / 总报损成本
        "spoilage_qty": round(total_spoiled, 1),
        "spoilage_units": round(total_spoiled, 1),
        "spoilage_cost": round(total_spoilage_cost, 2),
        # 平均库存资金占用 = 每日期末库存成本金额的平均值（metrics.avg_inventory_capital）
        "avg_inventory_capital": round(avg_inventory_capital, 2),
        # 库存周转 = 销售成本(COGS) ÷ 平均库存资金占用（180 天内的周转次数）
        "inventory_turnover": round(metrics.inventory_turnover(total_cogs, avg_inventory_capital), 4),

        "n_days": n_days,
        "memory_experiences": mem_exp_count,
    }

    return {
        "key": spec["key"],
        "label": spec["label"],
        "daily_logs": daily_logs,
        "daily": daily_series,
        "daily_livelihood": daily_livelihood,
        "summary": summary,
    }


# ════════════════════════════════════════════════════════════
# 实验运行与结果保存
# ════════════════════════════════════════════════════════════
def run_strategies(strategy_keys, budget: float = DEFAULT_SIM_BUDGET,
                   seed: int = DEFAULT_SEED, keep_daily: bool = True) -> dict:
    """跑一组策略，返回 {strategy_key: result}。"""
    gt = load_ground_truth()
    specs = _strategy_specs()
    out = {}
    for key in strategy_keys:
        out[key] = _simulate_strategy(specs[key], gt, budget, seed, keep_daily=keep_daily)
    return out


def _config_payload(gt, budget, seed, strategy_keys):
    return {
        "date_range": [gt["day_list"][0], gt["day_list"][-1]],
        "n_days": len(gt["day_list"]),
        "budget": budget,
        "seed": seed,
        "initial_inventory_rule": (f"base_daily_demand × {INIT_INVENTORY_DAYS} 天（向上取整），"
                                   "统一作为仿真起始日批次（无真实采购历史年龄）"),
        "strategies": [{"key": k, **_strategy_specs()[k]} for k in strategy_keys],
        "risk_scenarios": ["正常经营", "高温", "暴雨", "供应商D断供", "综合风险"],
        "note": "需求序列 = data/shopmind_180days_50sku.csv 的 sales 列（固定，非随机）；"
                "决策层只读当天以前的记录，真实需求仅在结算时使用。",
    }


def write_csvs(results: dict, gt: dict, budget: float, seed: int,
               strategy_keys: list[str], keep_daily: bool = True) -> dict:
    """把实验结果落盘：逐日明细 CSV + 汇总 CSV + 配置 JSON。返回写入的路径。"""
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    paths = {}

    if keep_daily:
        daily_path = EVAL_DIR / "digital_store_daily.csv"
        fieldnames = ["strategy", "day", "sku", "name", "category", "is_livelihood",
                      "event", "opening_inventory", "arrivals", "forecast_demand",
                      "actual_demand", "reorder_qty", "sold_qty", "stockout_qty",
                      "spoilage_qty", "closing_inventory", "revenue", "purchase_cost",
                      "gross_margin", "spoilage_capped", "raw_reorder_uncapped", "free_sellable_capacity", "expected_excess_qty", "min_remaining_shelf", "near_expiry_qty", "memory_adjustment_factor", "memory_delta"]
        with open(daily_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for key in strategy_keys:
                w.writerows(results[key]["daily_logs"])
        paths["daily"] = str(daily_path)

    summary_path = EVAL_DIR / "digital_store_summary.csv"
    summ_fields = ["strategy", "label", "cumulative_gross_margin", "revenue",
                   "purchase_cost", "cogs", "stockout_rate", "stockout_qty",
                   "stockout_sku_count", "stockout_occurrences",
                   "livelihood_secured_rate", "livelihood_stockout_qty",
                   "livelihood_stockout_rate", "spoilage_rate", "spoilage_qty",
                   "spoilage_units", "spoilage_cost", "avg_inventory_capital",
                   "inventory_turnover"]
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=summ_fields, extrasaction="ignore")
        w.writeheader()
        for key in strategy_keys:
            w.writerow(results[key]["summary"])
    paths["summary"] = str(summary_path)

    config_path = EVAL_DIR / "digital_store_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(_config_payload(gt, budget, seed, strategy_keys), f,
                  ensure_ascii=False, indent=2)
    paths["config"] = str(config_path)

    return paths


# ════════════════════════════════════════════════════════════
# 风险压力测试（前 → 中 → 后）
# ════════════════════════════════════════════════════════════
def _contiguous_windows(days: list[str]) -> list[list[date]]:
    if not days:
        return []
    ds = sorted(date.fromisoformat(d) for d in days)
    windows = [[ds[0]]]
    for d in ds[1:]:
        if (d - windows[-1][-1]).days == 1:
            windows[-1].append(d)
        else:
            windows.append([d])
    return windows


RISK_SCENARIOS = [
    ("heat", "高温"),
    ("rain", "暴雨"),
    ("supplier", "供应商D断供"),
    ("combined", "综合风险"),
]


def stress_analysis(results: dict, gt: dict, before_n: int = 3, after_n: int = 3) -> list[dict]:
    """对每一类风险事件，用 180 天日志切出「发生前 N 天 / 发生期间 / 结束后 N 天」三段，
    分别统计总体缺货率、民生最低保障达标率、毛利与平均库存资金占用 —— 全程只读仿真日志，不另跑实验。
    """
    event_by_day = gt["event_by_day"]
    day_list = gt["day_list"]
    valid = set(day_list)

    def phase_days(event_days):
        windows = _contiguous_windows(event_days)
        before, after = set(), set()
        for w in windows:
            for i in range(1, before_n + 1):
                before.add((w[0] - timedelta(days=i)).isoformat())
            for i in range(1, after_n + 1):
                after.add((w[-1] + timedelta(days=i)).isoformat())
        return before & valid, set(event_days), after & valid

    rows = []
    for rkey, rlabel in RISK_SCENARIOS:
        if rkey == "combined":
            ev_days = [d for d in day_list if event_by_day.get(d, "正常") != "正常"]
        else:
            ev_days = [d for d in day_list if event_by_day.get(d, "正常") == rlabel]
        if not ev_days:
            continue
        before, during, after = phase_days(ev_days)
        for key, res in results.items():
            dmap = {r["day"]: r for r in res["daily"]}
            for phase_name, dset in [("before", before), ("during", during), ("after", after)]:
                days_in = [dmap[d] for d in sorted(dset) if d in dmap]
                if not days_in:
                    continue
                so = sum(r["stockout_qty"] for r in days_in)
                demand = sum(r["demand_qty"] for r in days_in)
                rows.append({
                    "risk": rlabel,
                    "strategy": key,
                    "label": res["label"],
                    "phase": phase_name,
                    "n_days": len(days_in),
                    "stockout_rate": round(so / demand, 6) if demand > 0 else 0.0,
                    "stockout_qty": round(so, 1),
                    "livelihood_rate": round(
                        sum(r["livelihood_rate"] for r in days_in) / len(days_in), 6),
                    "gross_margin": round(sum(r["gross_margin"] for r in days_in), 2),
                    "avg_inventory_capital": round(
                        sum(r["inventory_value"] for r in days_in) / len(days_in), 2),
                })
    return rows


def write_stress_csv(rows: list[dict]) -> str:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    path = EVAL_DIR / "digital_store_stress.csv"
    fields = ["risk", "strategy", "label", "phase", "n_days", "stockout_rate",
              "stockout_qty", "livelihood_rate", "gross_margin", "avg_inventory_capital"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return str(path)


def write_ablation_csv(results: dict) -> str:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    path = EVAL_DIR / "ablation_results.csv"
    fields = ["strategy", "label", "cumulative_gross_margin", "stockout_rate",
              "stockout_qty", "livelihood_secured_rate", "livelihood_stockout_qty",
              "livelihood_stockout_rate", "spoilage_rate",
              "avg_inventory_capital", "inventory_turnover"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for key, res in results.items():
            w.writerow(res["summary"])
    return str(path)


# ════════════════════════════════════════════════════════════
# 可视化
# ════════════════════════════════════════════════════════════
_STRATEGY_COLORS = {
    "diannao": "#2c7a4b",
    "baseline": "#c0392b",
    "diannao_no_memory": "#1f4e79",
    "diannao_no_event": "#e67e22",
    "diannao_no_responsibility": "#8e44ad",
}


def build_cumulative_figure(results: dict):
    """图 1：180 天累计毛利曲线（逐日累加，两条策略各一条线）。"""
    import plotly.graph_objects as go

    fig = go.Figure()
    for key, res in results.items():
        days = [r["day"] for r in res["daily"]]
        cum = []
        acc = 0.0
        for r in res["daily"]:
            acc += r["gross_margin"]
            cum.append(acc)
        fig.add_trace(go.Scatter(
            x=days, y=cum, mode="lines", name=res["label"],
            line=dict(color=_STRATEGY_COLORS.get(key, "#555"), width=2.5),
        ))
    fig.update_layout(
        title=dict(text="图 1 · 180 天累计毛利曲线", font=dict(size=18, color="#1f4e79")),
        xaxis_title="日期", yaxis_title="累计毛利（¥）",
        template="plotly_white", height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=30, t=70, b=60),
    )
    return fig


def build_rates_figure(results: dict):
    """图 2：180 天总体缺货率（上）与民生最低保障达标率（下）变化，7 天滚动平均平滑。"""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.10,
        subplot_titles=("总体缺货率（7 天滚动平均）", "民生最低保障达标率（7 天滚动平均）"),
    )

    def rolling(vals, w=7):
        out = []
        for i in range(len(vals)):
            seg = vals[max(0, i - w + 1):i + 1]
            out.append(sum(seg) / len(seg))
        return out

    for key, res in results.items():
        days = [r["day"] for r in res["daily"]]
        so_rate = [(r["stockout_qty"] / r["demand_qty"]) if r["demand_qty"] > 0 else 0.0
                   for r in res["daily"]]
        liv_rate = [r["livelihood_rate"] for r in res["daily"]]
        fig.add_trace(go.Scatter(
            x=days, y=rolling(so_rate), mode="lines", name=res["label"],
            line=dict(color=_STRATEGY_COLORS.get(key, "#555"), width=2),
            showlegend=(key == "diannao"),
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=days, y=rolling(liv_rate), mode="lines", name=res["label"],
            line=dict(color=_STRATEGY_COLORS.get(key, "#555"), width=2),
            showlegend=(key == "diannao"),
        ), row=2, col=1)

    fig.update_yaxes(tickformat=".1%", row=1, col=1)
    fig.update_yaxes(tickformat=".0%", row=2, col=1)
    fig.update_layout(
        title=dict(text="图 2 · 180 天总体缺货率 / 民生最低保障达标率变化", font=dict(size=18, color="#1f4e79")),
        height=600, template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="right", x=1),
        margin=dict(l=60, r=30, t=90, b=60),
    )
    return fig


def conclusion_text(results: dict) -> str:
    """根据真实实验结果动态生成客观结论（谁更好就如实说，不隐藏、不写死）。

    明确区分三个口径：累计毛利 / 总体缺货率（全 50 SKU）/ 民生商品实际缺货率
    （19 个民生 SKU 的真实未满足需求比例），全部从本次实验 summary 动态读取。
    """
    d = results["diannao"]["summary"]
    b = results["baseline"]["summary"]

    # —— 民生商品实际缺货（本次实验最核心的"民生获得感"口径）——
    d_liv_so = d.get("livelihood_stockout_rate", 0.0)
    b_liv_so = b.get("livelihood_stockout_rate", 0.0)
    d_liv_qty = d.get("livelihood_stockout_qty", 0.0)
    b_liv_qty = b.get("livelihood_stockout_qty", 0.0)
    if d_liv_so < b_liv_so - 0.00005:
        liv_part = (f"小满通过 R³ 责任约束，把民生商品实际缺货率从 {b_liv_so:.2%} "
                    f"降至 {d_liv_so:.2%}，未满足的民生需求由 {b_liv_qty:.0f} 件减少至 "
                    f"{d_liv_qty:.0f} 件")
    elif d_liv_so > b_liv_so + 0.00005:
        liv_part = (f"小满的民生商品实际缺货率为 {d_liv_so:.2%}，"
                    f"高于传统策略的 {b_liv_so:.2%}")
    else:
        liv_part = f"两种策略的民生商品实际缺货率基本一致（约 {d_liv_so:.2%}）"

    # —— 累计毛利（相对 0.5% 以内视为基本一致，避免把微小波动当成结论）——
    d_m = d["cumulative_gross_margin"]
    b_m = b["cumulative_gross_margin"]
    if abs(d_m - b_m) <= 0.005 * max(abs(b_m), 1.0):
        margin_part = (f"两种策略累计毛利基本一致（小满 {CURRENCY}{d_m:,.0f}，"
                       f"传统 {CURRENCY}{b_m:,.0f}）")
    elif d_m > b_m:
        margin_part = (f"小满累计毛利 {CURRENCY}{d_m:,.0f}，"
                       f"略高于传统策略的 {CURRENCY}{b_m:,.0f}")
    else:
        margin_part = (f"小满累计毛利 {CURRENCY}{d_m:,.0f}，"
                       f"略低于传统策略的 {CURRENCY}{b_m:,.0f}")

    # —— 总体缺货率（全 50 SKU）——
    if d["stockout_rate"] < b["stockout_rate"] - 0.0005:
        stock_part = (f"总体缺货率 {d['stockout_rate']:.2%}，"
                      f"低于传统策略的 {b['stockout_rate']:.2%}")
    elif d["stockout_rate"] > b["stockout_rate"] + 0.0005:
        stock_part = (f"总体缺货率 {d['stockout_rate']:.2%}，"
                      f"略高于传统策略的 {b['stockout_rate']:.2%}")
    else:
        stock_part = f"两种策略总体缺货率基本一致（约 {d['stockout_rate']:.2%}）"

    text = (f"在本次 180 天仿真中，{liv_part}；{margin_part}；{stock_part}。"
            f"这体现小满在收益、库存韧性与社区责任之间的多目标权衡，"
            f"而非单纯追求利润最大化。")
    return text


if __name__ == "__main__":
    # 命令行快速自测：跑主对比并打印汇总
    import sys
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    budget = float(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SIM_BUDGET
    results = run_strategies(MAIN_STRATEGIES, budget=budget, seed=DEFAULT_SEED)
    print("=" * 78)
    print(f"  小满 · Digital Store 180 天长期仿真（预算 {CURRENCY}{budget:.0f}/天，seed={DEFAULT_SEED}）")
    print("=" * 78)
    for key in MAIN_STRATEGIES:
        s = results[key]["summary"]
        print(f"  {s['label']:<18} 累计毛利 {CURRENCY}{s['cumulative_gross_margin']:>10,.0f} "
              f"总体缺货率 {s['stockout_rate']:>7.2%} 民生达标率 {s['livelihood_secured_rate']:>7.2%} "
              f"损耗率 {s['spoilage_rate']:>7.2%} 均库存 {CURRENCY}{s['avg_inventory_capital']:>9,.0f}")
    print("=" * 78)
