# -*- coding: utf-8 -*-
"""
Event Tool（风险事件模块）修复的回归测试。

覆盖审计确认并已修复的五类问题：
  1. 同一事件影响不会对需求预测重复计算（预测乘一次，覆盖天数不再叠加）；
  2. 暴雨按品类区分方向（囤货刚需上升 / 冲动易腐消费下降）；
  3. 高温只影响饮料/冷饮相关品类，不无差别影响全部 SKU；
  4. 供应商断供时，断供供应商的商品不可采购（其余供应商照常）；
  5. 无事件时 Event Tool 不改变基础预测。
"""
from datetime import date, timedelta

from core import events, forecast, memory, policy, risk, simulator


# ── 通用隔离库助手 ─────────────────────────────────────────────
def _isolated_db(tmp_path, products, day_events_rows, sales_rows) -> str:
    """在临时目录建隔离记忆库，写入商品 / 每日事件 / 销量历史，返回库路径。"""
    db = tmp_path / "event_tool.db"
    simulator._setup_isolated_db(str(db), products, day_events_rows)
    memory.add_sales(sales_rows, str(db))
    return str(db)


def _constant_sales(products, start: date, end: date, heat_days=None,
                    drink_skus=None, heat_mult: float = 1.5) -> list[dict]:
    """生成一段常量销量历史；可选把高温日的饮料/冷饮销量抬到 heat_mult 倍。"""
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


# ── 1. 同一事件影响不重复计算 ──────────────────────────────────
def test_risk_multiplier_not_double_applied(tmp_path, monkeypatch):
    gt = simulator.load_ground_truth()
    products = gt["products"]
    drink_skus = {p["sku"] for p in products if p["category"] in ("饮料", "冷饮")}
    assert drink_skus, "数据中应有饮料/冷饮 SKU"

    # 造第一波高温历史（05-15~19），使第二波高温日能学到 >1 的逐商品系数
    heat_days = {f"2026-05-{d}" for d in (15, 16, 17, 18, 19)}
    sales = _constant_sales(products, date(2026, 3, 1), date(2026, 7, 13),
                            heat_days=heat_days, drink_skus=drink_skus)

    db = _isolated_db(tmp_path, products, gt["day_events_rows"], sales)
    monkeypatch.setattr(memory, "DB_PATH", db)
    events.clear_impact_cache()

    plan = policy.build_plan("2026-07-14", budget=1800.0, risks=["heat"], persist=False)

    drink_items = [it for it in plan["items"] if it["sku"] in drink_skus]
    assert drink_items
    # 事件影响确实作用在预测侧（一次）
    assert any(it["risk_factor"] > 1.0 for it in drink_items), \
        "高温应对饮料/冷饮产生 >1 的需求乘数（作用在预测侧）"

    # 关键：覆盖天数侧不再叠加同一事件系数
    for it in plan["items"]:
        assert it["risk_buffer_days"] == 0.0
        assert it["risk_buffer_note"] == ""
        # 目标覆盖天数 = 交期 + 补货缓冲 + 民生缓冲（可能被保质期封顶，但绝不多出风险项）
        assert it["target_cover_days"] <= (
            it["lead_time_days"] + it["review_buffer_days"]
            + it["livelihood_buffer_days"] + 1e-6)


# ── 2. 暴雨按品类区分方向 ──────────────────────────────────────
def test_rain_factor_has_both_directions():
    up = {k: v for k, v in risk.RAIN_FACTOR.items() if v > 1.0}
    down = {k: v for k, v in risk.RAIN_FACTOR.items() if v < 1.0}
    assert up, "暴雨应至少有一个囤货上升品类"
    assert down, "暴雨应至少有一个客流下降品类"
    assert {"方便食品", "粮油", "日用品"} <= set(up), "囤货刚需（方便食品/粮油/日用品）应上调"
    assert {"冷饮", "水果"} <= set(down), "冲动/易腐消费（冷饮/水果）应下调"
    assert risk.RAIN_DEFAULT == 1.0, "未知品类回退中性，不盲目下调"


# ── 3. 高温只影响相关品类 ──────────────────────────────────────
def test_heat_factor_only_affects_drink_categories():
    assert set(risk.HEAT_FACTOR) == {"饮料", "冷饮"}, \
        "高温只应作用于饮料/冷饮，不应无差别影响其它品类"
    assert risk.HEAT_DEFAULT == 1.0, "非相关品类保持中性"
    for cat in ("方便食品", "粮油", "日用品", "乳品", "零食", "水果", "烘焙"):
        assert risk.HEAT_FACTOR.get(cat, risk.HEAT_DEFAULT) == 1.0


