# -*- coding: utf-8 -*-
"""AI 决策中枢 · 第一环（core/ai_events.py）测试。

覆盖三条主线：
  1. 无 Key / 调用失败时必须能降级跑通（AI 不可用也不阻塞业务）
  2. 模型输出必须被白名单 + 夹紧过滤 —— AI 不能越权放大修正
  3. AI 绝不产出补货数量：它只给参数，数字仍由规则链路算

以及最重要的一条回归：
  **ai_factors=None 与 ai_factors={} 的方案指纹必须逐位一致**（降级不改变业务结果）。

注意 mock 层级：这里 patch 的是 `llm.chat_json`（模型出口），
而不是 `ai_events.llm_parse` —— 后者正是白名单校验发生的地方，patch 掉等于把被测逻辑一起跳过了。
"""

import hashlib
import json

import pytest

from core import ai_events, forecast, llm, memory, policy, risk


# ─────────────────────────────────────────── 测试脚手架

def _fake_model(monkeypatch, payload):
    """伪造模型的结构化输出（绕过真实网络），让 llm_parse 的真实校验链跑起来。"""
    monkeypatch.setattr(llm, "is_enabled", lambda: True)
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: payload)


def _no_model(monkeypatch):
    monkeypatch.setattr(llm, "is_enabled", lambda: False)


def _rule_only(monkeypatch):
    """强制走降级：模型出口返回 None。"""
    monkeypatch.setattr(llm, "is_enabled", lambda: True)
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: None)


def _plan_fingerprint(ai_factors=None, risks=None):
    """方案的补货指纹 —— 用来证明「降级不改变业务结果」。"""
    plan = policy.build_plan("2026-08-28", 1200.0, policy.MODE_DIANNAO,
                             persist=False, risks=risks, ai_factors=ai_factors)
    rows = [(it["sku"], round(float(it["reorder_qty"] or 0), 6),
             round(float(it["daily_demand"] or 0), 6))
            for it in plan["items"]]
    return hashlib.md5(json.dumps(rows, sort_keys=True).encode()).hexdigest()


# ─────────────────────────────────────────── 规则兜底（无 Key 路径）

def test_rule_parse_empty_text_is_no_event():
    r = ai_events.rule_parse("")
    assert r["events"] == []
    assert r["source"] == "rule"


@pytest.mark.parametrize("text,key", [
    ("明天下大暴雨，晚上没什么人出门", "rain"),
    ("明天高温 38 度，空调开着都凉快不了", "heat"),
    ("明天国庆节，人肯定多", "holiday"),
    ("供应商说送不来货，明天断供", "supplier"),
])
def test_rule_parse_keywords_hit_expected_keys(text, key):
    keys = [e["key"] for e in ai_events.rule_parse(text)["events"]]
    assert key in keys


def test_rule_parse_never_claims_strong_evidence():
    """关键词命中不等于证据充分 —— 规则路径最多给 weak。

    这是防止「店主随口一句话就大幅改预测」的关键约束。
    """
    for text in ("明天下大暴雨", "明天高温", "明天国庆节", "明天送不来货"):
        for e in ai_events.rule_parse(text)["events"]:
            assert e["level"] == "weak", text
            assert e["source"] == "rule"


def test_rule_parse_empty_categories_mean_no_demand_shift():
    """规则路径不给受影响品类 → 不产生任何需求侧乘数（只会走既有风险因子链）。"""
    assert ai_events.finalize(ai_events.rule_parse("明天下大暴雨"))["factors"] == {}


def test_weak_evidence_halves_the_factor():
    """weak 证据的乘数要向 1.0 收缩一半（不敢全信，也不敢完全忽略）。"""
    res = ai_events.finalize({
        "events": [{"key": "rain", "level": "weak", "affected_categories": ["饮料"],
                    "demand_factor": 0.5, "severity": "moderate"}],
    })
    assert res["factors"]["饮料"] == pytest.approx(0.75)


def test_insufficient_evidence_contributes_nothing():
    res = ai_events.finalize({
        "events": [{"key": "rain", "level": "insufficient", "affected_categories": ["饮料"],
                    "demand_factor": 0.2, "severity": "mild"}],
    })
    assert res["factors"] == {}


