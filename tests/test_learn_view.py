# -*- coding: utf-8 -*-
# 第12.3.1步：「它学会了什么」空状态与学习证据展示测试（不写库，仅 monkeypatch）。
from core import learn_view, memory


def _mk(monkeypatch, exps, evo):
    monkeypatch.setattr(memory, 'get_experiences', lambda limit=200: exps)
    monkeypatch.setattr(memory, 'get_evolution_log', lambda limit=1000: evo)
    monkeypatch.setattr(memory, 'get_products', lambda *a, **k: [{'sku': 'P006', 'name': '牛奶'}])
    return learn_view


def test_empty_state_is_productized(monkeypatch):
    lv = _mk(monkeypatch, [], [])
    h = lv.render_learn_page()
    assert '还没有形成经营经验' in h
    assert 'lx-exp' not in h


def test_records_path_uses_real_data(monkeypatch):
    exps = [{'day': '2026-07-10', 'sku': 'P006', 'signal': '断货',
             'qty_sold': 8.0, 'qty_stockout': 3.0, 'qty_spoilage': 0.0,
             'lesson': '牛奶备货不足'}]
    evo = [{'day': '2026-07-10', 'sku': 'P006', 'old_value': 0.15, 'new_value': 0.17}]
    lv = _mk(monkeypatch, exps, evo)
    h = lv.render_learn_page()
    assert '最近学到的经营经验' in h
    assert 'lx-exp' in h and '牛奶备货不足' in h and '上调' in h
