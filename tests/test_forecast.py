# -*- coding: utf-8 -*-
"""需求预测新逻辑（趋势外推 / 潜在需求还原开关）的测试。"""

from pytest import approx

from core import forecast
from core.config import (
    TREND_MULT_MAX,
    TREND_MULT_MIN,
)


def _recs(values):
    recs = []
    for i, v in enumerate(values):
        r = {"day": f"2026-01-{i + 1:02d}", "qty_sold": v, "qty_stockout": 0.0,
             "qty_spoilage": 0.0, "is_holiday": 0}
        recs.append(r)
    return recs


def test_potential_restore():
    r = {"qty_sold": 5, "qty_stockout": 3}
    assert forecast._potential(r, True) == 8
    assert forecast._potential(r, False) == 5


def test_trend_flat():
    slope, mult = forecast._trend(_recs([10] * 20))
    assert slope == approx(0.0)
    assert mult == approx(1.0)


def test_trend_rising_clamped():
    slope, mult = forecast._trend(_recs(list(range(1, 21))))
    assert mult > 1.0
    assert mult <= TREND_MULT_MAX


def test_trend_falling_clamped():
    slope, mult = forecast._trend(_recs(list(range(20, 0, -1))))
    assert mult < 1.0
    assert mult >= TREND_MULT_MIN


def test_weekday_profile_bounds():
    prof = forecast.weekday_profile(_recs([5, 8, 6, 9, 7, 10, 6] * 4))
    assert len(prof) == 7
    assert all(forecast.WEEKDAY_FACTOR_MIN <= v <= forecast.WEEKDAY_FACTOR_MAX for v in prof)


def test_estimate_empty_cold_start():
    out = forecast.estimate_daily_demand({"category": "粮油"}, "2026-01-01", [])
    assert out["cold_start"] is True
    assert out["daily_demand"] == 1.0
