# -*- coding: utf-8 -*-
"""
Event Evidence Gate（事件证据门控）的回归测试。

验证七件事：
  1. 没有事件 → 不修改 Forecast；
  2. Strong Evidence → 事件可以进入 Forecast；
  3. Insufficient Evidence → 不修改 Forecast；
  4. 首次节假日不能因为人工先验直接大幅提高预测；
  5. 供应商断供不通过需求倍率处理（供给侧，走停采 + 环境拦截）；
  6. 事件影响仍然只作用一次（预测侧乘一次，覆盖天数不叠加）；
  7. Event-Blind（risks=[]）不能读取事件证据结果。
"""
from datetime import date, timedelta

from core import event_evidence, events, forecast, memory, policy, risk, simulator


# ── 通用隔离库助手（与 test_event_tool.py 同口径）────────────────
def _isolated_db(tmp_path, products, day_events_rows, sales_rows) -> str:
    db = tmp_path / "event_evidence.db"
    simulator._setup_isolated_db(str(db), products, day_events_rows)
    memory.add_sales(sales_rows, str(db))
    return str(db)


def _constant_sales(products, start: date, end: date, heat_days=None,
                    drink_skus=None, heat_mult: float = 1.5) -> list[dict]:
    heat_days = heat_days or set()
    drink_skus = drink_skus or set()
    rows = []
    d = start
    while d <= end:
        ds = d.isoformat()
        is_heat = ds in heat_days
        for p in products:
            qty = 10.0
            if is_heat and p["sku"] in drink_skus:
                qty *= heat_mult
            rows.append({"day": ds, "sku": p["sku"], "qty_sold": qty,
                         "qty_stockout": 0.0, "qty_spoilage": 0.0,
                         "is_promo": 0, "is_holiday": 0})
        d += timedelta(days=1)
    return rows


def _drink_skus(products) -> set:
    return {p["sku"] for p in products if p["category"] in ("饮料", "冷饮")}


# ── 1. 没有事件 → 不修改 Forecast ─────────────────────────────
def test_no_event_no_forecast_change():
    recs = [{"day": f"2026-01-{i + 1:02d}", "qty_sold": 10.0, "qty_stockout": 0.0,
             "qty_spoilage": 0.0, "is_holiday": 0} for i in range(28)]
    prod = {"category": "饮料", "sku": "X", "base_daily_demand": 10.0}
    a = forecast.estimate_daily_demand(prod, "2026-01-29", recs, risks=[])
    b = forecast.estimate_daily_demand(prod, "2026-01-29", recs, risks=None)
    assert a["risk_factor"] == 1.0
    assert b["risk_factor"] == 1.0
    assert a["daily_demand"] == b["daily_demand"]
    mult, notes = forecast._risk_adjust(prod, [])
    assert mult == 1.0 and notes == []


# ── 2. Strong Evidence → 事件可以进入 Forecast ────────────────
def test_strong_evidence_enters_forecast(tmp_path, monkeypatch):
    gt = simulator.load_ground_truth()
    products = gt["products"]
    drink_skus = _drink_skus(products)
    heat_days = {f"2026-05-{d}" for d in (15, 16, 17, 18, 19)}
    sales = _constant_sales(products, date(2026, 3, 1), date(2026, 7, 13),
                            heat_days=heat_days, drink_skus=drink_skus)
    db = _isolated_db(tmp_path, products, gt["day_events_rows"], sales)
    monkeypatch.setattr(memory, "DB_PATH", db)
    events.clear_impact_cache()
    event_evidence.clear_cache()

    drink = [p for p in products if p["sku"] in drink_skus][0]
    rec = event_evidence.evaluate_product("heat", drink)
    assert rec["evidence_level"] == event_evidence.LEVEL_STRONG
    assert rec["apply_to_forecast"] is True
    assert rec["uplift"] > 1.0

    plan = policy.build_plan("2026-07-14", budget=1800.0, risks=["heat"], persist=False)
    drink_items = [it for it in plan["items"] if it["sku"] in drink_skus]
    assert any(it["risk_factor"] > 1.0 for it in drink_items), \
        "Strong 高温证据应对饮料/冷饮产生 >1 的需求乘数"


