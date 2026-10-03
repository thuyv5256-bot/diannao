# -*- coding: utf-8 -*-
"""基于经营反馈的策略自适应（在线策略校准）的防震荡行为测试。"""

from pytest import approx

from core import evolution, memory, policy
from core.config import (
    MEMORY_SAFETY_MAX_DELTA,
    SAFETY_FACTOR_MAX,
    SAFETY_FACTOR_MIN,
)


def _fb(sku, sold, stockout, spoilage):
    return {"sku": sku, "qty_sold": sold, "qty_stockout": stockout,
            "qty_spoilage": spoilage, "is_promo": 0, "is_holiday": 0}


def test_clamp():
    assert evolution._clamp(5, 0, 1) == 1
    assert evolution._clamp(-1, 0, 1) == 0
    assert evolution._clamp(0.5, 0, 1) == 0.5


def test_base_days_floor_and_ceiling():
    assert evolution._base_days_floor({"is_livelihood": 1, "shelf_life_days": 180}) == 4.0
    assert evolution._base_days_floor({"is_livelihood": 0, "shelf_life_days": 180}) == 2.0
    assert evolution._base_days_floor({"is_livelihood": 1, "shelf_life_days": 3}) == 3.0
    assert evolution._base_days_ceiling({"shelf_life_days": 3}) == approx(2.1)
    assert evolution._base_days_ceiling({"shelf_life_days": 365}) == 12.0


def test_stockout_creates_experience(db):
    evolution.process_feedback("2026-01-01", [_fb("L1", sold=5, stockout=5, spoilage=0)])
    exps = memory.get_experiences()
    assert any(e["sku"] == "L1" and e["signal"] == "断货" for e in exps)


def test_stockout_raises_calibration(db):
    # 基础策略参数保持不动……
    ctx = {"L1": {"forecast_qty": 5.0, "reorder_qty": 10.0}}   # 预测 5、实际需求 10
    evolution.process_feedback("2026-01-01", [_fb("L1", sold=5, stockout=5, spoilage=0)], plan_context=ctx)
    assert memory.get_policy("L1")["safety_factor"] == 0.15
    # ……但下一次同类场景（普通日）会读到经验，上调安全系数
    cal = policy.memory_safety_calibration([])
    assert cal["L1"]["delta"] > 0
    assert cal["L1"]["factor"] > 1.0


def test_spoilage_lowers_calibration(db):
    ctx = {"N1": {"forecast_qty": 20.0, "reorder_qty": 20.0}}  # 预测 20、实际需求 10 → 预测偏高
    evolution.process_feedback("2026-01-01", [_fb("N1", sold=10, stockout=0, spoilage=3)], plan_context=ctx)
    cal = policy.memory_safety_calibration([])
    assert cal["N1"]["delta"] < 0


def test_stockout_and_spoilage_only_stockout(db):
    # 同一天既断货又损耗 → 只按断货沉淀经验，校准方向向上（避免自我抵消）
    ctx = {"L1": {"forecast_qty": 4.0, "reorder_qty": 8.0}}
    evolution.process_feedback("2026-01-01", [_fb("L1", sold=4, stockout=4, spoilage=2)], plan_context=ctx)
    exps = [e for e in memory.get_experiences() if e["sku"] == "L1"]
    assert exps and all(e["signal"] == "断货" for e in exps)
    assert policy.memory_safety_calibration([])["L1"]["delta"] > 0


def test_small_noise_does_not_trigger(db):
    # 缺货率未超过阈值：不沉淀经验，也不产生校准
    evolution.process_feedback("2026-01-01", [_fb("L1", sold=9, stockout=1, spoilage=0)])
    assert memory.get_experiences() == []
    assert policy.memory_safety_calibration([]) == {}


def test_calibration_delta_capped(db):
    # 多次同类断货经验累加，也不得超过单商品累计最大幅度
    ctx = {"L1": {"forecast_qty": 5.0, "reorder_qty": 10.0}}
    for _ in range(5):
        evolution.process_feedback("2026-01-01", [_fb("L1", sold=5, stockout=5, spoilage=0)], plan_context=ctx)
    delta = policy.memory_safety_calibration([])["L1"]["delta"]
    assert delta <= MEMORY_SAFETY_MAX_DELTA + 1e-9


def test_effective_safety_bounded(db):
    memory.set_policy("L1", 5.0, 0.59)
    ctx = {"L1": {"forecast_qty": 1.0, "reorder_qty": 10.0}}
    evolution.process_feedback("2026-01-01", [_fb("L1", sold=1, stockout=9, spoilage=0)], plan_context=ctx)
    base = memory.get_policy("L1")["safety_factor"]
    delta = policy.memory_safety_calibration([])["L1"]["delta"]
    effective = max(SAFETY_FACTOR_MIN, min(SAFETY_FACTOR_MAX, base + delta))
    assert effective <= SAFETY_FACTOR_MAX


def test_duplicate_feedback_not_relearned(db):
    # 同一「日期 + SKU + 销量/断货/报损」完全一致的反馈只学习一次
    day = "2026-01-01"
    ctx = {"L1": {"forecast_qty": 5.0, "reorder_qty": 10.0}}
    r1 = evolution.process_feedback(day, [_fb("L1", sold=5, stockout=5, spoilage=0)], plan_context=ctx)
    assert r1["summary"]["skipped"] == 0
    assert len(r1["changes"]) == 1

    r2 = evolution.process_feedback(day, [_fb("L1", sold=5, stockout=5, spoilage=0)], plan_context=ctx)
    assert r2["summary"]["skipped"] == 1
    assert r2["changes"] == []  # 不再重复调整策略
    # 经验与进化轨迹都只保留一条
    assert len([e for e in memory.get_experiences() if e["sku"] == "L1"]) == 1
    assert len(memory.get_evolution_log()) == 1
    assert policy.memory_safety_calibration([])["L1"]["delta"] == approx(0.06)


def test_correction_updates_without_accumulating(db):
    # 数据修正（断货量 5 → 8）应覆盖更新原经验，而不是再累计一条
    day = "2026-01-01"
    ctx = {"L1": {"forecast_qty": 5.0, "reorder_qty": 10.0}}
    evolution.process_feedback(day, [_fb("L1", sold=5, stockout=5, spoilage=0)], plan_context=ctx)
    r = evolution.process_feedback(day, [_fb("L1", sold=5, stockout=8, spoilage=0)], plan_context=ctx)
    assert r["summary"]["updated"] == 1
    assert r["summary"]["skipped"] == 0
    exps = [e for e in memory.get_experiences() if e["sku"] == "L1"]
    assert len(exps) == 1
    assert exps[0]["qty_stockout"] == 8.0
    assert len(memory.get_evolution_log()) == 1
    assert policy.memory_safety_calibration([])["L1"]["delta"] == approx(0.06)
