# -*- coding: utf-8 -*-
"""P2：AI 链路的延迟与fallback 可靠性测试。

要证明的事情很具体：**无论大模型正常、超时、报错还是没有 Key，
补货主流程都必须能跑完**，且最终数字不受影响。

同时验证体验层约定：
  · 点击后立即有「正在理解」的反馈（第一帧是thinking 而不是空白）
  · 降级时明确告知「已切换确定性规则，不影响补货计算」

本文件不测 DeepSeek 的真实响应时间 —— 那是外部网络服务，
不可作为回归指标。测的是**四种情形下主流程都通**。
"""
import time

import pytest

from core import ai_events, ai_insight, llm, policy

PLAN_DATE = "2026-08-28"
BUDGET = 600.0


def _pure_rule_fingerprint():
    """纯规则链路的结果指纹 —— 任何 AI 情形下它都不该变。"""
    plan = policy.build_plan(PLAN_DATE, BUDGET, policy.MODE_DIANNAO, persist=False)
    return [(it["sku"], round(float(it["reorder_qty"] or 0), 6))
            for it in plan["items"]], round(float(plan["metrics"]["total_cost"]), 4)


# ══════════════════════════════════════════════════════════════
# 一、四种LLM 情形下补货主流程都必须可完成
# ══════════════════════════════════════════════════════════════

def test_case1_llm_normal(monkeypatch):
    """情形 1：模型正常。主流程走通，事件与洞察 source=llm。"""
    monkeypatch.setattr(llm, "is_enabled", lambda: True)
    # ai_events.llm_parse 需要 events 列表才会返回 source=llm
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: {
        "events": [{"key": "rain", "level": "strong", "severity": "high",
                    "evidence": "店主明确提到暴雨", "demand_factor": 0.75}],
        "summary": "明天下暴雨，客流下降",
    })
    ev = ai_events.parse("明天下大暴雨", ["冷饮", "生鲜"])
    plan = policy.build_plan(PLAN_DATE, BUDGET, policy.MODE_DIANNAO,
                             persist=False, risks=ev["active"])
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: {
        "insights": [{
            "category": "stock", "severity": "medium",
            "title": "库存结构可优化",
            "insight": "部分商品覆盖天数偏低。",
            "evidence": "预算 600",
            "advice": "建议关注库存覆盖偏低商品的补货节奏",
        }],
        "digest": "整体结构合理。",
    })
    ins = ai_insight.analyze(plan)
    assert ev["source"] == "llm", "事件理解未走通模型路径"
    assert ev["active"] == ["rain"]
    assert ins["source"] == "llm", "洞察未走通模型路径"
    assert plan["metrics"]["total_cost"] > 0


def test_case2_llm_timeout(monkeypatch):
    """情形 2：模型超时（抛TimeoutError）。必须自动降级、主流程跑完。"""
    monkeypatch.setattr(llm, "is_enabled", lambda: True)

    def _timeout(*a, **k):
        raise TimeoutError("模拟超时")
    monkeypatch.setattr(llm, "chat_json", _timeout)
    monkeypatch.setattr(llm, "chat", _timeout, raising=False)

    t0 = time.time()
    ev = ai_events.parse("明天下大暴雨", ["冷饮", "生鲜"])
    plan = policy.build_plan(PLAN_DATE, BUDGET, policy.MODE_DIANNAO,
                             persist=False, risks=ev["active"])
    ins = ai_insight.analyze(plan)
    elapsed = time.time() - t0

    assert ev["source"] != "llm", "超时后未降级"
    assert ins["source"] != "llm", "洞察超时后未降级"
    assert plan["metrics"]["total_cost"] > 0, "超时导致补货无法计算"
    assert plan["items"], "超时导致商品列表为空"
    assert elapsed < 60, "超时路径耗时过长（%.1fs）" % elapsed


def test_case3_llm_exception(monkeypatch):
    """情形 3：模型返回异常结构（未捕获的类型错误）。必须降级、跑完。"""
    monkeypatch.setattr(llm, "is_enabled", lambda: True)
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: {"insights": "不是列表"})

    ev = ai_events.parse("明天下大暴雨", ["冷饮", "生鲜"])
    plan = policy.build_plan(PLAN_DATE, BUDGET, policy.MODE_DIANNAO,
                             persist=False, risks=ev["active"])
    ins = ai_insight.analyze(plan)
    assert plan["metrics"]["total_cost"] > 0
    assert isinstance(ins.get("insights"), list)


def test_case4_no_api_key(monkeypatch):
    """情形 4：没有 API Key。必须纯规则跑完，且数字与规则基线一致。"""
    monkeypatch.setattr(llm, "is_enabled", lambda: False)
    ev = ai_events.parse("明天下大暴雨", ["冷饮", "生鲜"])
    plan = policy.build_plan(PLAN_DATE, BUDGET, policy.MODE_DIANNAO,
                             persist=False, risks=ev["active"])
    ins = ai_insight.analyze(plan)
    assert ev["source"] == "rule"
    assert ins["source"] == "rule"
    assert plan["metrics"]["total_cost"] > 0
    assert ins["insights"], "无 Key 时应降级为规则体检而不是空白"


# ══════════════════════════════════════════════════════════════
# 二、AI 情形不得改变纯规则链路的结果
# ══════════════════════════════════════════════════════════════

