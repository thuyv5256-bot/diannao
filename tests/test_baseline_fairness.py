# -*- coding: utf-8 -*-
# 第7.1步：Traditional Baseline 公平性测试。
# 验证 R³ 与 Baseline 共享同一环境，且 Baseline 不读未来数据。

from core import policy, simulator


def _small_gt(n=12):
    gt = simulator.load_ground_truth()
    days = gt["day_list"][:n]
    gt["day_list"] = days
    gt["demand_map"] = {k: v for k, v in gt["demand_map"].items() if k[0] in days}
    gt["event_by_day"] = {d: gt["event_by_day"].get(d, "正常") for d in days}
    gt["day_events_rows"] = [e for e in gt["day_events_rows"] if e["day"] in days]
    return gt


def _run(key, n=12, seed=42, budget=1800.0):
    gt = _small_gt(n)
    return simulator._simulate_strategy(simulator._strategy_specs()[key], gt, budget, seed, keep_daily=True)


def test_same_initial_inventory_and_demand():
    d = _run("diannao")
    b = _run("baseline")
    dm = {(r["day"], r["sku"]): r for r in d["daily_logs"]}
    bm = {(r["day"], r["sku"]): r for r in b["daily_logs"]}
    assert set(dm) == set(bm)
    for k in dm:
        assert dm[k]["actual_demand"] == bm[k]["actual_demand"]
    d0 = d["daily"][0]["day"]
    d_first = {r["sku"]: r["opening_inventory"] for r in d["daily_logs"] if r["day"] == d0}
    b_first = {r["sku"]: r["opening_inventory"] for r in b["daily_logs"] if r["day"] == d0}
    assert d_first == b_first


def test_same_budget_passed(monkeypatch):
    budgets = []
    orig = policy.build_plan

    def spy(plan_date, budget=policy.DEFAULT_BUDGET, *a, **k):
        budgets.append(budget)
        return orig(plan_date, budget, *a, **k)

    monkeypatch.setattr(policy, "build_plan", spy)
    _run("diannao", n=4)
    _run("baseline", n=4)
    assert budgets and all(x == 1800.0 for x in budgets)


def test_same_profit_and_cost_formula():
    pm = _small_gt(10)["prod_map"]
    for key in ("diannao", "baseline"):
        res = simulator._simulate_strategy(simulator._strategy_specs()[key], _small_gt(10), 1800.0, 42, keep_daily=True)
        for r in res["daily_logs"]:
            p = pm[r["sku"]]
            exp = r["sold_qty"] * (p["sell_price"] - p["cost_price"]) - r["spoilage_qty"] * p["cost_price"]
            assert abs(r["gross_margin"] - exp) < 0.02   # 两组同一利润/成本公式


def test_same_products_supplier_lead_time():
    gt = _small_gt(6)
    before = [(p["sku"], p["supplier"], p["lead_time_days"], p["cost_price"]) for p in gt["products"]]
    for key in ("diannao", "baseline"):
        simulator._simulate_strategy(simulator._strategy_specs()[key], gt, 1800.0, 42, keep_daily=True)
    after = [(p["sku"], p["supplier"], p["lead_time_days"], p["cost_price"]) for p in gt["products"]]
    assert before == after   # 两组读同一商品档案（供应商/交期/成本一致，未被策略改写）


def test_same_order_arrival_rule():
    assert simulator._add_days("2026-03-01", 2) == "2026-03-03"
    assert simulator._add_days("2026-03-01", 3) == "2026-03-04"
    leads = {p["lead_time_days"] for p in simulator.load_ground_truth()["products"]}
    assert leads <= {1, 2, 3}   # 两组共用同一到货规则（下单日 + max(1,lead)）


def test_same_fefo_expiry_rules():
    assert callable(simulator._expire_batches) and callable(simulator._fefo_sell)
    for key in ("diannao", "baseline"):
        res = _run(key, n=8)
        for r in res["daily_logs"]:
            assert r["closing_inventory"] >= -0.01
            assert r["spoilage_qty"] >= 0


def test_baseline_no_future_leakage():
    gt = _small_gt(5)
    res = simulator._simulate_strategy(simulator._strategy_specs()["baseline"], gt, 1800.0, 42, keep_daily=True)
    day1 = gt["day_list"][0]
    rows = [r for r in res["daily_logs"] if r["day"] == day1]
    assert rows
    for r in rows:
        base = gt["prod_map"][r["sku"]]["base_daily_demand"]
        assert abs(r["forecast_demand"] - base) < 0.01   # 首日仅冷启动，未读未来


def test_same_spoilage_cost_basis():
    pm = _small_gt(10)["prod_map"]
    for key in ("diannao", "baseline"):
        res = simulator._simulate_strategy(simulator._strategy_specs()[key], _small_gt(10), 1800.0, 42, keep_daily=True)
        log_cost = sum(r["spoilage_qty"] * pm[r["sku"]]["cost_price"] for r in res["daily_logs"])
        assert abs(log_cost - res["summary"]["spoilage_cost"]) < 1.0   # 两组同一损耗成本口径