def test_strong_evidence_applies_factor_fully():
    """strong 证据的乘数全额生效（不打折）。"""
    res = ai_events.finalize({
        "events": [{"key": "rain", "level": "strong", "affected_categories": ["饮料"],
                    "demand_factor": 0.7, "severity": "severe"}],
    })
    assert res["factors"]["饮料"] == pytest.approx(0.7)


def test_unity_factor_is_not_recorded_as_adjustment():
    """乘数恰好为 1.0 等于「没修正」，不该留下空转条目。"""
    res = ai_events.finalize({
        "events": [{"key": "rain", "level": "strong", "affected_categories": ["饮料"],
                    "demand_factor": 1.0, "severity": "mild"}],
    })
    assert res["factors"] == {}


# ─────────────────────────────────────────── 统一入口与降级

def test_parse_without_key_falls_back_to_rule(monkeypatch):
    _no_model(monkeypatch)
    r = ai_events.parse("明天下大暴雨，晚上没人出门", ["饮料", "零食"])
    assert r["source"] == "rule"
    assert "rain" in r["active"]


def test_parse_falls_back_when_model_output_unusable(monkeypatch):
    """模型返回 None / 非 dict / events 非 list 时，必须自动走规则而不是抛异常。"""
    for bad in (None, {}, {"events": "不是列表"}, [1, 2, 3]):
        _rule_only(monkeypatch)
        monkeypatch.setattr(llm, "chat_json", lambda *a, **k: bad)
        r = ai_events.parse("明天下大暴雨", ["饮料"])
        assert r["source"] == "rule", bad
        assert "rain" in r["active"], bad


def test_blank_text_does_not_burn_a_model_call(monkeypatch):
    """空描述不该白烧一次模型调用。"""
    called = []
    monkeypatch.setattr(llm, "is_enabled", lambda: True)
    monkeypatch.setattr(llm, "chat_json",
                        lambda *a, **k: called.append(1) or None)
    r = ai_events.parse("   ", ["饮料"])
    assert called == []
    assert r["events"] == []


def test_mode_label_reflects_key_presence(monkeypatch):
    _no_model(monkeypatch)
    assert "降级" in ai_events.mode_label()
    monkeypatch.setattr(llm, "is_enabled", lambda: True)
    assert "AI" in ai_events.mode_label()


def test_parse_risks_returns_normalized_keys(monkeypatch):
    """便捷入口的输出必须能直接喂给 policy.build_plan(risks=...)。"""
    _no_model(monkeypatch)
    keys = ai_events.parse_risks("明天下大暴雨")
    assert set(keys) <= set(risk.RISK_KEYS)
    assert risk.normalize(keys) == keys


# ─────────────────────────────────────────── 模型输出的白名单与夹紧

def test_model_invented_keys_are_dropped(monkeypatch):
    """模型发明的风险键（如 "pandemic"）必须被丢弃，不能进 active。"""
    _fake_model(monkeypatch, {
        "events": [{"key": "pandemic", "level": "strong", "severity": "severe",
                    "affected_categories": ["饮料"], "demand_factor": 0.3}],
        "summary": "x", "source": "llm", "model": "fake",
    })
    r = ai_events.parse("随便什么", ["饮料"])
    assert r["events"] == []
    assert r["active"] == []
    assert r["factors"] == {}


def test_non_dict_event_entries_are_skipped(monkeypatch):
    """模型偶尔会在 events 里塞字符串/null，不能让整次解析崩掉。"""
    _fake_model(monkeypatch, {
        "events": ["字符串", None, 42,
                   {"key": "rain", "level": "weak", "severity": "moderate",
                    "affected_categories": [], "demand_factor": 1.0}],
        "summary": "x", "source": "llm", "model": "fake",
    })
    r = ai_events.parse("明天下大暴雨", ["饮料"])
    assert [e["key"] for e in r["events"]] == ["rain"]