# ── 3. Insufficient Evidence → 不修改 Forecast ───────────────
def test_insufficient_evidence_no_forecast(tmp_path, monkeypatch):
    gt = simulator.load_ground_truth()
    products = gt["products"]
    # 只造到首个高温日（05-15）之前的历史 → 无高温历史样本
    sales = _constant_sales(products, date(2026, 3, 1), date(2026, 5, 14))
    db = _isolated_db(tmp_path, products, gt["day_events_rows"], sales)
    monkeypatch.setattr(memory, "DB_PATH", db)
    events.clear_impact_cache()
    event_evidence.clear_cache()

    drink = [p for p in products if p["category"] in ("饮料", "冷饮")][0]
    rec = event_evidence.evaluate_product("heat", drink)
    assert rec["evidence_level"] == event_evidence.LEVEL_INSUFFICIENT
    assert rec["apply_to_forecast"] is False

    plan = policy.build_plan("2026-05-15", budget=1800.0, risks=["heat"], persist=False)
    assert all(it["risk_factor"] == 1.0 for it in plan["items"]), \
        "无历史高温证据时不应乘任何倍率"


# ── 4. 首次节假日不能因为人工先验直接大幅提高预测 ──────────────
def test_first_holiday_no_prior_boost(tmp_path, monkeypatch):
    gt = simulator.load_ground_truth()
    products = gt["products"]
    # 历史到 06-06（节假日 06-07/08/09 尚未发生）→ 首次节假日无任何历史样本
    sales = _constant_sales(products, date(2026, 3, 1), date(2026, 6, 6))
    db = _isolated_db(tmp_path, products, gt["day_events_rows"], sales)
    monkeypatch.setattr(memory, "DB_PATH", db)
    events.clear_impact_cache()
    event_evidence.clear_cache()

    plan = policy.build_plan("2026-06-07", budget=1800.0, risks=["holiday"], persist=False)
    for it in plan["items"]:
        assert it["risk_factor"] == 1.0, "首次节假日不应乘人工先验倍率"

    # 对照：某饮料商品的预测不应被抬到先验倍率（饮料先验节日系数 1.28）
    drink = [p for p in products if p["category"] == "饮料"][0]
    fc = forecast.estimate_daily_demand(
        drink, "2026-06-07",
        memory.get_sales(drink["sku"], "2026-06-07", lookback=28),
        risks=["holiday"])
    assert fc["risk_factor"] == 1.0


# ── 5. 供应商断供不通过需求倍率处理 ───────────────────────────
def test_supplier_outage_not_demand_multiplier(tmp_path, monkeypatch):
    gt = simulator.load_ground_truth()
    products = gt["products"]
    sales = _constant_sales(products, date(2026, 6, 1), date(2026, 7, 28))
    db = _isolated_db(tmp_path, products, gt["day_events_rows"], sales)
    monkeypatch.setattr(memory, "DB_PATH", db)
    events.clear_impact_cache()
    event_evidence.clear_cache()

    plan = policy.build_plan("2026-07-29", budget=1800.0, risks=["supplier"], persist=False)
    for it in plan["items"]:
        assert it["risk_factor"] == 1.0, "断供不应产生需求预测倍率"

    supplier_skus = {p["sku"] for p in products if p["supplier"] == risk.SUPPLIER_OUTAGE_NAME}
    by_sku = {it["sku"]: it for it in plan["items"]}
    for sku in supplier_skus:
        assert by_sku[sku]["supplier_down"] is True
        assert by_sku[sku]["reorder_qty"] == 0.0


# ── 6. 事件影响仍然只作用一次 ────────────────────────────────
def test_event_effect_applied_once(tmp_path, monkeypatch):
    gt = simulator.load_ground_truth()
    products = gt["products"]
    drink_skus = _drink_skus(products)
    heat_days = {f"2026-05-{d}" for d in (15, 16, 17, 18, 19)}
    sales = _constant_sales(products, date(2026, 3, 1), date(2026, 7, 13),
                            heat_days=heat_days, drink_skus=drink_skus)
    db = _isolated_db(tmp_path, products, gt["day_events_rows"], sales)
    monkeypatch.setattr(memory, "DB_PATH", db)
    events.clear_impact_cache()
    event_evidence.clear_cache()

    plan = policy.build_plan("2026-07-14", budget=1800.0, risks=["heat"], persist=False)
    for it in plan["items"]:
        assert it["risk_buffer_days"] == 0.0, "事件影响只应在预测侧乘一次，覆盖天数不再叠加"
        assert it["risk_buffer_note"] == ""


# ── 7. Event-Blind（risks=[]）不能读取事件证据结果 ────────────
def test_event_blind_cannot_read_evidence(tmp_path, monkeypatch):
    gt = simulator.load_ground_truth()
    products = gt["products"]
    sales = _constant_sales(products, date(2026, 3, 1), date(2026, 7, 13))
    db = _isolated_db(tmp_path, products, gt["day_events_rows"], sales)
    monkeypatch.setattr(memory, "DB_PATH", db)
    events.clear_impact_cache()
    event_evidence.clear_cache()

    def _boom(*a, **k):
        raise AssertionError("Event-Blind 决策不应读取事件证据")

    monkeypatch.setattr(event_evidence, "evaluate_product", _boom)
    # Blind：risks=[] → 决策全程不触碰证据门控（不调用 evaluate_product）
    plan = policy.build_plan("2026-07-14", budget=1800.0, risks=[], persist=False)
    assert all(it["risk_factor"] == 1.0 for it in plan["items"])


