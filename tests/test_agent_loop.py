# -*- coding: utf-8 -*-
"""Agent 自主性的**可验证**证据（ARD T-AG-04）。

═══ 为什么要专门写这一组测试 ═══
`core/agent_loop.py` 声称自己是「自主决策」而不是「流程演示」。这句话要是
不能变成会失败的断言，它就只是文案。本文件把「自主」拆成五条可检验命题：

  1. **路径分化**   —— 同一份代码，换输入 → 目标 / 策略 / 工具路径 / 置信度真的不同；
  2. **资源意识**   —— 没有民生告急时，它主动**跳过最贵**的 `assess_traffic`；
                      民生告急时，它主动**追加**这一步；
  3. **置信度真实** —— 预算越紧 → 置信度越低，而不是一个常数；
  4. **策略有效**   —— 同一批候选方案，喂给不同策略权重 → 打分/胜出者真的会变；
  5. **不依赖 LLM** —— 全程无 Key、无网络也能完整跑通；空/坏输入不崩，优雅降级。

所有断言用的都是**数据集里真实存在的日期**（2026-03-01 ~ 2026-08-27），
没有一个数字是编的；其中日期与场景的对应关系在注释里写明了诊断依据。
"""

import pytest

from core import agent_loop, tools
from core.agent_loop import AgentRunner, STRATEGIES, run_agent


# 场景锚点：来自 180 天数据的真实诊断（见 core/agent_loop.py 的诊断口径注释）
DATE_STEADY = "2026-08-11"   # 平常日：无积压压力、民生不告急
DATE_ACUTE = "2026-08-16"    # 民生偏紧日：民生最低覆盖跌破相对警戒线（会触发客流评估）
DATE_OVERSTOCK = "2026-07-27"  # 压货压力最高的一天（0.60）


# ══════════════════════════════════════════════════════════
# 0. 基本契约：能跑通、结构完整、不依赖外部
# ══════════════════════════════════════════════════════════

def test_run_agent_returns_full_structure():
    """一轮决策必须产出页面需要的全部结构，缺一即失败。"""
    r = run_agent("2026-08-27", 600, persist=False)
    for key in ("plan_date", "budget", "phases", "trace", "diagnosis", "goal",
                "plan_tasks", "strategy", "candidates", "chosen", "actions",
                "reflection", "path", "stats", "tools"):
        assert key in r, "缺少字段 %s" % key
    assert len(r["phases"]) == 5, "五阶段循环必须齐备"
    assert [p["key"] for p in r["phases"]] == [
        "perceive", "reason", "plan", "act", "reflect"]
    assert len(r["candidates"]) >= 2, "至少要有多方案的博弈空间"
    assert r["chosen"]["tag"] in {c["tag"] for c in r["candidates"]}


def test_trace_has_all_five_phases_visited():
    """轨迹里必须真实出现五个阶段的标记，不能跳阶段。"""
    r = run_agent("2026-08-27", 600, persist=False)
    visited = [e["key"] for e in r["trace"] if e.get("kind") == "phase"]
    assert visited == ["perceive", "reason", "plan", "act", "reflect"]


def test_no_llm_dependency(monkeypatch):
    """把 LLM 入口封死，Agent 仍必须完整跑通（纯规则可复现）。"""
    from core import llm

    def _boom(*a, **k):
        raise AssertionError("Agent 决策不应触碰 LLM")

    for name in ("chat", "complete", "ask", "call", "client", "available"):
        if hasattr(llm, name):
            monkeypatch.setattr(llm, name, _boom, raising=False)
    r = run_agent("2026-08-27", 600, persist=False)
    assert r["chosen"], "关掉 LLM 后仍应有胜出方案"


def test_deterministic_same_input_same_output():
    """同输入必得同输出：跑两遍，路径摘要与得分必须逐字一致。"""
    a = run_agent("2026-08-27", 600, persist=False)
    b = run_agent("2026-08-27", 600, persist=False)
    assert a["path"] == b["path"]
    assert [c["score"] for c in a["candidates"]] == [c["score"] for c in b["candidates"]]
    assert a["diagnosis"] == b["diagnosis"]


@pytest.mark.parametrize("bad", ["", "not-a-date", "2026-13-45", None, "2026-08-27"])
def test_bad_input_degrades_gracefully(bad):
    """坏输入不能把整个循环炸掉 —— 要么正常出结果，要么抛可读异常。"""
    try:
        r = run_agent(bad, 600, persist=False)
        assert r["goal"], "即使日期不标准也应有目标"
    except Exception as exc:  # noqa: BLE001
        assert str(exc), "异常必须带可读信息，不能是空异常"


