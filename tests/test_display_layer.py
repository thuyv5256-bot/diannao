# -*- coding: utf-8 -*-
# 第10.1/10.2 展示层测试：渲染不得改变 order_qty（同一输入前后一致）。
from conftest import require_app

from core import decision_basis, policy


def _plan():
    return policy.build_plan("2026-07-14", 600.0, policy.MODE_DIANNAO, persist=False)


def test_render_plan_does_not_change_order_qty(db):
    app = require_app()   # 缺 gradio/plotly 时 skip，而不是失败
    plan = _plan()
    before = {it["sku"]: it["reorder_qty"] for it in plan["items"]}
    app.render_plan_html(plan)
    after = {it["sku"]: it["reorder_qty"] for it in plan["items"]}
    assert before == after


def test_decision_basis_does_not_change_item(db):
    plan = _plan()
    it = plan["items"][0]
    before_qty = it["reorder_qty"]
    before_on_hand = it["on_hand"]
    decision_basis.render_reorder_basis(it)
    assert it["reorder_qty"] == before_qty
    assert it["on_hand"] == before_on_hand