# ── 8. 证据记录结构完整（字段齐全，数字真实计算）──────────────
def test_evidence_record_structure(tmp_path, monkeypatch):
    gt = simulator.load_ground_truth()
    products = gt["products"]
    drink_skus = _drink_skus(products)
    heat_days = {f"2026-05-{d}" for d in (15, 16, 17, 18, 19)}
    sales = _constant_sales(products, date(2026, 3, 1), date(2026, 7, 13),
                            heat_days=heat_days, drink_skus=drink_skus)
    db = _isolated_db(tmp_path, products, gt["day_events_rows"], sales)
    monkeypatch.setattr(memory, "DB_PATH", db)
    events.clear_impact_cache()
    event_evidence.clear_cache()

    drink = [p for p in products if p["sku"] in drink_skus][0]
    rec = event_evidence.evaluate_product("heat", drink)
    for field in ("sample_count", "baseline_count", "uplift",
                  "direction_consistency", "ci_low", "ci_high",
                  "evidence_level", "apply_to_forecast", "reason"):
        assert field in rec, f"证据记录缺少字段 {field}"
    assert rec["sample_count"] >= 1
    assert rec["baseline_count"] >= 1
    assert 0.0 < rec["ci_low"] <= rec["ci_high"]


# ══════════════════════════════════════════════════════════
# 时间穿越修复（P1-1 / C-3）：Day t 的决策只允许使用 Day t−1 及以前
# 已结算的数据。新增四个回归测试 A/B/C/D。
# ══════════════════════════════════════════════════════════

# ── A. 未来极端值不影响今天的证据 ─────────────────────────
def test_future_extreme_value_does_not_affect_today(tmp_path, monkeypatch):
    gt = simulator.load_ground_truth()
    products = gt["products"]
    drink_skus = _drink_skus(products)
    drink = [p for p in products if p["sku"] in drink_skus][0]
    heat_days = {f"2026-05-{d}" for d in (15, 16, 17, 18, 19)}
    sales = _constant_sales(products, date(2026, 3, 1), date(2026, 7, 13),
                            heat_days=heat_days, drink_skus=drink_skus)
    db = _isolated_db(tmp_path, products, gt["day_events_rows"], sales)
    monkeypatch.setattr(memory, "DB_PATH", db)
    events.clear_impact_cache()
    event_evidence.clear_cache()

    before = event_evidence.evaluate_product("heat", drink, as_of="2026-07-14")
    assert before["evidence_level"] == event_evidence.LEVEL_STRONG

    # 在决策日之后（07-20）人为加入一个销量极大的"未来"高温日，
    # 并把它登记为高温事件日 —— 对 07-14 而言这是尚未发生的未来。
    future_rows = [
        {"day": "2026-07-20", "sku": p["sku"],
         "qty_sold": 1000.0 if p["sku"] in drink_skus else 10.0,
         "qty_stockout": 0.0, "qty_spoilage": 0.0, "is_promo": 0, "is_holiday": 0}
        for p in products
    ]
    memory.add_sales(future_rows, db)
    memory.upsert_day_events([{"day": "2026-07-20", "event": "高温",
                               "weather": "", "temperature_c": 35.0,
                               "is_weekend": 0, "supplier_available": 1}], db)
    events.clear_impact_cache()
    event_evidence.clear_cache()

    # as_of=07-14：未来极端值必须被排除 → 证据与之前完全一致
    after = event_evidence.evaluate_product("heat", drink, as_of="2026-07-14")
    assert after["sample_count"] == before["sample_count"]
    assert after["baseline_count"] == before["baseline_count"]
    assert after["uplift"] == before["uplift"]
    assert after["evidence_level"] == before["evidence_level"]

    # 对照：不设截止（全量历史）确实会多出一个未来高温日样本，
    # 证明该未来日已被正确登记、且 as_of 门控确实把它挡在了外面。
    full = event_evidence.evaluate_product("heat", drink)
    assert full["sample_count"] == before["sample_count"] + 1