# ── 4. 节假日品类映射与数据一致 ────────────────────────────────
def test_holiday_category_mapping_matches_data():
    data_cats = {"饮料", "零食", "生鲜", "乳品", "粮油", "调味", "日用品", "冷饮",
                 "方便食品", "水果", "烘焙", "蔬菜", "应急用品", "冷冻食品"}
    for k in forecast.HOLIDAY_FACTOR_BY_CATEGORY:
        assert k in data_cats, f"节日因子表品类 {k} 不在真实数据中"
    assert "日用品" in forecast.HOLIDAY_FACTOR_BY_CATEGORY
    assert "日化" not in forecast.HOLIDAY_FACTOR_BY_CATEGORY
    assert "酒饮" not in forecast.HOLIDAY_FACTOR_BY_CATEGORY


# ── 5. 供应商断供：断供供应商商品不可采购 ───────────────────────
def test_supplier_down_blocks_purchase(tmp_path, monkeypatch):
    gt = simulator.load_ground_truth()
    products = gt["products"]
    supplier_skus = [p["sku"] for p in products if p["supplier"] == risk.SUPPLIER_OUTAGE_NAME]
    other_skus = [p["sku"] for p in products if p["supplier"] != risk.SUPPLIER_OUTAGE_NAME]
    assert supplier_skus and other_skus, "数据中应同时有断供供应商与其它供应商商品"

    sales = _constant_sales(products, date(2026, 6, 1), date(2026, 7, 28))
    db = _isolated_db(tmp_path, products, gt["day_events_rows"], sales)
    monkeypatch.setattr(memory, "DB_PATH", db)
    events.clear_impact_cache()

    plan = policy.build_plan("2026-07-29", budget=1800.0, risks=["supplier"], persist=False)
    by_sku = {it["sku"]: it for it in plan["items"]}

    for sku in supplier_skus:
        it = by_sku[sku]
        assert it["supplier_down"] is True, f"{sku} 应被标记为断供供应商商品"
        assert it["raw_reorder"] == 0.0, f"断供商品 {sku} 不应产生采购需求"
        assert it["reorder_qty"] == 0.0, f"断供商品 {sku} 最终不应采购"
    assert any(by_sku[s]["reorder_qty"] > 0 for s in other_skus), \
        "断供时其它供应商商品仍应可正常采购"


# ── 6. 无事件时 Event Tool 不改变基础预测 ───────────────────────
def test_no_event_leaves_forecast_unchanged():
    recs = [{"day": f"2026-01-{i + 1:02d}", "qty_sold": 10.0, "qty_stockout": 0.0,
             "qty_spoilage": 0.0, "is_holiday": 0} for i in range(28)]
    prod = {"category": "饮料", "sku": "X", "base_daily_demand": 10.0}
    a = forecast.estimate_daily_demand(prod, "2026-01-29", recs, risks=[])
    b = forecast.estimate_daily_demand(prod, "2026-01-29", recs, risks=None)
    assert a["risk_factor"] == 1.0
    assert b["risk_factor"] == 1.0
    assert a["daily_demand"] == b["daily_demand"], \
        "无事件（[] 与 None）应得到完全相同的预测"
    mult, notes = forecast._risk_adjust(prod, [])
    assert mult == 1.0 and notes == []


# ── 7. 逐商品事件系数用潜在需求（销量 + 缺货量），而非压扁的销量 ──
def test_sku_event_stats_uses_potential_demand(monkeypatch):
    events.clear_impact_cache()
    products = [{"sku": "S1", "category": "饮料", "name": "测试水"}]
    days = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
    sales = [
        {"day": "2026-01-01", "sku": "S1", "qty_sold": 10.0, "qty_stockout": 0.0},
        {"day": "2026-01-02", "sku": "S1", "qty_sold": 10.0, "qty_stockout": 0.0},
        # 事件日：销量 8 但缺货 7 → 潜在需求 15
        {"day": "2026-01-03", "sku": "S1", "qty_sold": 8.0, "qty_stockout": 7.0},
        {"day": "2026-01-04", "sku": "S1", "qty_sold": 10.0, "qty_stockout": 0.0},
    ]
    monkeypatch.setattr(events.memory, "get_products", lambda db_path=None: products)
    monkeypatch.setattr(events.memory, "available_days", lambda db_path=None: days)
    monkeypatch.setattr(
        events.memory, "get_sales_range",
        lambda sku, s, e, db_path=None: [r for r in sales if r["sku"] == sku])
    monkeypatch.setattr(events, "historical_event_days",
                        lambda k, as_of=None, db_path=None: ["2026-01-03"])

    st = events.sku_event_stats("heat")
    assert "S1" in st
    assert st["S1"]["normal_avg"] == 10.0
    assert st["S1"]["event_avg"] == 15.0, "事件日应按潜在需求（8+7）计算，而非压扁的销量 8"
    assert st["S1"]["multiplier"] == 1.5
