# -*- coding: utf-8 -*-
"""「今天生意怎么样」页展示层测试（不写库，仅 monkeypatch）。

只测表达层：页面不得宣称「自动采集 POS」，未触发学习时不得伪造 Memory 命中，
列名必须与 core 层字段口径一致。
"""
import pandas as pd
from conftest import require_app

from core import feedback_view


def _df(**over):
    data = {'商品': ['牛奶'], '实际卖出': [10], '没买到（断货）': [0],
            '损耗（报废）': [0], '商品编号': ['P006']}
    data.update(over)
    return pd.DataFrame(data)


def _result(**kw):
    base = {'summary': {'stockout_days': 0, 'spoilage_days': 0, 'adjustments': 0,
                        'skipped': 0, 'updated': 0, 'removed': 0},
            'changes': []}
    base.update(kw)
    return base


# ── 页面不得夸大数据来源 ──────────────────────────────────
def test_page_never_claims_pos_auto_collection():
    """载入只是读历史经营记录，不能写成自动采集 POS。"""
    h = feedback_view.render_table_hint('2026-08-27')
    assert 'POS' not in h and '自动采集' not in h
    # 必须如实说明断货/损耗要店主自己填
    assert '需要你按当天的实际情况填写' in h


def test_head_states_purpose():
    h = feedback_view.render_head()
    assert '今天生意怎么样' in h
    assert 'xm-h1' in h and 'xm-page' in h


# ── 未触发学习时不得伪造 ──────────────────────────────────
def test_no_trigger_only_says_saved():
    h = feedback_view.render_result(_result(), '2026-08-27')
    assert '已保存' in h
    assert '没有触发新的策略调整' in h
    # 不得出现任何"形成经验/更新策略"的表述
    assert '经营经验' not in h and '更新了' not in h


def test_dedup_does_not_claim_learning():
    h = feedback_view.render_result(
        _result(summary={'stockout_days': 0, 'spoilage_days': 0, 'adjustments': 0,
                         'skipped': 3, 'updated': 0, 'removed': 0}), '2026-08-27')
    assert '此前已经记录过' in h
    assert '经营经验' not in h


def test_removed_reversal_is_explained():
    h = feedback_view.render_result(
        _result(summary={'stockout_days': 0, 'spoilage_days': 0, 'adjustments': 0,
                         'skipped': 0, 'updated': 0, 'removed': 1}), '2026-08-27')
    assert '已撤销那次调整' in h
    assert '经营经验' not in h


# ── 真实触发学习时才展示明细 ──────────────────────────────
def test_real_changes_show_experience_table():
    changes = [{'name': '牛奶', 'is_livelihood': 1, 'trigger': '断货', 'scene': '高温',
                'safety_factor': (0.15, 0.17), 'reason': '预测误差的策略自适应'}]
    h = feedback_view.render_result(
        _result(changes=changes, summary={'stockout_days': 1, 'spoilage_days': 0,
                                          'adjustments': 1, 'skipped': 0,
                                          'updated': 0, 'removed': 0}), '2026-08-27')
    assert '更新了 1 个商品的经营经验' in h
    assert '牛奶' in h and '断货' in h and '民生' in h
    assert '0.15 → 0.17' in h
    assert 'xm-table' in h


# ── 输入校验 ─────────────────────────────────────────────
def test_invalid_input_uses_v2_semantic_color():
    h = feedback_view.render_invalid('必须填大于等于 0 的数字')
    assert 'xm-badge-red' in h and '无法保存' in h
    assert "class='note'" not in h  # 不再使用旧版 .note


def test_empty_table_message():
    assert '还没有内容' in feedback_view.render_empty()


# ── 列名口径 ─────────────────────────────────────────────
def test_columns_match_core_fields():
    assert feedback_view.FB_COLUMNS == [
        '商品', '实际卖出', '没买到（断货）', '损耗（报废）', '商品编号']
    assert feedback_view.FB_DATATYPES == ['str', 'number', 'number', 'number', 'str']


def test_submit_reads_exact_columns(monkeypatch):
    """submit_feedback 必须按 view 的列名取值，且 sku 取自商品编号列。"""
    app = require_app()   # 缺 gradio/plotly 时 skip，而不是失败
    seen = {}

    def _fake_plan(*a, **k):
        return {'items': [{'sku': 'P006', 'daily_demand': 5.0, 'reorder_qty': 3.0}]}

    def _fake_process(day, feedback, plan_context=None):
        seen['day'] = day
        seen['fb'] = feedback
        return _result()

    monkeypatch.setattr(app.policy, 'build_plan', _fake_plan)
    monkeypatch.setattr(app.evolution, 'process_feedback', _fake_process)
    monkeypatch.setattr(app, 'render_evolution_html', lambda: '')

    body, _ = app.submit_feedback('2026-08-27', _df())
    assert seen['day'] == '2026-08-27'
    assert seen['fb'] == [{'sku': 'P006', 'qty_sold': 10.0,
                           'qty_stockout': 0.0, 'qty_spoilage': 0.0}]
    assert '已保存' in body
