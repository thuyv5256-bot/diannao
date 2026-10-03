# -*- coding: utf-8 -*-
# 第5.1步：Memory 误差学习闭环测试。
# 覆盖：预测偏低→补货变化 / 无经验→不影响 / 重复提交→不重学 /
#       不无限放大 / 无未来泄漏 / 事件已解释的误差不重学。

from pytest import approx

from core import evolution, memory, policy
from core.config import MEMORY_SAFETY_MAX_DELTA


def _fb(sku, sold, stockout, spoilage):
    return {"sku": sku, "qty_sold": sold, "qty_stockout": stockout,
            "qty_spoilage": spoilage, "is_promo": 0, "is_holiday": 0}


def _prepare(monkeypatch, plan_date="2026-07-14", use_memory=True):
    products = memory.get_products()
    policies = memory.get_all_policy()
    fc = {p["sku"]: {"daily_demand": 10.0, "risk_factor": 1.0, "holiday_note": "", "risk_note": "", "promo_note": ""} for p in products}
    monkeypatch.setattr(policy.forecast, "forecast_all", lambda *a, **k: fc)
    monkeypatch.setattr(policy.memory, "get_inventory", lambda: {p["sku"]: 0.0 for p in products})
    items, _meta = policy._prepare_items(plan_date, policies, products, risks=[], use_memory=use_memory)
    return {it["sku"]: it for it in items}


def test_low_forecast_bias_raises_reorder(db, monkeypatch):
    # 历史：预测 5、实际需求 10 → 预测偏低 → 后续补货目标应更高
    ctx = {"L1": {"forecast_qty": 5.0, "reorder_qty": 10.0}}
    evolution.process_feedback("2026-07-10", [_fb("L1", sold=5, stockout=5, spoilage=0)], plan_context=ctx)
    with_mem = _prepare(monkeypatch, use_memory=True)
    without = _prepare(monkeypatch, use_memory=False)
    assert with_mem["L1"]["memory_adjustment_factor"] > 1.0
    assert with_mem["L1"]["target_stock"] > without["L1"]["target_stock"]


def test_no_experience_no_effect(db, monkeypatch):
    with_mem = _prepare(monkeypatch, use_memory=True)
    without = _prepare(monkeypatch, use_memory=False)
    assert with_mem["L1"]["memory_adjustment_factor"] == 1.0
    assert with_mem["L1"]["target_stock"] == without["L1"]["target_stock"]


def test_duplicate_feedback_not_relearned(db):
    day = "2026-07-10"
    ctx = {"L1": {"forecast_qty": 5.0, "reorder_qty": 10.0}}
    evolution.process_feedback(day, [_fb("L1", sold=5, stockout=5, spoilage=0)], plan_context=ctx)
    f1 = policy.memory_safety_calibration([], as_of="2026-07-14")["L1"]["factor"]
    evolution.process_feedback(day, [_fb("L1", sold=5, stockout=5, spoilage=0)], plan_context=ctx)
    f2 = policy.memory_safety_calibration([], as_of="2026-07-14")["L1"]["factor"]
    assert f1 == f2
    assert len([e for e in memory.get_experiences() if e["sku"] == "L1"]) == 1


def test_correction_bounded_no_amplification(db):
    ctx = {"L1": {"forecast_qty": 1.0, "reorder_qty": 1.0}}
    for i in range(20):
        evolution.process_feedback(f"2026-07-{i+1:02d}", [_fb("L1", sold=1, stockout=9, spoilage=0)], plan_context=ctx)
    cal = policy.memory_safety_calibration([], as_of="2026-08-01")
    assert abs(cal["L1"]["delta"]) <= MEMORY_SAFETY_MAX_DELTA + 1e-9
    assert 1.0 - MEMORY_SAFETY_MAX_DELTA <= cal["L1"]["factor"] <= 1.0 + MEMORY_SAFETY_MAX_DELTA


def test_no_future_leak(db):
    ctx = {"L1": {"forecast_qty": 5.0, "reorder_qty": 10.0}}
    evolution.process_feedback("2026-07-20", [_fb("L1", sold=5, stockout=5, spoilage=0)], plan_context=ctx)
    # 决策日 2026-07-15 早于经验日 → 读不到（不泄漏未来）
    assert "L1" not in policy.memory_safety_calibration([], as_of="2026-07-15")
    # 决策日 2026-07-21 晚于经验日 → 可读到
    assert policy.memory_safety_calibration([], as_of="2026-07-21")["L1"]["delta"] > 0


def test_event_explained_error_not_relearned(db):
    # 断货确实发生，但潜在需求(8+2=10) = 原预测(10) → 残差 0
    # → Memory 不重复学习 Event/Forecast 已解释掉的部分，校准为 0
    ctx = {"L1": {"forecast_qty": 10.0, "reorder_qty": 10.0}}
    evolution.process_feedback("2026-07-10", [_fb("L1", sold=8, stockout=2, spoilage=0)], plan_context=ctx)
    assert memory.get_experiences()  # 经验已沉淀（存在断货信号）
    cal = policy.memory_safety_calibration([], as_of="2026-07-14")
    assert cal.get("L1", {}).get("delta", 0.0) == approx(0.0)
