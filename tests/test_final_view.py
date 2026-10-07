# -*- coding: utf-8 -*-
# 第10.3步：FINAL 实验对比展示页测试（只读 eval/final 冻结结果，不重跑实验）。
import pytest

from core import final_view


def _ready():
    return final_view.load_final() is not None


def test_loads_all_four_experiments():
    if not _ready():
        pytest.skip("eval/final 不存在")
    d = final_view.load_final()
    for exp in ('r3_vs_traditional', 'memory_ab', 'spoilage_ab', 'ablation_3obj'):
        assert exp in d['results']


def test_render_has_four_sections_and_brand():
    if not _ready():
        pytest.skip("eval/final 不存在")
    html = final_view.render_html()
    assert '小满' in html
    assert '面向社区小店的智能补货 Agent' in html
    for s in ('① 小满 vs Traditional', '② R³ 三目标如何改变经营取舍', '③ 经营经验真的会影响后续决策吗？', '④ 损耗控制 A/B'):
        assert s in html
    assert '结果可复现' in html


def test_no_forbidden_marketing_words():
    if not _ready():
        pytest.skip("eval/final 不存在")
    html = final_view.render_html()
    for bad in ('全面领先', '完胜'):
        assert bad not in html


def test_memory_stats_from_final_flow():
    if not _ready():
        pytest.skip("eval/final 不存在")
    ms = final_view.memory_stats()
    assert 'hits' in ms and 'changed' in ms
    assert ms['hits'] >= 0 and ms['changed'] >= 0
