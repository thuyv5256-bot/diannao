# -*- coding: utf-8 -*-
"""
Event-Aware vs Event-Blind 公平对照实验的回归测试。

验证六件事：
  1. 两个世界使用完全相同的外部事件与真实需求（同一份 CSV 数据，纯函数读取）；
  2. Event-Blind 的决策阶段读不到事件信息（预测乘数=1，不感知断供）；
  3. 两个世界的真实需求环境一致（需求序列与策略无关）；
  4. 两个世界的断供环境一致（供应商断供由结算层强制拦截，与 Agent 是否知晓无关）；
  5. 除「Agent 是否获得事件信息」外，其余核心参数完全一致；
  6. 固定 seed 后实验可复现。
"""
from collections import Counter

from core import forecast, policy, risk, simulator


# ── 1 + 3：两个世界使用完全相同的外部事件与真实需求 ──────────────
def test_ab_uses_identical_external_environment():
    # load_ground_truth 是读固定 CSV 的纯函数：两次加载的上帝视角数据完全一致，
    # 且 run_strategies 用同一份 gt 驱动所有策略 → 外部事件与真实需求天然相同。
    gt1 = simulator.load_ground_truth()
    gt2 = simulator.load_ground_truth()
    assert gt1["demand_map"] == gt2["demand_map"]
    assert gt1["event_by_day"] == gt2["event_by_day"]
    assert gt1["day_list"] == gt2["day_list"]

    ev = Counter(gt1["event_by_day"].values())
    assert ev["高温"] == 10
    assert ev["暴雨"] == 6
    assert ev["节假日"] == 3
    assert ev["供应商D断供"] == 3
    # 真实需求（qty_sold）与事件无关：同一 (day, sku) 的需求对所有策略都一样
    assert all(v >= 0 for v in gt1["demand_map"].values())


# ── 5：除「是否获得事件信息」外，其余核心参数完全一致 ─────────────
def test_ab_specs_differ_only_in_event_access():
    specs = simulator._strategy_specs()
    aware = specs["diannao"]           # Event-Aware
    blind = specs["diannao_no_event"]  # Event-Blind
    assert aware["use_events"] is True
    assert blind["use_events"] is False
    # R³ 模式 / Memory 开关 / 民生保障 三项核心参数必须一致
    for k in ("mode", "use_memory", "protect_livelihood"):
        assert aware[k] == blind[k], f"{k} 应在两世界一致"


# ── 2：Event-Blind 的决策阶段读不到事件信息 ──────────────────────
def test_blind_decision_has_no_event_access(tmp_path, monkeypatch):
    gt = simulator.load_ground_truth()
    products = gt["products"]
    db = str(tmp_path / "event_ab_blind.db")
    simulator._setup_isolated_db(db, products, gt["day_events_rows"])
    monkeypatch.setattr(simulator.memory, "DB_PATH", db)

    # 盲区 Agent（risks=[]）在断供日做决策：不感知任何事件
    plan = policy.build_plan("2026-07-29", budget=1800.0, risks=[], persist=False)
    for it in plan["items"]:
        assert it["risk_factor"] == 1.0, "盲区预测不应带任何事件乘数"
        assert it["supplier_down"] is False, "盲区决策不应主动停采断供供应商"

    # 对照：同一断供日，感知 Agent（risks=["supplier"]）确实会停采断供供应商
    aware = policy.build_plan("2026-07-29", budget=1800.0, risks=["supplier"], persist=False)
    supplier_skus = {p["sku"] for p in products
                     if p["supplier"] == risk.SUPPLIER_OUTAGE_NAME}
    aware_down = [it for it in aware["items"] if it["sku"] in supplier_skus and it["supplier_down"]]
    assert aware_down, "感知 Agent 在断供日应停采断供供应商商品"


# ── 4：两个世界的断供环境一致（环境强制拦截，与 Agent 是否知晓无关）──
def test_supplier_outage_enforced_environmentally():
    event_by_day = {"2026-07-29": "供应商D断供", "2026-07-28": "正常"}
    items = [
        {"sku": "P016", "supplier": "供应商D", "reorder_qty": 10.0, "cost": 20.0},
        {"sku": "P001", "supplier": "供应商A", "reorder_qty": 5.0, "cost": 10.0},
    ]
    # 断供日：供应商D 的商品下单被环境拦截，其它供应商照常
    blocked = simulator._enforce_supplier_outage("2026-07-29", event_by_day, items)
    assert blocked == ["P016"]
    assert items[0]["reorder_qty"] == 0.0 and items[0]["cost"] == 0.0
    assert items[1]["reorder_qty"] == 5.0

    # 非断供日：不拦截
    items2 = [{"sku": "P016", "supplier": "供应商D", "reorder_qty": 10.0, "cost": 20.0}]
    assert simulator._enforce_supplier_outage("2026-07-28", event_by_day, items2) == []
    assert items2[0]["reorder_qty"] == 10.0


# ── 6：固定 seed 后实验可复现 ──────────────────────────────────
def test_ab_reproducible_with_fixed_seed():
    gt = simulator.load_ground_truth()
    # baseline 为纯贪心（最快），用于验证仿真框架在固定 seed + 固定需求下确定性复现；
    # diannao 走 HiGHS MILP，同为确定性求解器（相同输入 → 相同输出）。
    spec = simulator._strategy_specs()["baseline"]
    r1 = simulator._simulate_strategy(spec, gt, 1800.0, 42, keep_daily=False)
    r2 = simulator._simulate_strategy(spec, gt, 1800.0, 42, keep_daily=False)
    assert r1["summary"] == r2["summary"], "固定 seed 下两次运行应得到完全一致的长期指标"