@pytest.mark.parametrize("budget", [0, -100, 1e9])
def test_extreme_budget_does_not_crash(budget):
    """极端预算（0 / 负数 / 超大）都必须能跑完，策略与胜出仍然成立。"""
    r = run_agent("2026-08-27", budget, persist=False)
    assert r["strategy"]["key"] in STRATEGIES
    assert r["chosen"]["tag"]


# ══════════════════════════════════════════════════════════
# 1. 路径分化：同一份代码，换输入 → 走出不同的路
# ══════════════════════════════════════════════════════════

def test_goal_diverges_across_scenarios():
    """目标必须随情境分化 —— 至少三种不同目标在真实数据上可触发。"""
    goals = {
        "steady": run_agent(DATE_STEADY, 1500, persist=False)["goal"]["key"],
        "tight": run_agent(DATE_STEADY, 250, persist=False)["goal"]["key"],
        "acute": run_agent(DATE_ACUTE, 600, persist=False)["goal"]["key"],
        "overstock": run_agent(DATE_OVERSTOCK, 600, persist=False)["goal"]["key"],
    }
    assert len(set(goals.values())) >= 3, (
        "目标没有分化，Agent 是「假自主」：%s" % goals)
    assert goals["acute"] == "save_livelihood"
    assert goals["overstock"] == "clear_overstock"
    assert goals["tight"] == "spend_wisely"
    assert goals["steady"] == "steady"


def test_strategy_diverges_and_matches_goal():
    """策略必须跟着目标走，四个策略在真实场景里都能被选中。"""
    cases = [
        (DATE_ACUTE, 600, "livelihood_first"),
        (DATE_OVERSTOCK, 600, "risk_averse"),
        (DATE_STEADY, 250, "profit_oriented"),
        (DATE_STEADY, 1500, "balanced"),
    ]
    got = {}
    for d, b, want in cases:
        k = run_agent(d, b, persist=False)["strategy"]["key"]
        got[(d, b)] = k
        assert k == want, "目标→策略映射断了：%s ¥%s 得到 %s，应为 %s" % (d, b, k, want)
    assert len(set(got.values())) == 4, "四个策略应当都被真实触发过：%s" % got


def test_confidence_is_not_a_constant():
    """置信度必须真实浮动（证据/预算不同 → 置信度不同）。"""
    confs = [
        run_agent(DATE_STEADY, 1500, persist=False)["reflection"]["confidence"],
        run_agent(DATE_ACUTE, 250, persist=False)["reflection"]["confidence"],
        run_agent(DATE_OVERSTOCK, 600, persist=False)["reflection"]["confidence"],
    ]
    assert len(set(confs)) >= 2, "置信度是个常数，说明它没有真实推导：%s" % confs
    for c in confs:
        assert 0.0 < c <= 1.0


def test_path_summary_differs_between_inputs():
    """路径摘要（页面底部那句对比）必须因输入而不同。"""
    a = run_agent(DATE_STEADY, 1500, persist=False)["path"]
    b = run_agent(DATE_ACUTE, 600, persist=False)["path"]
    assert (a["goal"], a["strategy"], a["traffic_assessed"]) != \
           (b["goal"], b["strategy"], b["traffic_assessed"]), \
        "换了个真实场景，路径却一模一样：%s vs %s" % (a, b)


# ══════════════════════════════════════════════════════════
# 2. 资源意识：跳过最贵的工具 / 需要时才花代价
# ══════════════════════════════════════════════════════════

def _traffic_calls(r):
    return [c for c in r["trace"] if c.get("kind") == "call"
            and c.get("tool") == "assess_traffic"]


def test_skips_expensive_tool_when_not_needed():
    """没有民生告急时，必须主动跳过最贵的 assess_traffic，并在轨迹里说明理由。"""
    r = run_agent(DATE_STEADY, 1500, persist=False)
    assert r["diagnosis"]["livelihood_stockout"] == 0
    assert _traffic_calls(r) == [], "不该在无告急时还去跑最贵的客流评估"
    skip_notes = [e for e in r["trace"]
                  if e.get("kind") == "think" and "跳过" in (e.get("title") or "")]
    assert skip_notes, "跳过最贵工具必须留下解释，不能默默不调"


def test_calls_expensive_tool_when_acute():
    """民生告急时，必须主动追加 assess_traffic —— 该花的代价要花。"""
    r = run_agent(DATE_ACUTE, 600, persist=False)
    assert r["diagnosis"]["livelihood_stockout"] > 0
    assert _traffic_calls(r), "民生告急却不评估客流影响，属于该做没做"