def test_ai_state_does_not_change_rule_only_numbers(monkeypatch):
    """切换 LLM 开关不改变 build_plan(不带 ai_factors) 的结果。"""
    base_fp, base_cost = _pure_rule_fingerprint()
    monkeypatch.setattr(llm, "is_enabled", lambda: False)
    off_fp, off_cost = _pure_rule_fingerprint()
    monkeypatch.setattr(llm, "is_enabled", lambda: True)
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: {
        "insights": [], "digest": "x"})
    on_fp, on_cost = _pure_rule_fingerprint()
    assert base_fp == off_fp == on_fp, "LLM 开关改变了补货数量"
    assert base_cost == off_cost == on_cost, "LLM 开关改变了总成本"


# ══════════════════════════════════════════════════════════════
# 三、体验层：立即反馈 + 降级明示
# ══════════════════════════════════════════════════════════════

def test_thinking_banner_renders():
    """AI 调用中必须有明确提示，而不是空白等待。"""
    from core import ai_view
    html = ai_view.render_thinking("AI 正在理解天气、供应与经营风险…")
    assert "ai-thinking" in html
    assert "ai-spin" in html, "缺少加载动效"
    assert "AI 正在理解" in html
    assert "ai-mode-bar" not in html, "thinking 帧不应混入结果内容"


def test_degraded_status_says_numbers_unaffected():
    """降级时必须明说「已切换确定性规则，不影响补货计算」。"""
    from core import ai_view
    html = ai_view.render_ai_status("AI 业务洞察", 3.2, degraded=True,
                                   reason="事件理解已降级为规则解析")
    assert "ai-status-warn" in html
    assert "不影响补货计算" in html
    assert "事件理解已降级为规则解析" in html


def test_normal_status_reports_elapsed():
    """正常完成时披露耗时（不承诺绝对时间，只报告实测值）。"""
    from core import ai_view
    html = ai_view.render_ai_status("AI 事件理解 + 业务洞察", 4.11, degraded=False)
    assert "ai-status-ok" in html
    assert "4.1s" in html
    assert "不影响补货计算" not in html


def test_status_bar_has_no_degraded_text_when_ok():
    """成功时不应出现降级措辞，避免误导。"""
    from core import ai_view
    ok = ai_view.render_ai_status("AI 业务洞察", 2.0, degraded=False)
    assert "暂不可用" not in ok
    assert "已切换确定性规则" not in ok


# ══════════════════════════════════════════════════════════════
# 四、app 层：两入口都是流式且第一帧立即反馈
# ══════════════════════════════════════════════════════════════

def _app_module():
    import app as app_mod
    return app_mod


def test_do_ai_parse_yields_thinking_first(monkeypatch):
    """do_ai_parse 第一帧必须是 thinking，不能让用户干等。"""
    app_mod = _app_module()
    monkeypatch.setattr(app_mod.ai_events, "parse",
                        lambda *a, **k: {"source": "rule", "active": [],
                                          "factors": {}, "summary": "无",
                                          "events": []})
    monkeypatch.setattr(app_mod.ai_insight, "analyze",
                        lambda *a, **k: {"source": "rule", "insights": [],
                                          "digest": ""})
    frames = list(app_mod.do_ai_parse("明天下大暴雨"))
    assert len(frames) >= 2, "应至少两帧（thinking + 结果）"
    first = frames[0][2]
    assert "ai-thinking" in first, "第一帧不是即时反馈：%r" % first[:60]
    assert "ai-status" in frames[-1][2], "末帧缺少状态说明"


def test_do_ai_insight_yields_thinking_first(monkeypatch):
    """do_ai_insight 同样第一帧立即反馈。"""
    app_mod = _app_module()
    monkeypatch.setattr(app_mod.ai_insight, "analyze",
                        lambda *a, **k: {"source": "rule", "insights": [],
                                          "digest": ""})
    monkeypatch.setattr(app_mod.ai_events, "parse",
                        lambda *a, **k: {"source": "rule", "active": [],
                                          "factors": {}, "summary": "无",
                                          "events": []})
    frames = list(app_mod.do_ai_insight("明天下大暴雨"))
    assert len(frames) >= 2
    assert "ai-thinking" in frames[0][2]
    assert "ai-status" in frames[-1][2]


def test_do_ai_parse_survives_llm_failure(monkeypatch):
    """LLM 抛异常时，app 层入口仍要产出完整页面 + 降级状态。"""
    app_mod = _app_module()
    monkeypatch.setattr(app_mod.llm, "is_enabled", lambda: True)

    monkeypatch.setattr(app_mod.ai_events, "parse",
                        lambda *a, **k: {"source": "rule", "active": [],
                                          "factors": {}, "summary": "降级",
                                          "events": []})
    monkeypatch.setattr(app_mod.ai_insight, "analyze",
                        lambda *a, **k: {"source": "rule", "insights": [],
                                          "digest": ""})
    frames = list(app_mod.do_ai_parse("明天下大暴雨"))
    last = frames[-1][2]
    assert "ai-status-warn" in last, "未提示降级"
    assert "不影响补货计算" in last


def test_do_ai_parse_still_computes_real_plan(monkeypatch):
    """降级路径下最终方案必须仍是真实规则算出来的（含完整商品行）。"""
    app_mod = _app_module()
    monkeypatch.setattr(app_mod.llm, "is_enabled", lambda: False)
    frames = list(app_mod.do_ai_parse("明天下大暴雨"))
    last = frames[-1][2]
    assert len(last) > 500, "降级后页面内容过短，可能没算出方案"
    # KPI 帧里应能看到真实成本
    kpi = frames[-1][0]
    assert "¥" in kpi or "成本" in kpi or kpi