def test_unknown_categories_are_dropped(monkeypatch):
    """模型只能影响本店在售品类；编出来的品类一律丢弃。"""
    _fake_model(monkeypatch, {
        "events": [{"key": "rain", "level": "strong", "severity": "severe",
                    "affected_categories": ["饮料", "外星食品"], "demand_factor": 0.5}],
        "summary": "x", "source": "llm", "model": "fake",
    })
    r = ai_events.parse("下雨", ["饮料", "零食"])
    assert "外星食品" not in r["factors"]
    assert "饮料" in r["factors"]


@pytest.mark.parametrize("bad", [0.0, -5.0, 99.0, None, "不是数字", [1]])
def test_demand_factor_is_clamped(monkeypatch, bad):
    """任何离谱的乘数都必须被夹进 [_FACTOR_MIN, _FACTOR_MAX]。"""
    _fake_model(monkeypatch, {
        "events": [{"key": "rain", "level": "strong", "severity": "severe",
                    "affected_categories": ["饮料"], "demand_factor": bad}],
        "summary": "x", "source": "llm", "model": "fake",
    })
    f = ai_events.parse("下雨", ["饮料"])["factors"].get("饮料", 1.0)
    assert ai_events._FACTOR_MIN <= f <= ai_events._FACTOR_MAX


def test_bad_enum_values_fall_back_to_safe_default(monkeypatch):
    """模型返回非法枚举值时归一到合法值，不让脏数据流进规则层。"""
    _fake_model(monkeypatch, {
        "events": [{"key": "rain", "level": "特别严重", "severity": "巨severe",
                    "affected_categories": ["饮料"], "demand_factor": 0.5}],
        "summary": "x", "source": "llm", "model": "fake",
    })
    e = ai_events.parse("下雨", ["饮料"])["events"][0]
    assert e["level"] in ai_events.LEVELS
    assert e["severity"] in ai_events.SEVERITIES


def test_negative_lead_time_is_clamped(monkeypatch):
    _fake_model(monkeypatch, {
        "events": [{"key": "supplier", "level": "strong", "severity": "severe",
                    "affected_categories": [], "demand_factor": 1.0,
                    "lead_time_hours": -99}],
        "summary": "x", "source": "llm", "model": "fake",
    })
    assert ai_events.parse("送不来货", ["饮料"])["events"][0]["lead_time_hours"] == 0


def test_supplier_event_does_not_touch_demand(monkeypatch):
    """断供是供给侧事件，不该去改需求预测乘数。"""
    _fake_model(monkeypatch, {
        "events": [{"key": "supplier", "level": "strong", "severity": "severe",
                    "affected_categories": ["饮料"], "demand_factor": 0.3}],
        "summary": "x", "source": "llm", "model": "fake",
    })
    r = ai_events.parse("送不来货", ["饮料"])
    assert r["factors"] == {}
    assert "supplier" in r["active"]
    assert r["effective"] is True      # 但它仍然是一次「有效事件」


def test_factors_do_not_multiply_explode():
    """总量守恒：同品类多事件叠乘后仍必须落在夹紧区间内。"""
    res = ai_events.finalize({
        "events": [{"key": "rain", "level": "strong", "affected_categories": ["饮料"],
                    "demand_factor": 0.2, "severity": "severe"}] * 6,
    })
    assert res["factors"]
    for f in res["factors"].values():
        assert ai_events._FACTOR_MIN <= f <= ai_events._FACTOR_MAX


# ─────────────────────────────────────────── 核心断言：AI 不产出数量

def test_ai_never_emits_any_quantity_field(monkeypatch):
    """结构性防线：AI 事件里不允许出现任何数量/金额类键。

    模型就算胡编 reorder_qty，也进不了结果—— 数量只能由 policy 链路算。
    """
    _fake_model(monkeypatch, {
        "events": [{"key": "rain", "level": "strong", "severity": "severe",
                    "affected_categories": ["饮料"], "demand_factor": 0.5,
                    "reorder_qty": 999, "qty": 888, "daily_demand": 77,
                    "budget": 50000, "cover_days": 365}],
        "summary": "x", "source": "llm", "model": "fake",
    })
    e = ai_events.parse("下雨", ["饮料"])["events"][0]
    for banned in ("reorder_qty", "qty", "daily_demand", "budget", "cover_days"):
        assert banned not in e


