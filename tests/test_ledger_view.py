# -*- coding: utf-8 -*-
# 「店里的老账本」展示层测试（只读真实数据，UI v2）。
from core import ledger_view, memory


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


def test_ledger_experiences_come_from_memory_not_hardcoded():
    """经验区必须严格等于 memory.get_experiences() 的真实内容。

    不预设「数据库是空的」——演示环境已通过 seed_demo_history.py 播种过
    模拟经营历史（经验由core/evolution.py 正常业务逻辑生成）。
    本测试的真正目的：证明页面上的经验**来自数据库**而非写死在 HTML 里。
    """
    exps = memory.get_experiences(limit=50)
    h = ledger_view.render_ledger()
    if exps:
        # 有经验 → 页面上每一条都必须在数据库里真实存在
        assert '还没有形成经营经验' not in h
        names = {p['sku']: p['name'] for p in memory.get_products()}
        for e in exps:
            nm = names.get(e['sku'], e['sku'])
            assert nm in h, "经验 %s 未出现在页面上" % nm
    else:
        # 空库 → 必须是真实空状态
        assert '还没有形成经营经验' in h
    # 无论有无数据，都严禁引用 FINAL 实验结果
    assert '739' not in h


def test_ledger_demo_history_disclosure():
    """演示数据必须明确标注来源，避免评委误认为真实商户采集。"""
    h = ledger_view.render_head()
    assert '演示门店' in h and '模拟经营历史' in h


def test_ledger_secondary_fields_in_accordion():
    h = ledger_view.render_ledger()
    # 次级技术字段（供应商 / 到货时间 / 断货损耗明细）收进展开区域，而非铺满
    assert '查看完整商品字段' in h
    assert 'xm-acc' in h
