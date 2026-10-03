# -*- coding: utf-8 -*-
# 第5.2步：Memory 持久化 / 去重 / UI 一致性测试。
# 覆盖：写入→重启仍在 / 恢复后仍影响决策 / 重复反馈不重复学习 /
#       UI 与算法同源 / 隔离环境不读旧记忆 / reset 清空。

import sqlite3

import pytest

from core import evolution, learn_view, memory, policy


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


def test_memory_persists_across_restart(db):
    ctx = {"L1": {"forecast_qty": 5.0, "reorder_qty": 10.0}}
    evolution.process_feedback("2026-07-10", [_fb("L1", sold=5, stockout=5, spoilage=0)], plan_context=ctx)
    # 模拟重启：直接新开 sqlite 连接读文件（不经过任何 Python 内存）
    conn = sqlite3.connect(memory.DB_PATH)
    conn.row_factory = sqlite3.Row
    n = conn.execute("SELECT COUNT(*) FROM experiences").fetchone()[0]
    uid = conn.execute("SELECT uid FROM experiences WHERE sku='L1'").fetchone()[0]
    conn.close()
    assert n == 1
    assert uid  # 稳定唯一标识已落库
    assert memory.get_experiences()[0]["sku"] == "L1"


def test_recovered_memory_affects_decision(db, monkeypatch):
    ctx = {"L1": {"forecast_qty": 5.0, "reorder_qty": 10.0}}
    evolution.process_feedback("2026-07-10", [_fb("L1", sold=5, stockout=5, spoilage=0)], plan_context=ctx)
    # 重新读取（等价于重启后进程）：决策仍读到该经验并上调
    items = _prepare(monkeypatch, use_memory=True)
    assert items["L1"]["memory_adjustment_factor"] > 1.0


def test_duplicate_feedback_single_learning(db):
    day = "2026-07-10"
    ctx = {"L1": {"forecast_qty": 5.0, "reorder_qty": 10.0}}
    for _ in range(3):
        evolution.process_feedback(day, [_fb("L1", sold=5, stockout=5, spoilage=0)], plan_context=ctx)
    assert len(memory.get_experiences()) == 1
    assert len(memory.get_feedback_log()) == 1
    assert len(memory.get_evolution_log()) == 1


def test_ui_reads_same_memory_as_algorithm(db):
    pytest.importorskip("gradio")
    import app
    ctx = {"L1": {"forecast_qty": 5.0, "reorder_qty": 10.0}}
    evolution.process_feedback("2026-07-10", [_fb("L1", sold=5, stockout=5, spoilage=0)], plan_context=ctx)
    html = learn_view.render_learn_page()
    assert "大米" in html and "2026-07-10" in html           # 真实经验出现在 UI
    assert "大米" in app.render_memory_html()                # 老账本读同一来源
    assert policy.memory_safety_calibration([], as_of="2026-07-14")["L1"]["delta"] > 0


def test_isolated_env_has_no_old_memory(db):
    # db fixture 指向全新临时库：不得偷偷读到任何旧实验的 Memory
    assert memory.get_experiences() == []
    assert memory.get_feedback_log() == []
    assert memory.get_evolution_log() == []
    assert policy.memory_safety_calibration([]) == {}


def test_reset_clears_memory(db):
    ctx = {"L1": {"forecast_qty": 5.0, "reorder_qty": 10.0}}
    evolution.process_feedback("2026-07-10", [_fb("L1", sold=5, stockout=5, spoilage=0)], plan_context=ctx)
    assert memory.get_experiences()
    memory.reset_all()
    assert memory.get_experiences() == []
    assert memory.get_feedback_log() == []
    assert policy.memory_safety_calibration([]) == {}