def test_tool_costs_are_real_and_catalogued():
    """工具元数据必须齐备：名称/分类/成本都要真实登记，成本只用三档。"""
    cat = tools.tool_catalog()
    assert len(cat) >= 10, "工具层过于单薄"
    for t in cat:
        assert t["name"] and t["desc"]
        assert t["category"] in tools.CATEGORIES
        assert t["cost"] in tools.COST_LEVELS
    assert "assess_traffic" in {t["name"] for t in cat}
    expensive = {t["name"] for t in cat if t["cost"] == "高"}
    assert "assess_traffic" in expensive, "客流评估应当被登记为高成本"


def test_acutely_scenario_uses_more_tools_than_steady_is_not_required():
    """资源意识不等于「一律少调」：告急场景允许调用更多工具（代价换信息）。"""
    steady = run_agent(DATE_STEADY, 1500, persist=False)["stats"]["tool_calls"]
    acute = run_agent(DATE_ACUTE, 600, persist=False)["stats"]["tool_calls"]
    # 不强制大小关系（避免把「必须多调」写成硬规则），但两者都应为正
    assert steady > 0 and acute > 0
    # 告急场景确实把最贵那一步加上去了
    assert acute >= steady


# ══════════════════════════════════════════════════════════
# 3. 策略真的在影响决策（打分器的有效性）
# ══════════════════════════════════════════════════════════

def _build_three_candidates(plan_date="2026-08-27", budget=600.0):
    """复刻 act() 的三套候选，供打分器做「换策略→换胜出者」的对照实验。"""
    a = tools.call_tool("build_replenishment", plan_date=plan_date, budget=budget,
                        protect_livelihood=True, risks=[])["result"]
    b = tools.call_tool("build_replenishment", plan_date=plan_date, budget=budget,
                        protect_livelihood=False, risks=[], use_memory=False)["result"]
    c = tools.call_tool("build_replenishment", plan_date=plan_date, budget=budget,
                        protect_livelihood=True, risks=[], day_scale=0.70)["result"]
    out = []
    for tag, cand in (("A", a), ("B", b), ("C", c)):
        sim = tools.call_tool("simulate_plan", plan=cand["plan"], horizon_days=3)["result"]
        out.append((tag, cand["plan"]["metrics"], sim))
    return out


def test_scorer_is_strategy_sensitive():
    """同一批候选，换策略 → 至少有一个候选的得分发生变化。

    这是「策略不是装饰」的底线证据。注意：本数据集里惠民约束几乎不牺牲毛利，
    所以 A 常常在所有策略下都占优 —— **胜出者不必分化**，但得分必须随权重变化。
    """
    runner = AgentRunner("2026-08-27", 600)
    cands = _build_three_candidates()
    totals = {k: [runner._score(m, s, st)["total"] for _, m, s in cands]
              for k, st in STRATEGIES.items()}
    # 四个策略里，至少存在两个策略给出不同的分数向量
    vectors = {tuple(round(v, 4) for v in vals) for vals in totals.values()}
    assert len(vectors) >= 2, "权重换了但得分纹丝不动，打分器没在用权重：%s" % totals


def test_livelihood_priority_raises_livelihood_contribution():
    """惠民优先给「保民生」的权重最高 —— 同一候选，民生项在总分里的贡献更大。

    `breakdown` 存的是**已加权**的贡献（权重 × 目标分），`parts` 才是归一化后的
    原始目标分；这里要验的是权重真的进了总分。
    """
    runner = AgentRunner("2026-08-27", 600)
    cands = _build_three_candidates()
    # 找保障率最低的候选（纯利润版通常最低）
    worst = min(cands, key=lambda x: float(x[1].get("livelihood_secured_rate") or 0))
    liv = runner._score(worst[1], worst[2], STRATEGIES["livelihood_first"])
    pro = runner._score(worst[1], worst[2], STRATEGIES["profit_oriented"])
    # 原始目标分与策略无关，必须一致（同一候选、同一沙盘）
    assert liv["parts"] == pro["parts"]
    # 但「保民生」被加权后的贡献不同：惠民优先(0.55) 应大于收益优先(0.25)
    assert liv["breakdown"]["保民生"] > pro["breakdown"]["保民生"]
    # 且总分不同 —— 策略真的改变了结论
    assert liv["total"] != pro["total"]