def test_ai_result_carries_only_parameters():
    """整个 AI 结果里不允许出现顶层数量字段。"""
    r = ai_events.parse("明天下大暴雨", ["饮料"])
    for banned in ("reorder_qty", "qty", "budget", "total_cost"):
        assert banned not in r


# ─────────────────────────────────────────── 降级不改变业务结果（最重要）

def test_no_ai_factors_leaves_plan_bit_identical():
    """ai_factors=None 与 ai_factors={} 的方案指纹必须逐位相同。"""
    assert _plan_fingerprint(None) == _plan_fingerprint({})


def test_no_key_run_matches_ai_factors_empty_run(monkeypatch):
    """无 Key 降级路径产出的数字，与「传空因子」完全一致。"""
    _no_model(monkeypatch)
    r = ai_events.parse("明天下大暴雨，晚上没人出门", ["饮料"])
    assert _plan_fingerprint(r.get("factors") or None) == _plan_fingerprint({})


# ─────────────────────────────────────────── 反向断言：因子真的进了预测

def test_ai_factors_actually_change_forecast():
    """若这条不成立，上面所有「一致」断言都毫无意义。"""
    cats = sorted({str(p.get("category") or "").strip()
                   for p in memory.get_products() if p.get("category")})
    if not cats:
        pytest.skip("记忆库为空")
    cat = cats[0]

    base = policy.build_plan("2026-08-28", 1200.0, policy.MODE_DIANNAO, persist=False)
    with_ai = policy.build_plan("2026-08-28", 1200.0, policy.MODE_DIANNAO, persist=False,
                                risks=["rain"], ai_factors={cat: 0.6})
    b = {it["sku"]: it["daily_demand"] for it in base["items"] if it["category"] == cat}
    a = {it["sku"]: it["daily_demand"] for it in with_ai["items"] if it["category"] == cat}
    assert b and a, "该品类下应有商品"
    assert any(abs(a[k] - b[k]) > 1e-9 for k in b), "AI 因子必须真的改变日需求"


def test_plan_exposes_ai_factors_for_display():
    """plan 里带上 ai_factors，页面才能区分「这次算没算 AI」。"""
    p1 = policy.build_plan("2026-08-28", 1200.0, policy.MODE_DIANNAO, persist=False)
    assert p1.get("ai_factors") is None
    p2 = policy.build_plan("2026-08-28", 1200.0, policy.MODE_DIANNAO, persist=False,
                           ai_factors={"饮料": 0.8})
    assert p2.get("ai_factors") == {"饮料": 0.8}


# ─────────────────────────────────────────── forecast 层的硬边界常量

def test_ai_safety_constants_are_sane():
    assert 0 < forecast.AI_MAX_ADJUST <= 0.25
    assert 0 < forecast.AI_STRONG_CAP <= 0.30


def test_ai_factor_returns_note_for_traceability():
    """AI 修正必须留下可追溯的说明（页面上要能看到 AI 做了什么）。"""
    prod = {"category": "饮料", "name": "矿泉水", "sku": "M1", "unit": "瓶",
            "shelf_life_days": 30, "is_livelihood": 0, "pack_size": 1,
            "on_hand": 50, "cost_price": 1.0, "sell_price": 2.0}
    _, notes = forecast._ai_factor(prod, {"饮料": 0.8})
    assert notes, "应当记录一条 AI 修正说明"
    _, none_notes = forecast._ai_factor(prod, None)
    assert none_notes == []


def test_ai_factor_ignores_unrelated_category():
    """因子只作用于命中的品类。"""
    prod = {"category": "饮料", "name": "矿泉水", "sku": "M1", "unit": "瓶",
            "shelf_life_days": 30, "is_livelihood": 0, "pack_size": 1,
            "on_hand": 50, "cost_price": 1.0, "sell_price": 2.0}
    mult, notes = forecast._ai_factor(prod, {"零食": 0.5})
    assert mult == 1.0
    assert notes == []
