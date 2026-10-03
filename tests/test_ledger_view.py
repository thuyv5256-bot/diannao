# -*- coding: utf-8 -*-
# 第12.4步：「店里的老账本」展示层测试（只读真实数据）。
from core import ledger_view


def test_ledger_renders_compact_summary_not_kpi():
    h = ledger_view.render_ledger()
    assert 'lv-sum' in h and 'kpi-row' not in h
    assert '过去发生过什么' in h
    assert '商品经营档案' in h
    assert '老账本负责记住发生过什么' in h


def test_ledger_uses_real_events_and_suppliers():
    h = ledger_view.render_ledger()
    assert '供应商与到货时间' in h
