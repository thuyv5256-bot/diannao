# -*- coding: utf-8 -*-
# 「店里的老账本」展示层测试（只读真实数据，UI v2）。
from core import ledger_view


def test_ledger_uses_compact_summary_not_kpi():
    h = ledger_view.render_ledger()
    # 顶部紧凑 summary row，不是四张巨大 KPI 卡
    assert 'lb-sum' in h and 'kpi-row' not in h
    # 顶部四项统计：经营记录 · 商品档案 · 民生商品 · 历史事件
    assert '天经营记录' in h and '种商品档案' in h and '种民生商品' in h and '类历史事件' in h


def test_ledger_sections_present_and_real_data():
    h = ledger_view.render_ledger()
    assert '店里的老账本' in h
    # 五个 section 都在
    assert '经营记录' in h
    assert '历史经营事件' in h
    assert '商品档案' in h
    assert '供应与到货' in h
    assert '经营经验' in h
    # 真实历史事件 / 供应商数据已渲染
    assert '高温' in h and '供应商D断供' in h
    assert '供应商A' in h


def test_ledger_experiences_empty_state_is_real():
    # demo-store 当前 experiences = 0 → 真实空状态，不引用 FINAL 实验经验
    h = ledger_view.render_ledger()
    assert '还没有形成经营经验' in h
    assert '739' not in h  # 严禁引用 FINAL 实验数据


def test_ledger_secondary_fields_in_accordion():
    h = ledger_view.render_ledger()
    # 次级技术字段（供应商 / 到货时间 / 断货损耗明细）收进展开区域，而非铺满
    assert '查看完整商品字段' in h
    assert 'xm-acc' in h
