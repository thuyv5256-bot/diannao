# -*- coding: utf-8 -*-
"""
Digital Store 180 天长期仿真的单元测试。

重点验证四件「公平 / 正确性」硬保证：
  1. 可复现   —— 同种子跑两遍结果完全一致；
  2. 公平     —— 两种策略面对完全相同的需求序列与初始库存；
  3. 无泄漏   —— 首日预测 = 冷启动基础值（不偷看当日真实需求）；
  4. 账能对平 —— 累计毛利 = 收入 − 销售成本 − 损耗成本，库存永不为负。
"""

import pytest

from core import simulator


def _small_gt(n: int = 12) -> dict:
    """截取前 n 天作为轻量实验环境，让测试快速运行（完整 180 天留给 CLI/网页）。"""
    gt = simulator.load_ground_truth()
    days = gt["day_list"][:n]
    gt["day_list"] = days
    gt["demand_map"] = {k: v for k, v in gt["demand_map"].items() if k[0] in days}
    gt["event_by_day"] = {d: gt["event_by_day"].get(d, "正常") for d in days}
    gt["day_events_rows"] = [e for e in gt["day_events_rows"] if e["day"] in days]
    return gt


def _run(key, n=12, seed=42, keep_daily=True):
    gt = _small_gt(n)
    spec = simulator._strategy_specs()[key]
    return simulator._simulate_strategy(spec, gt, 1800.0, seed, keep_daily=keep_daily)


# ── 可复现性 ────────────────────────────────────────────────
def test_determinism_same_seed():
    """同一策略、同一种子、同一需求序列 → 结果必须逐位一致。"""
    a = _run("baseline", n=15, seed=42, keep_daily=False)["summary"]
    b = _run("baseline", n=15, seed=42, keep_daily=False)["summary"]
    assert a == b


# ── 公平性：两种策略面对同一需求序列与同一初始库存 ──────────
def test_fairness_identical_demand_and_opening():
    diannao = _run("diannao", n=12)
    baseline = _run("baseline", n=12)
    d_map = {(r["day"], r["sku"]): r for r in diannao["daily_logs"]}
    b_map = {(r["day"], r["sku"]): r for r in baseline["daily_logs"]}
    assert set(d_map) == set(b_map)
    for key, dr in d_map.items():
        br = b_map[key]
        assert dr["actual_demand"] == br["actual_demand"]      # 同一天同一 SKU 需求一致
        # 首日（无补货差异）期初库存一致；两策略从同一起点出发
        assert dr["opening_inventory"] >= 0
    # 首日（day_list[0]）所有 SKU 的期初库存两策略完全相同
    d0 = diannao["daily"][0]["day"]
    d_first = {r["sku"]: r["opening_inventory"] for r in diannao["daily_logs"] if r["day"] == d0}
    b_first = {r["sku"]: r["opening_inventory"] for r in baseline["daily_logs"] if r["day"] == d0}
    assert d_first == b_first


# ── 无未来数据泄漏：首日预测 = 冷启动基础值 ────────────────
def test_no_leakage_day1_forecast_is_cold_start():
    gt = _small_gt(5)
    res = simulator._simulate_strategy(simulator._strategy_specs()["diannao"],
                                       gt, 1800.0, 42, keep_daily=True)
    day1 = gt["day_list"][0]
    prod_map = gt["prod_map"]
    rows = [r for r in res["daily_logs"] if r["day"] == day1]
    assert rows, "首日应有逐 SKU 日志"
    for r in rows:
        base = prod_map[r["sku"]]["base_daily_demand"]
        # 首日无历史销量，预测应退回冷启动基础值，而非偷看当日真实需求
        assert abs(r["forecast_demand"] - base) < 0.01, (r["sku"], r["forecast_demand"], base)


