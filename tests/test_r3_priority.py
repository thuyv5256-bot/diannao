# -*- coding: utf-8 -*-
# 第6.1步：R³ 约束优先级与预算不足逻辑测试。
# 覆盖：预算充足→民生底线满足 / 预算刚好=民生底线→不超预算 / 预算不足→不超预算且<100% /
#       缺口金额正确 / 高利润非民生不能挤掉民生 / SKU顺序无关。

import copy

import pytest

from core import policy
from core import r3_optimizer


def _item(sku, is_livelihood=1, cost_price=10.0, sell_price=15.0, pack_size=1,
          raw_reorder=10.0, floor_qty=3.0, target_stock=10.0, on_hand=0.0,
          need_qty=10.0, traffic_pull=1.0, unit_margin=None):
    return {
        "sku": sku, "name": sku, "category": "x", "unit": "件",
        "is_livelihood": is_livelihood,
        "cost_price": cost_price, "sell_price": sell_price,
        "pack_size": pack_size, "shelf_life_days": 365,
        "traffic_pull": traffic_pull,
        "daily_demand": 1.0, "base_days": 3.0, "safety_factor": 0.15,
        "target_cover_days": 3.0, "floor_days": 3.0,
        "target_stock": target_stock, "on_hand": on_hand, "need_qty": need_qty,
        "raw_reorder": raw_reorder,
        "raw_cost": round(raw_reorder * cost_price, 2),
        "floor_qty": floor_qty,
        "floor_cost": round(floor_qty * cost_price, 2),
        "unit_margin": unit_margin if unit_margin is not None else round(sell_price - cost_price, 2),
        "capital_eff": round((sell_price - cost_price) / cost_price, 4),
    }


def _solve(base, budget):
    items = [copy.deepcopy(it) for it in base]
    meta = r3_optimizer.solve(items, budget, protect_livelihood=True)
    return items, meta


def _greedy(base, budget):
    items = [copy.deepcopy(it) for it in base]
    policy._allocate(items, budget, protect_livelihood=True)
    return items


def test_sufficient_budget_secures_floor():
    pytest.importorskip("scipy.optimize")
    base = [_item("L1", is_livelihood=1, cost_price=10.0, floor_qty=5.0, raw_reorder=20.0),
            _item("L2", is_livelihood=1, cost_price=10.0, floor_qty=3.0, raw_reorder=15.0)]
    items, meta = _solve(base, 1000.0)
    assert all(it["reorder_qty"] >= it["floor_qty"] - 1e-9 for it in items)
    assert meta["livelihood_floor_secured"] == 1.0


def test_budget_equals_floor_no_overspend():
    pytest.importorskip("scipy.optimize")
    base = [_item("L1", is_livelihood=1, cost_price=10.0, floor_qty=5.0, raw_reorder=20.0),
            _item("L2", is_livelihood=1, cost_price=10.0, floor_qty=3.0, raw_reorder=15.0)]
    items, meta = _solve(base, 80.0)   # 民生底线总花费 = 5×10 + 3×10 = 80
    assert sum(it["cost"] for it in items) <= 80.0 + 1e-6
    assert all(it["reorder_qty"] >= it["floor_qty"] - 1e-9 for it in items)
    assert meta["livelihood_floor_secured"] == 1.0


def test_insufficient_budget_not_overspend_and_rate_below_100():
    pytest.importorskip("scipy.optimize")
    base = [_item("L1", is_livelihood=1, cost_price=10.0, floor_qty=5.0, raw_reorder=20.0),
            _item("L2", is_livelihood=1, cost_price=10.0, floor_qty=5.0, raw_reorder=20.0)]
    items, meta = _solve(base, 60.0)   # 底线需 100，只给 60
    assert sum(it["cost"] for it in items) <= 60.0 + 1e-6   # 绝不超预算
    assert meta["livelihood_floor_secured"] < 1.0           # 保障率 < 100%


def test_insufficient_budget_shortfall_cost_correct():
    pytest.importorskip("scipy.optimize")
    base = [_item("L1", is_livelihood=1, cost_price=10.0, floor_qty=5.0, raw_reorder=20.0),
            _item("L2", is_livelihood=1, cost_price=10.0, floor_qty=5.0, raw_reorder=20.0)]
    items, _meta = _solve(base, 60.0)
    cov = policy.calculate_essential_coverage(items)
    expected = sum(max(0.0, it["floor_qty"] - it["reorder_qty"]) * it["cost_price"] for it in items)
    assert cov["shortfall_cost"] > 0
    assert abs(cov["shortfall_cost"] - expected) < 1e-6
    assert cov["rate"] < 1.0


def test_high_margin_non_livelihood_cannot_steal_floor_budget():
    pytest.importorskip("scipy.optimize")
    base = [_item("L", is_livelihood=1, cost_price=10.0, sell_price=13.0, floor_qty=3.0,
                  raw_reorder=10.0, traffic_pull=2.0, unit_margin=3.0),
            _item("N", is_livelihood=0, cost_price=10.0, sell_price=50.0, floor_qty=0.0,
                  raw_reorder=10.0, unit_margin=40.0)]
    items, _meta = _solve(base, 30.0)   # 恰好够民生兜底 3×10
    assert items[0]["reorder_qty"] >= 3.0
    assert items[1]["reorder_qty"] == 0.0


def test_order_independence_milp():
    pytest.importorskip("scipy.optimize")
    base = [_item("A", is_livelihood=1, cost_price=10.0, floor_qty=4.0, raw_reorder=10.0),
            _item("B", is_livelihood=1, cost_price=10.0, floor_qty=4.0, raw_reorder=10.0),
            _item("C", is_livelihood=0, cost_price=10.0, sell_price=30.0, raw_reorder=10.0)]
    i1, _ = _solve(base, 60.0)
    i2, _ = _solve(list(reversed(base)), 60.0)
    assert {it["sku"]: it["reorder_qty"] for it in i1} == {it["sku"]: it["reorder_qty"] for it in i2}


def test_order_independence_greedy():
    base = [_item("A", is_livelihood=1, cost_price=10.0, floor_qty=4.0, raw_reorder=10.0,
                  traffic_pull=1.0, need_qty=10.0),
            _item("B", is_livelihood=1, cost_price=10.0, floor_qty=4.0, raw_reorder=10.0,
                  traffic_pull=1.0, need_qty=10.0)]
    # 底线共需 80、预算 40 → 只能保 1 个；A/B 权重并列，结果必须与遍历顺序无关
    r1 = {it["sku"]: it["reorder_qty"] for it in _greedy(base, 40.0)}
    r2 = {it["sku"]: it["reorder_qty"] for it in _greedy(list(reversed(base)), 40.0)}
    assert r1 == r2
    assert sorted(r1.values()) == [0.0, 4.0]
