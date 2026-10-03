# -*- coding: utf-8 -*-
"""
第 4.1 步：批次库存 + FEFO + 到期报损机制的回归测试。

覆盖审计要求的 A~G 七个场景：
  A. 新货不能刷新旧货（旧批次到期正常报损，新批次继续存在）
  B. FEFO 优先销售最早到期批次
  C. 正确过期（shelf_life_days=3 无 off-by-one）
  D. 报损一次（过期批次不会重复报损、报损后不可再销售）
  E. 库存守恒（期初 + 到货 − 销售 − 报损 = 期末，对任意一天成立）
  F. 长保质期（shelf_life_days 大于模拟窗口时不应凭空过期）
  G. 缺货与报损不重复（同一件商品不同时记销售/缺货与过期）
"""

from core import simulator


def _small_gt(n: int = 12) -> dict:
    """截取前 n 天作为轻量实验环境（完整 180 天留给 CLI/网页）。"""
    gt = simulator.load_ground_truth()
    days = gt["day_list"][:n]
    gt["day_list"] = days
    gt["demand_map"] = {k: v for k, v in gt["demand_map"].items() if k[0] in days}
    gt["event_by_day"] = {d: gt["event_by_day"].get(d, "正常") for d in days}
    gt["day_events_rows"] = [e for e in gt["day_events_rows"] if e["day"] in days]
    return gt


# ── A. 新货不能刷新旧货 ──────────────────────────────────────
def test_new_arrival_does_not_refresh_old_batch():
    batches = [
        simulator._make_batch("2026-03-01", 5.0, 2),   # 旧批次：expiry 03-03
        simulator._make_batch("2026-03-02", 10.0, 2),  # 新批次：expiry 03-04
    ]
    # 03-03：旧批次必须正常过期，新批次继续存在（新货到货没有刷新旧货年龄）
    expired = simulator._expire_batches(batches, "2026-03-03")
    assert expired == 5.0
    assert len(batches) == 1
    assert batches[0]["expiry"] == "2026-03-04"
    assert batches[0]["qty"] == 10.0


# ── B. FEFO 优先卖最早到期 ───────────────────────────────────
def test_fefo_sells_earliest_expiry_first():
    batches = [
        simulator._make_batch("2026-03-01", 5.0, 3),   # expiry 03-04，最早到期
        simulator._make_batch("2026-03-03", 10.0, 5),  # expiry 03-08
    ]
    sold = simulator._fefo_sell(batches, 6.0)
    assert sold == 6.0
    # 最早到期批次(5件)售罄被移除；第二批次卖 1 件剩 9
    remaining = {b["expiry"]: b["qty"] for b in batches}
    assert "2026-03-04" not in remaining
    assert remaining["2026-03-08"] == 9.0


# ── C. 正确过期，无 off-by-one ───────────────────────────────
def test_expiry_no_off_by_one():
    b = simulator._make_batch("2026-03-01", 7.0, 3)
    assert b["expiry"] == "2026-03-04"   # arrival + shelf_life_days
    # 前三天（03-01 / 03-02 / 03-03）可售、不过期
    for d in ("2026-03-01", "2026-03-02", "2026-03-03"):
        lst = [dict(b)]
        assert simulator._expire_batches(lst, d) == 0.0, d
        assert len(lst) == 1
    # 第四天（03-04）整批报损
    lst = [dict(b)]
    assert simulator._expire_batches(lst, "2026-03-04") == 7.0
    assert lst == []


# ── D. 报损一次，报损后不可再销售 ────────────────────────────
def test_expired_batch_spoiled_only_once():
    batches = [simulator._make_batch("2026-03-01", 7.0, 3)]  # expiry 03-04
    assert simulator._expire_batches(batches, "2026-03-04") == 7.0
    assert batches == []                                     # 报损即删除
    # 第二天再报损：不再产生 spoilage
    assert simulator._expire_batches(batches, "2026-03-05") == 0.0
    # 报损后无法再销售
    assert simulator._fefo_sell(batches, 7.0) == 0.0


# ── E. 库存守恒（对任意一天）────────────────────────────────
def test_inventory_conservation_every_day():
    gt = _small_gt(8)
    res = simulator._simulate_strategy(simulator._strategy_specs()["diannao"],
                                       gt, 1800.0, 42, keep_daily=True)
    assert res["daily_logs"], "应有逐日逐 SKU 日志"
    for r in res["daily_logs"]:
        # 期初有效库存(到货前) + 当日到货 − 当日销售 − 当日报损 = 期末有效库存
        opening_before_arrivals = r["opening_inventory"] - r["arrivals"]
        rhs = (opening_before_arrivals + r["arrivals"]
               - r["sold_qty"] - r["spoilage_qty"])
        assert abs(rhs - r["closing_inventory"]) < 0.05, (r["day"], r["sku"], r)
        assert r["closing_inventory"] >= -0.01


# ── F. 长保质期不凭空过期 ────────────────────────────────────
def test_long_shelf_life_no_artificial_expiry():
    b = simulator._make_batch("2026-03-01", 100.0, 365)
    assert b["expiry"] == "2027-03-01"          # 远超 180 天窗口
    lst = [dict(b)]
    # 窗口最后一天（180 天 ≈ 2026-08-27）仍不过期
    assert simulator._expire_batches(lst, "2026-08-27") == 0.0
    assert len(lst) == 1


# ── G. 缺货与报损不重复 ─────────────────────────────────────
def test_no_double_count_sold_stockout_spoiled():
    batches = [
        simulator._make_batch("2026-03-01", 5.0, 3),   # expiry 03-04（到期）
        simulator._make_batch("2026-03-03", 10.0, 3),  # expiry 03-06
    ]
    opening = simulator._total_qty(batches)             # 15
    expired = simulator._expire_batches(batches, "2026-03-04")
    sold = simulator._fefo_sell(batches, 20.0)
    stockout = max(0.0, 20.0 - sold)
    closing = simulator._total_qty(batches)
    assert expired == 5.0
    assert sold == 10.0       # 只卖活批次，到期 5 件绝不被卖
    assert stockout == 10.0   # 缺货只算需求超过可售的部分
    # 需求侧守恒：销售 + 缺货 = 需求
    assert abs(sold + stockout - 20.0) < 1e-9
    # 供给侧守恒，且过期不与销售/缺货重叠：过期 + 售出 + 剩余 = 期初
    assert abs(expired + sold + closing - opening) < 1e-9