# ── 真实需求忠实落地 ────────────────────────────────────────
def test_actual_demand_matches_ground_truth():
    gt = _small_gt(10)
    res = simulator._simulate_strategy(simulator._strategy_specs()["baseline"],
                                       gt, 1800.0, 42, keep_daily=True)
    for r in res["daily_logs"]:
        assert abs(r["actual_demand"] - gt["demand_map"][(r["day"], r["sku"])]) < 1e-9


# ── 账能对平 + 指标边界 ─────────────────────────────────────
def test_accounting_identity_and_bounds():
    res = _run("diannao", n=10)
    s = res["summary"]
    # 累计毛利 = 收入 − 销售成本 − 损耗成本
    assert abs(s["cumulative_gross_margin"]
               - (s["revenue"] - s["cogs"] - s["spoilage_cost"])) < 0.10
    assert 0.0 <= s["stockout_rate"] <= 1.0
    assert 0.0 <= s["livelihood_secured_rate"] <= 1.0
    assert 0.0 <= s["spoilage_rate"] <= 1.0
    assert s["avg_inventory_capital"] >= 0
    # 库存永不为负（补货 + 到货 − 销售 − 损耗 ≥ 0）
    for r in res["daily_logs"]:
        assert r["closing_inventory"] >= -0.01


# ── 结果落盘（不写真实 eval/ 目录，改写到临时目录）─────────
def test_write_csvs(tmp_path, monkeypatch):
    monkeypatch.setattr(simulator, "EVAL_DIR", tmp_path)
    gt = _small_gt(6)
    spec = simulator._strategy_specs()["baseline"]
    res = simulator._simulate_strategy(spec, gt, 1800.0, 42, keep_daily=True)
    paths = simulator.write_csvs({"baseline": res}, gt, 1800.0, 42, ["baseline"], keep_daily=True)
    assert (tmp_path / "digital_store_daily.csv").exists()
    assert (tmp_path / "digital_store_summary.csv").exists()
    assert (tmp_path / "digital_store_config.json").exists()
    daily = (tmp_path / "digital_store_daily.csv").read_text(encoding="utf-8")
    assert "opening_inventory" in daily and "gross_margin" in daily
    summ = (tmp_path / "digital_store_summary.csv").read_text(encoding="utf-8")
    assert "livelihood_secured_rate" in summ
    cfg = (tmp_path / "digital_store_config.json").read_text(encoding="utf-8")
    assert '"seed": 42' in cfg and '"budget": 1800.0' in cfg
    # 返回的路径与落盘一致
    assert paths["daily"] == str(tmp_path / "digital_store_daily.csv")


# ── 图（依赖 plotly，装了才测）──────────────────────────────
def test_figures_have_two_traces():
    pytest.importorskip("plotly")
    diannao = _run("diannao", n=8)
    baseline = _run("baseline", n=8)
    results = {"diannao": diannao, "baseline": baseline}
    fig1 = simulator.build_cumulative_figure(results)
    fig2 = simulator.build_rates_figure(results)
    assert len(fig1.data) == 2          # 累计毛利两条线
    assert len(fig2.data) == 4          # 总体缺货率 + 民生最低保障达标率，各两条线


# ── 新增指标：民生商品实际缺货率 / 缺货件数（必须从日志动态累计，禁止硬编码）──
def test_livelihood_stockout_metrics_from_logs():
    res = _run("diannao", n=12)
    s = res["summary"]
    # 从逐日逐 SKU 日志重新聚合民生 SKU 的缺货件数与需求件数，验证汇总指标与之同源
    liv = [r for r in res["daily_logs"] if r["is_livelihood"] == 1]
    log_so = sum(r["stockout_qty"] for r in liv)
    log_dem = sum(r["actual_demand"] for r in liv)
    assert s["livelihood_stockout_qty"] >= 0
    assert abs(s["livelihood_stockout_qty"] - log_so) < 1.5
    assert abs(s["livelihood_stockout_rate"] - (log_so / log_dem if log_dem else 0.0)) < 0.002
    assert 0.0 <= s["livelihood_stockout_rate"] <= 1.0