def test_score_breakdown_has_three_objectives():
    """打分必须真的是三目标加权，明细要对得上账。"""
    runner = AgentRunner("2026-08-27", 600)
    cands = _build_three_candidates()
    _, m, s = cands[0]
    sc = runner._score(m, s, STRATEGIES["balanced"])
    assert set(sc["breakdown"]) == {"收益", "抗风险", "保民生"}
    assert set(sc["parts"]) == {"margin_score", "resilience_score", "livelihood_score"}
    # breakdown 是已加权贡献，三项相加必须等于总分
    manual = sum(sc["breakdown"].values())
    assert abs(manual - sc["total"]) < 0.05, (
        "明细三项之和对不上总分：%s vs %s" % (manual, sc["total"]))
    # 再验一层：breakdown = 权重 × parts
    w = STRATEGIES["balanced"]["weights"]
    assert abs(sc["breakdown"]["收益"] - w["margin"] * sc["parts"]["margin_score"]) < 0.02
    assert abs(sc["breakdown"]["抗风险"]
               - w["resilience"] * sc["parts"]["resilience_score"]) < 0.02
    assert abs(sc["breakdown"]["保民生"]
               - w["livelihood"] * sc["parts"]["livelihood_score"]) < 0.02


# ══════════════════════════════════════════════════════════
# 4. 反思：自评与改进项是真的、可执行的
# ══════════════════════════════════════════════════════════

def test_reflection_confidence_parts_sum_sensibly():
    r = run_agent(DATE_ACUTE, 250, persist=False)
    parts = r["reflection"]["confidence_parts"]
    assert set(parts) == {"evidence", "reliability", "budget"}
    for v in parts.values():
        assert 0.0 <= v <= 1.0
    assert r["reflection"]["confidence"] >= 0.30


def test_budget_hardening_lowers_confidence():
    """同样场景，预算越紧 → 置信度不应更高（钱不够时结论更没底）。"""
    loose = run_agent(DATE_ACUTE, 2400, persist=False)["reflection"]["confidence"]
    tight = run_agent(DATE_ACUTE, 250, persist=False)["reflection"]["confidence"]
    assert tight <= loose + 1e-9, "预算更紧置信度反而更高，自评不诚实"


def test_reflection_has_critiques_and_next_actions():
    """自我批评与下一轮改进项必须非空、且带可读说明。"""
    r = run_agent(DATE_ACUTE, 250, persist=False)
    crit = r["reflection"]["critiques"]
    nxt = r["reflection"]["next_actions"]
    assert crit and all(c.get("title") and c.get("detail") for c in crit)
    assert nxt and all(a.get("action") and a.get("detail") for a in nxt)
    # 每轮必做的闭环入口必须始终在
    assert any("录入" in a["action"] for a in nxt)


def test_failed_tool_is_recorded_not_swallowed(monkeypatch):
    """工具失败必须被如实记录并进入反思，不能静默吞掉（铁律 2）。"""
    from core import tools as _tools

    real = _tools.call_tool

    def flaky(name, **kw):
        if name == "assess_traffic":
            return {"ok": False, "result": None, "error": "RuntimeError: 模拟失败",
                    "elapsed_ms": 0.1}
        return real(name, **kw)

    # run_agent 内部经 tools.call_tool；打桩让最贵那一步必失败
    monkeypatch.setattr(_tools, "call_tool", flaky)
    r = run_agent(DATE_ACUTE, 600, persist=False)
    failed = [c for c in r["trace"] if c.get("kind") == "call" and not c.get("ok")]
    assert failed, "工具失败了却没留下记录"
    # 整个循环仍应产出结论（可降级）
    assert r["chosen"] and r["strategy"]


# ══════════════════════════════════════════════════════════
# 5. 轨迹与页面的契约
# ══════════════════════════════════════════════════════════

def test_every_tool_call_has_why_and_meta():
    """每一次工具调用都要带「为什么调它」与分类/成本，页面才讲得清。"""
    r = run_agent(DATE_ACUTE, 600, persist=False)
    calls = [c for c in r["trace"] if c.get("kind") == "call"]
    assert calls
    for c in calls:
        assert c.get("why"), "工具 %s 没写为什么调它" % c.get("tool")
        assert c.get("category") in tools.CATEGORIES
        assert c.get("cost") in tools.COST_LEVELS
        assert isinstance(c.get("elapsed_ms"), (int, float))


def test_stats_are_consistent():
    r = run_agent(DATE_ACUTE, 600, persist=False)
    st = r["stats"]
    calls = [c for c in r["trace"] if c.get("kind") == "call"]
    assert st["tool_calls"] == len(calls)
    assert st["failed_calls"] == sum(1 for c in calls if not c["ok"])
    assert st["total_steps"] == sum(
        1 for e in r["trace"] if e.get("kind") == "think")
