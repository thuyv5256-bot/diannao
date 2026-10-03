# -*- coding: utf-8 -*-
"""
在途库存「有效口径」修复的回归测试（第 3 步审计的唯一修复项）。

验证核心规则：在途库存必须按「到货日」判断是否落在对应评估窗口内，
只有窗口内能到货的「有效在途」才计入：
  · 补货需求 need / R³ 采购上界
  · R³ 韧性缺口 s_i
  · 预计缺货 / 覆盖天数
  · 民生最低保障兜底量
晚到的在途不得提前算作可用库存（不能简单把全部在途当可用）。

覆盖审计要求的 A~E 五个场景。
"""

import pytest

from core import policy, r3_optimizer


def _product(sku="P1", is_livelihood=0, lead_time_days=2, pack_size=1,
             shelf_life_days=30.0):
    return {
        "sku": sku, "name": sku, "category": "饮料", "supplier": "供应商A",
        "is_livelihood": int(is_livelihood), "unit": "件",
        "cost_price": 5.0, "sell_price": 8.0, "pack_size": pack_size,
        "shelf_life_days": shelf_life_days, "lead_time_days": lead_time_days,
        "traffic_pull": 1.0, "base_daily_demand": 10.0,
    }


def _prepare(monkeypatch, products, on_hand, entries_map, plan_date="2026-07-14"):
    """直接调用 _prepare_items（跳过求解器），可控地注入预测与库存。"""
    monkeypatch.setattr(
        policy.forecast, "forecast_all",
        lambda plan_date, restore_potential=True, risks=None: {
            p["sku"]: {"daily_demand": 10.0, "holiday_note": "",
                       "risk_note": "", "promo_note": "", "risk_factor": 1.0}
            for p in products
        })
    monkeypatch.setattr(policy.memory, "get_inventory",
                        lambda: dict(on_hand))
    policies = {p["sku"]: {"base_days": 3.0, "safety_factor": 0.15}
                for p in products}
    items, _meta = policy._prepare_items(
        plan_date, policies, products, risks=[], use_memory=False,
        in_transit_map=entries_map)
    return items


# ── 有效在途口径（纯函数边界） ──────────────────────────────
def test_eligible_in_transit_boundary():
    # 窗口 3 天 → horizon = 07-17：到货日 < 07-17 才计入
    entries = [("2026-07-15", 10.0), ("2026-07-16", 10.0),
               ("2026-07-17", 10.0), ("2026-07-18", 10.0)]
    assert policy._eligible_in_transit(entries, "2026-07-14", 3.0) == 20.0
    assert policy._eligible_in_transit(entries, "2026-07-14", 5.0) == 40.0
    assert policy._eligible_in_transit([], "2026-07-14", 3.0) == 0.0


# ── A. 已在途且及时到货：计入有效库存，不重复制造缺口 ────────
def test_timely_in_transit_is_counted(monkeypatch):
    products = [_product()]
    # 当前库存 10，在途 20 明天到（07-15），lead=2 → 覆盖窗口 3 天
    items = _prepare(monkeypatch, products, on_hand={"P1": 10.0},
                     entries_map={"P1": [("2026-07-15", 20.0)]})
    it = items[0]
    assert it["eligible_in_transit"] == 20.0
    # target_stock = 10×3 + 10×3×0.15 = 34.5；need = 34.5 − 10 − 20 = 4.5
    assert abs(it["need_qty"] - 4.5) < 0.6
    assert it["raw_reorder"] == 5.0


# ── B. 到货太晚：不得算作可用库存 ────────────────────────────
def test_late_in_transit_not_counted(monkeypatch):
    products = [_product()]
    # 在途 20 要 5 天后（07-19）才到，超出 3 天覆盖窗口
    items = _prepare(monkeypatch, products, on_hand={"P1": 10.0},
                     entries_map={"P1": [("2026-07-19", 20.0)]})
    it = items[0]
    assert it["eligible_in_transit"] == 0.0
    # 晚到的货不抵扣：need = 34.5 − 10 − 0 = 24.5 → 整件 25
    assert it["raw_reorder"] == 25.0


# ── C. 防重复采购 + R³ 韧性缺口与在途同口径 ──────────────────
def test_r3_resilience_uses_eligible_in_transit(monkeypatch):
    pytest.importorskip("scipy.optimize")
    products = [_product()]
    items = _prepare(monkeypatch, products, on_hand={"P1": 10.0},
                     entries_map={"P1": [("2026-07-15", 20.0)]})
    # 及时到货 20 后，理想补货上界 raw_reorder=5（不是 25），R³ 不得重复采购
    meta = r3_optimizer.solve(items, budget=1000.0, protect_livelihood=True)
    it = items[0]
    assert it["reorder_qty"] == 5.0          # 不超过在途调整后的理想量
    # 韧性缺口：s_i ≥ 34.5 − 10 − 20 − 5 = −0.5 → s_i = 0（有效在途已填平缺口）
    assert meta["solver"]["resilience"]["shortfall_units"] < 0.5


# ── D. 民生保障：仅在保障窗口内到货才用于满足最低保障 ────────
def test_livelihood_floor_eligible_only_within_window(monkeypatch):
    products = [_product(is_livelihood=1)]
    # 及时到货（窗口内）：在途 20 覆盖兜底 → 兜底量 0
    items = _prepare(monkeypatch, products, on_hand={"P1": 10.0},
                     entries_map={"P1": [("2026-07-15", 20.0)]})
    assert items[0]["floor_qty"] == 0.0

    # 晚到（窗口外）：在途不能算进 3 天兜底 → 兜底量 20（30 − 10）
    items2 = _prepare(monkeypatch, products, on_hand={"P1": 10.0},
                      entries_map={"P1": [("2026-07-19", 20.0)]})
    assert items2[0]["floor_qty"] == 20.0


# ── E. UI/计算口径一致：need_qty 与「目标 − 当前 − 有效在途」一致 ──
def test_need_field_matches_eligible_in_transit(monkeypatch):
    products = [_product()]
    items = _prepare(monkeypatch, products, on_hand={"P1": 10.0},
                     entries_map={"P1": [("2026-07-15", 20.0)]})
    it = items[0]
    expected = max(0.0, it["target_stock"] - it["on_hand"] - it["eligible_in_transit"])
    assert abs(it["need_qty"] - expected) < 0.6


def test_evaluate_plan_supply_uses_eligible_in_transit(monkeypatch):
    products = [_product()]

    def _eval(items):
        for it in items:
            it["reorder_qty"] = 0.0
            it["cost"] = 0.0
            it["trimmed"] = False
            it["trim_note"] = ""
            it["floor_secured"] = None
        policy.evaluate_plan(items, {"budget": 1000.0})

    # 及时到货：supply = 10 + 20 + 0 → 覆盖 3 天
    items = _prepare(monkeypatch, products, on_hand={"P1": 10.0},
                     entries_map={"P1": [("2026-07-15", 20.0)]})
    _eval(items)
    assert abs(items[0]["final_cover_days"] - 3.0) < 0.01

    # 晚到：supply = 10 + 0 + 0 → 覆盖 1 天（晚到在途不算可用）
    items2 = _prepare(monkeypatch, products, on_hand={"P1": 10.0},
                      entries_map={"P1": [("2026-07-19", 20.0)]})
    _eval(items2)
    assert abs(items2[0]["final_cover_days"] - 1.0) < 0.01