# ── B. 当天结果不影响当天决策；Day t+1 才看到 Day t ────────
def test_today_sales_do_not_affect_today_decision(tmp_path, monkeypatch):
    gt = simulator.load_ground_truth()
    products = gt["products"]
    drink_skus = _drink_skus(products)
    drink = [p for p in products if p["sku"] in drink_skus][0]
    heat_days = {f"2026-05-{d}" for d in (15, 16, 17, 18, 19)}
    sales = _constant_sales(products, date(2026, 3, 1), date(2026, 7, 13),
                            heat_days=heat_days, drink_skus=drink_skus)
    db = _isolated_db(tmp_path, products, gt["day_events_rows"], sales)
    monkeypatch.setattr(memory, "DB_PATH", db)
    events.clear_impact_cache()
    event_evidence.clear_cache()

    before = event_evidence.evaluate_product("heat", drink, as_of="2026-07-14")
    assert before["sample_count"] >= 3

    fc_before = forecast.estimate_daily_demand(
        drink, "2026-07-14",
        memory.get_sales(drink["sku"], "2026-07-14", lookback=28),
        risks=["heat"])

    # Day t（07-14，本身是第二波高温日）的销售，是在当天决策之后才结算的
    day_rows = [
        {"day": "2026-07-14", "sku": p["sku"],
         "qty_sold": 20.0 if p["sku"] in drink_skus else 10.0,
         "qty_stockout": 0.0, "qty_spoilage": 0.0, "is_promo": 0, "is_holiday": 0}
        for p in products
    ]
    memory.add_sales(day_rows, db)
    events.clear_impact_cache()
    event_evidence.clear_cache()

    # 当天证据不变 → 当天的预测/决策不变
    after = event_evidence.evaluate_product("heat", drink, as_of="2026-07-14")
    assert after["sample_count"] == before["sample_count"]
    assert after["uplift"] == before["uplift"]

    fc_after = forecast.estimate_daily_demand(
        drink, "2026-07-14",
        memory.get_sales(drink["sku"], "2026-07-14", lookback=28),
        risks=["heat"])
    assert fc_after["risk_factor"] == fc_before["risk_factor"], \
        "当天结算的销量不应改变当天的预测乘数"

    # Day t+1（07-15）才允许看到 07-14 的结果 → 事件样本 +1
    next_day = event_evidence.evaluate_product("heat", drink, as_of="2026-07-15")
    assert next_day["sample_count"] == before["sample_count"] + 1


# ── C. 历史数据可以正常进入证据 ───────────────────────────
def test_historical_data_enters_evidence(tmp_path, monkeypatch):
    gt = simulator.load_ground_truth()
    products = gt["products"]
    drink_skus = _drink_skus(products)
    drink = [p for p in products if p["sku"] in drink_skus][0]
    heat_days = {f"2026-05-{d}" for d in (15, 16, 17, 18, 19)}
    sales = _constant_sales(products, date(2026, 3, 1), date(2026, 7, 13),
                            heat_days=heat_days, drink_skus=drink_skus)
    db = _isolated_db(tmp_path, products, gt["day_events_rows"], sales)
    monkeypatch.setattr(memory, "DB_PATH", db)
    events.clear_impact_cache()
    event_evidence.clear_cache()

    before = event_evidence.evaluate_product("heat", drink, as_of="2026-07-14")
    assert before["uplift"] > 1.0

    # 修正一个"过去"的高温日（05-15）销量 → 证据应立即随之更新
    memory.add_sales([{"day": "2026-05-15", "sku": drink["sku"], "qty_sold": 30.0,
                       "qty_stockout": 0.0, "qty_spoilage": 0.0,
                       "is_promo": 0, "is_holiday": 0}], db)
    events.clear_impact_cache()
    event_evidence.clear_cache()

    after = event_evidence.evaluate_product("heat", drink, as_of="2026-07-14")
    assert after["sample_count"] == before["sample_count"]
    assert after["uplift"] > before["uplift"], \
        "过去的历史数据修正应正常进入证据，不能被 as_of 门控误伤"


# ── D. 未来事件不能出现在 historical_event_days ───────────
def test_future_events_not_in_historical_event_days(tmp_path, monkeypatch):
    gt = simulator.load_ground_truth()
    products = gt["products"]
    sales = _constant_sales(products, date(2026, 3, 1), date(2026, 7, 13))
    db = _isolated_db(tmp_path, products, gt["day_events_rows"], sales)
    monkeypatch.setattr(memory, "DB_PATH", db)
    events.clear_impact_cache()

    # 对 07-14 而言，真实数据里的 07-14~18 是第二波高温（未来），绝不能返回；
    # 只应返回 05-15~19 这 5 个已经结算完成的高温日。
    days = events.historical_event_days("heat", as_of="2026-07-14")
    assert days == [f"2026-05-{d}" for d in (15, 16, 17, 18, 19)]
