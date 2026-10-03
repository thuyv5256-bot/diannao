# -*- coding: utf-8 -*-
"""R³-Stock 多目标整数优化（core/r3_optimizer.py）的模型正确性测试。

用合成商品直接调用求解器，验证硬约束与目标语义；scipy 未安装时整模块跳过，
不影响其它测试与比赛现场的贪心回退路径。
"""

import pytest

pytest.importorskip("scipy.optimize")

from core import r3_optimizer


def _item(sku="A", is_livelihood=1, cost_price=10.0, sell_price=15.0, pack_size=1,
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


def test_available():
    assert r3_optimizer.available() is True


def test_never_exceeds_budget_and_integer_packs():
    base = [
        _item("A", is_livelihood=1, cost_price=8.0, sell_price=12.0, pack_size=4,
              raw_reorder=40.0, floor_qty=12.0, target_stock=40.0),
        _item("B", is_livelihood=0, cost_price=5.0, sell_price=9.0, pack_size=2,
              raw_reorder=30.0, target_stock=30.0),
        _item("C", is_livelihood=0, cost_price=3.0, sell_price=8.0, pack_size=1,
              raw_reorder=20.0, target_stock=20.0),
    ]
    for budget in (0, 10, 100, 500):
        items = [dict(it) for it in base]
        meta = r3_optimizer.solve(items, budget, protect_livelihood=True)
        assert meta["solver"]["status"] == "Optimal"
        total = sum(it["cost"] for it in items)
        assert total <= budget + 1e-6
        for it in items:
            assert it["reorder_qty"] >= 0
            assert it["reorder_qty"] % it["pack_size"] == 0  # 整包
            assert it["reorder_qty"] <= it["raw_reorder"] + 1e-9  # 不超过理想量


def test_livelihood_floor_secured_when_affordable():
    items = [
        _item("L", is_livelihood=1, cost_price=10.0, sell_price=13.0,
              raw_reorder=10.0, floor_qty=3.0, traffic_pull=2.0, unit_margin=3.0),
        _item("N", is_livelihood=0, cost_price=10.0, sell_price=50.0,
              raw_reorder=10.0, floor_qty=0.0, unit_margin=40.0),
    ]
    # 预算 30 正好够民生兜底（3×10），不够全量；高毛利 N 不应挤掉民生兜底
    meta = r3_optimizer.solve(items, budget=30.0, protect_livelihood=True)
    assert items[0]["reorder_qty"] >= items[0]["floor_qty"]
    assert items[0]["floor_secured"] is True
    assert items[1]["reorder_qty"] == 0


def test_budget_sufficient_does_not_waste():
    items = [_item("A", is_livelihood=1, cost_price=10.0, sell_price=15.0,
                   raw_reorder=10.0, floor_qty=3.0, target_stock=10.0)]
    meta = r3_optimizer.solve(items, budget=1000.0, protect_livelihood=True)
    # 理想需求只要 100，预算 1000 不应为了花完钱而多买
    assert items[0]["reorder_qty"] == items[0]["raw_reorder"]
    assert meta["overflow"] > 0


def test_outage_item_zero():
    items = [
        _item("D", is_livelihood=1, cost_price=10.0, sell_price=15.0,
              raw_reorder=0.0, floor_qty=0.0, target_stock=0.0),
        _item("E", is_livelihood=0, cost_price=5.0, sell_price=9.0,
              raw_reorder=10.0, target_stock=10.0),
    ]
    meta = r3_optimizer.solve(items, budget=100.0, protect_livelihood=True)
    assert items[0]["reorder_qty"] == 0
    assert meta["solver"]["status"] == "Optimal"
