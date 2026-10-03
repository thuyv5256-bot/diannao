# -*- coding: utf-8 -*-
"""补货分配核心（_allocate 三层惠民约束）的边界测试。"""

from core import policy


def _item(sku="A", is_livelihood=1, cost_price=10.0, pack_size=1,
          raw_reorder=10.0, floor_qty=3.0, need_qty=10.0, capital_eff=1.0,
          traffic_pull=1.0):
    return {
        "sku": sku, "name": sku, "category": "x", "unit": "件",
        "is_livelihood": is_livelihood,
        "cost_price": cost_price, "sell_price": cost_price * 1.5,
        "pack_size": pack_size, "shelf_life_days": 365,
        "traffic_pull": traffic_pull,
        "daily_demand": 1.0, "base_days": 3.0, "safety_factor": 0.15,
        "target_cover_days": 3.0, "floor_days": 3.0,
        "holiday_note": "", "promo_note": "",
        "target_stock": 10.0, "on_hand": 0.0, "need_qty": need_qty,
        "raw_reorder": raw_reorder,
        "raw_cost": round(raw_reorder * cost_price, 2),
        "floor_qty": floor_qty,
        "floor_cost": round(floor_qty * cost_price, 2),
        "unit_margin": cost_price * 0.5,
        "capital_eff": capital_eff,
    }


def test_ceil_to_pack():
    assert policy._ceil_to_pack(0, 4) == 0
    assert policy._ceil_to_pack(1, 4) == 4
    assert policy._ceil_to_pack(4, 4) == 4
    assert policy._ceil_to_pack(5, 4) == 8
    assert policy._ceil_to_pack(3, 1) == 3


def test_floor_to_pack():
    assert policy._floor_to_pack(10, 3, 1) == 3
    assert policy._floor_to_pack(10, 3, 4) == 0
    assert policy._floor_to_pack(50, 10, 4) == 4
    assert policy._floor_to_pack(0, 3, 1) == 0
    assert policy._floor_to_pack(100, 0, 1) == 0


def test_allocate_zero_budget():
    items = [_item(sku="L", is_livelihood=1)]
    policy._allocate(items, budget=0.0, protect_livelihood=True)
    assert all(it["reorder_qty"] == 0 for it in items)
    assert all(it["cost"] == 0 for it in items)


def test_allocate_never_exceeds_budget():
    base = [
        _item(sku="L", is_livelihood=1, capital_eff=0.5, traffic_pull=1.8),
        _item(sku="N", is_livelihood=0, capital_eff=2.0, traffic_pull=1.0),
    ]
    for budget in [0, 1, 30, 100, 500]:
        for protect in (True, False):
            items = [dict(it) for it in base]
            policy._allocate(items, budget, protect_livelihood=protect)
            assert sum(it["cost"] for it in items) <= budget + 1e-6


def test_allocate_protects_livelihood_floor():
    base = [
        _item(sku="L", is_livelihood=1, capital_eff=0.1, traffic_pull=1.8),
        _item(sku="N", is_livelihood=0, capital_eff=10.0, traffic_pull=1.0),
    ]
    # 预算只够民生兜底（30），不够全量（200）
    items = [dict(it) for it in base]
    policy._allocate(items, budget=30.0, protect_livelihood=True)
    assert items[0]["floor_secured"] is True
    assert items[0]["reorder_qty"] == items[0]["floor_qty"] == 3
    assert items[1]["reorder_qty"] == 0

    # baseline 不兜底：按资金效率排序，高毛利的 N 先拿货
    items2 = [dict(it) for it in base]
    policy._allocate(items2, budget=30.0, protect_livelihood=False)
    assert items2[0]["floor_secured"] is None
    assert items2[1]["reorder_qty"] > 0
