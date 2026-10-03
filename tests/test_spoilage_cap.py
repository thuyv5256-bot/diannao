# -*- coding: utf-8 -*-
# 第4.2步：短保商品损耗风险控制（FEFO 可售容量采购上限）回归测试。
# 覆盖 A~F 场景 + 纯函数交期/FEFO 行为 + MILP 尊重采购上限。
import pytest

from core import policy


def _product(sku="P1", is_livelihood=0, lead_time_days=2, pack_size=1,
             shelf_life_days=3.0, cost_price=5.0, sell_price=8.0):
    return {
        "sku": sku, "name": sku, "category": "乳品", "supplier": "供应商A",
        "is_livelihood": int(is_livelihood), "unit": "件",
        "cost_price": cost_price, "sell_price": sell_price, "pack_size": pack_size,
        "shelf_life_days": shelf_life_days, "lead_time_days": lead_time_days,
        "traffic_pull": 1.0, "base_daily_demand": 10.0,
    }


def _prepare(monkeypatch, products, on_hand, batches_map=None, entries_map=None, plan_date='2026-07-14', daily=10.0):
    fc = {p['sku']: {'daily_demand': daily, 'risk_factor': 1.0, 'holiday_note': '', 'risk_note': '', 'promo_note': ''} for p in products}
    monkeypatch.setattr(policy.forecast, 'forecast_all', lambda *a, **k: fc)
    monkeypatch.setattr(policy.memory, 'get_inventory', lambda: dict(on_hand))
    policies = {p['sku']: {'base_days': 3.0, 'safety_factor': 0.15} for p in products}
    items, _meta = policy._prepare_items(plan_date, policies, products, risks=[], use_memory=False, in_transit_map=entries_map, on_hand_batches=batches_map)
    return items


def test_free_capacity_late_transit_ignored():
    cap = policy._free_sellable_capacity([], [('2026-07-25', 100.0)], '2026-07-14', 10.0, 2, 3)
    assert cap == 30.0


def test_free_capacity_batch_age_matters():
    early = policy._free_sellable_capacity([(1, 50.0)], [], '2026-07-14', 10.0, 2, 5)
    late = policy._free_sellable_capacity([(5, 50.0)], [], '2026-07-14', 10.0, 2, 5)
    assert early > late


def test_scenario_A_short_shelf_high_stock_limits_order(monkeypatch):
    products = [_product(shelf_life_days=3.0, lead_time_days=2)]
    items = _prepare(monkeypatch, products, on_hand={'P1': 50.0}, batches_map={'P1': [(3, 50.0)]})
    assert items[0]['raw_reorder'] == 0.0


def test_scenario_B_short_shelf_low_stock_allows_order(monkeypatch):
    products = [_product(shelf_life_days=3.0, lead_time_days=2)]
    items = _prepare(monkeypatch, products, on_hand={})
    assert items[0]['raw_reorder'] > 0.0


def test_scenario_D_timely_in_transit_no_duplicate(monkeypatch):
    products = [_product(shelf_life_days=3.0, lead_time_days=2)]
    items = _prepare(monkeypatch, products, on_hand={}, entries_map={'P1': [('2026-07-15', 30.0)]})
    assert items[0]['eligible_in_transit'] == 30.0
    assert items[0]['raw_reorder'] == 5.0


def test_scenario_C_large_near_expiry_limits_order(monkeypatch):
    products = [_product(shelf_life_days=3.0, lead_time_days=2)]
    items = _prepare(monkeypatch, products, on_hand={'P1': 30.0}, batches_map={'P1': [(1, 30.0)]}, daily=2.0)
    assert items[0]['raw_reorder'] == 0.0


def test_scenario_E_late_in_transit_not_effective(monkeypatch):
    products = [_product(shelf_life_days=3.0, lead_time_days=2)]
    items = _prepare(monkeypatch, products, on_hand={}, entries_map={'P1': [('2026-07-25', 30.0)]})
    assert items[0]['eligible_in_transit'] == 0.0
    assert items[0]['raw_reorder'] > 5.0


def test_scenario_F_livelihood_floor_preserved(monkeypatch):
    products = [_product(shelf_life_days=1.0, lead_time_days=2, is_livelihood=1)]
    items = _prepare(monkeypatch, products, on_hand={})
    it = items[0]
    assert it['free_sellable_capacity'] < it['floor_qty']
    assert it['raw_reorder'] >= it['floor_qty']


def test_cap_binds_trims_safety_overflow(monkeypatch):
    products = [_product(shelf_life_days=3.0, lead_time_days=2)]
    items = _prepare(monkeypatch, products, on_hand={})
    it = items[0]
    assert it['raw_reorder_uncapped'] == 35.0
    assert it['raw_reorder'] == 30.0
    assert it['spoilage_capped'] is True
    assert it['expected_excess_qty'] == 5.0
    assert it['expected_spoilage_cost'] == 25.0


def test_long_shelf_life_no_cap(monkeypatch):
    products = [_product(shelf_life_days=365.0, lead_time_days=2)]
    items = _prepare(monkeypatch, products, on_hand={})
    it = items[0]
    assert it['spoilage_capped'] is False
    assert it['expected_spoilage_cost'] == 0.0
    assert it['raw_reorder'] == 35.0


def test_batch_age_changes_spoilage_risk(monkeypatch):
    products = [_product(shelf_life_days=5.0, lead_time_days=2)]
    early = _prepare(monkeypatch, products, on_hand={'P1': 34.0}, batches_map={'P1': [(1, 34.0)]})
    late = _prepare(monkeypatch, products, on_hand={'P1': 34.0}, batches_map={'P1': [(5, 34.0)]})
    assert early[0]['free_sellable_capacity'] > late[0]['free_sellable_capacity']


def test_milp_respects_spoilage_cap(monkeypatch):
    pytest.importorskip('scipy.optimize')
    from core import r3_optimizer
    products = [_product(shelf_life_days=3.0, lead_time_days=2)]
    items = _prepare(monkeypatch, products, on_hand={})
    for it in items:
        it['need_qty'] = it['raw_reorder']
    r3_optimizer.solve(items, budget=1000.0, protect_livelihood=True)
    assert items[0]['reorder_qty'] <= items[0]['raw_reorder'] + 1e-9
