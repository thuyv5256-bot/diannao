# -*- coding: utf-8 -*-
# 第8.1步：统一指标模块 core/metrics.py 的公式测试。
from core import metrics


def test_stockout_and_fill_rate():
    assert metrics.stockout_rate(3, 10) == 0.3
    assert metrics.fill_rate(7, 10) == 0.7
    assert metrics.stockout_rate(3, 0) == 0.0     # 分母为 0 安全
    assert metrics.fill_rate(0, 0) == 0.0


def test_livelihood_rates():
    assert metrics.livelihood_stockout_rate(2, 8) == 0.25
    assert metrics.livelihood_fill_rate(6, 8) == 0.75
    assert metrics.livelihood_stockout_rate(2, 0) == 0.0


def test_spoilage():
    assert metrics.spoilage_rate(2, 18) == 0.1     # 2 / (18 + 2)
    assert metrics.spoilage_rate(0, 0) == 0.0
    assert metrics.spoilage_cost(5, 3.5) == 17.5


def test_gross_margin():
    assert metrics.gross_margin(10, 2.0, 3, 5.0) == 20.0 - 15.0
    assert metrics.gross_margin(0, 2.0, 0, 5.0) == 0.0


def test_inventory_capital_and_turnover():
    assert metrics.inventory_value(4, 2.5) == 10.0
    assert metrics.avg_inventory_capital([10.0, 20.0, 30.0]) == 20.0
    assert metrics.avg_inventory_capital([]) == 0.0
    assert metrics.inventory_turnover(100.0, 20.0) == 5.0
    assert metrics.inventory_turnover(100.0, 0.0) == 0.0


def test_livelihood_secured_rate():
    assert metrics.livelihood_secured_rate(3, 4) == 0.75
    assert metrics.livelihood_secured_rate(0, 0) == 1.0     # 无民生商品 → 视为满分
    assert metrics.livelihood_secured_rate(2, 2) == 1.0


def test_expected_not_same_as_realized():
    # 决策阶段「预计缺货率」与实际「缺货率」是两个不同函数，命名区分，不得混用
    assert metrics.expected_stockout_rate is not metrics.stockout_rate
    assert metrics.expected_stockout_rate(5, 20) == 0.25
    assert metrics.expected_spoilage_cost(3, 2.0) == 6.0


def test_all_canonical_metrics_exist_in_one_module():
    # 统一来源：全部指标都由 core.metrics 提供
    names = ("stockout_rate", "fill_rate", "livelihood_stockout_rate",
             "livelihood_fill_rate", "spoilage_rate", "spoilage_cost",
             "gross_margin", "inventory_value", "avg_inventory_capital",
             "inventory_turnover", "livelihood_secured_rate")
    for name in names:
        assert callable(getattr(metrics, name))
