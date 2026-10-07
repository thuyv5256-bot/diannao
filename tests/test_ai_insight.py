# -*- coding: utf-8 -*-
"""AI 决策中枢 · 第二环（core/ai_insight.py）测试。

这一环回答的是「这次决策有什么问题」，与第一环（向前看事件）互补。
铁律只有一条：**只指出问题 + 给建议，绝不改数字**。

覆盖：
  1. 无 Key / 模型输出不可用时降级到纯规则体检
  2. 防幻觉校验：evidence 里的数字必须在事实清单中真实存在
  3. 字段白名单 + 枚举合法 + 去重 + 截断
  4. 洞察是只读的——调用前后方案数字必须完全不变

mock 层级同 test_ai_events：patch `llm.chat_json`（模型出口），
让 `llm_insight` 内部的真实校验链跑起来。
"""

import copy

import pytest

from core import ai_insight, llm, policy

PLAN_DATE = "2026-08-28"
BUDGET = 1200.0


def _plan(**kw):
    return policy.build_plan(PLAN_DATE, BUDGET, policy.MODE_DIANNAO, persist=False, **kw)


def _no_model(monkeypatch):
    monkeypatch.setattr(llm, "is_enabled", lambda: False)


def _fake_model(monkeypatch, payload):
    monkeypatch.setattr(llm, "is_enabled", lambda: True)
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: payload)


def _qty_fingerprint(plan):
    return [(it["sku"], round(float(it["reorder_qty"] or 0), 6)) for it in plan["items"]]


# ─────────────────────────────────────────── 事实清单

def test_build_facts_mentions_budget_and_items():
    facts = ai_insight.build_facts(_plan())
    assert "预算" in facts
    assert "商品" in facts or "SKU" in facts.upper()
    assert len(facts) > 100


def test_build_facts_handles_empty_plan():
    """空方案不能崩，产出的是一句「无可分析」。"""
    assert ai_insight.build_facts({})


def test_build_facts_includes_extra_context():
    facts = ai_insight.build_facts(_plan(), {"AI 事件理解": "暴雨，证据充分"})
    assert "暴雨" in facts


# ─────────────────────────────────────────── 规则体检（永远可用）

def test_rule_insight_on_real_plan():
    r = ai_insight.rule_insight(_plan())
    assert r["source"] == "rule"
    assert isinstance(r["insights"], list)
    assert r["digest"]


def test_rule_insight_on_empty_plan_is_safe():
    r = ai_insight.rule_insight({})
    assert r["insights"] == []


def test_rule_insight_items_are_well_formed():
    """每条洞察都必须字段齐全、枚举合法 —— 页面直接消费这些字段。"""
    for it in ai_insight.rule_insight(_plan())["insights"]:
        assert it["category"] in {"demand", "stock", "profit", "liveliness", "supply"}
        assert it["severity"] in ai_insight.SEVERITIES
        assert it["title"] and it["insight"]


def test_rule_insight_is_read_only():
    """规则洞察绝不能碰方案数字。"""
    plan = _plan()
    before = _qty_fingerprint(plan)
    ai_insight.rule_insight(plan)
    assert _qty_fingerprint(plan) == before


# ─────────────────────────────────────────── 降级路径

def test_analyze_without_key_falls_back_to_rule(monkeypatch):
    _no_model(monkeypatch)
    r = ai_insight.analyze(_plan())
    assert r["source"] == "rule"
    assert r["facts"], "降级路径也必须附上事实清单（页面要显示给评委看）"


@pytest.mark.parametrize("bad", [None, {}, {"insights": "不是列表"}, [1, 2]])
def test_analyze_falls_back_on_bad_model_output(monkeypatch, bad):
    """模型输出不可用时必须降级，而不是抛异常把页面搞挂。"""
    _fake_model(monkeypatch, bad)
    r = ai_insight.analyze(_plan())
    assert r["source"] == "rule"


def test_analyze_uses_model_when_available(monkeypatch):
    _fake_model(monkeypatch, {
        "digest": "整体结构尚可，但要留意积压。",
        "insights": [{
            "category": "stock", "severity": "medium",
            "title": "有几个商品覆盖天数偏短",
            "insight": "这些商品随时可能断货。",
            "evidence": "预算 1200",
            "advice": "优先补这几个",
        }],
    })
    r = ai_insight.analyze(_plan())
    assert r["source"] == "llm"
    assert r["model"]
    assert r["insights"]


# ─────────────────────────────────────────── 防幻觉：evidence 必须落在事实里

def test_insight_with_fabricated_numbers_is_dropped(monkeypatch):
    """编造的数字（如毛利提升 37%）必须整条丢弃 —— 这是防幻觉的关键闸门。"""
    facts = ai_insight.build_facts(_plan())
    _fake_model(monkeypatch, {
        "digest": "x",
        "insights": [{
            "category": "profit", "severity": "high",
            "title": "毛利大幅提升",
            "insight": "换了这个策略毛利提升 37%。",
            "evidence": "毛利提升 37%，客单价提升 12%",   # 全部是编的
            "advice": "继续保持",
        }],
    })
    r = ai_insight.analyze(_plan())
    assert all("毛利大幅提升" != i["title"] for i in r["insights"])


def test_insight_with_real_numbers_survives(monkeypatch):
    """依据里用了真实存在的数字才允许输出。"""
    plan = _plan()
    facts = ai_insight.build_facts(plan)
    import re
    real = re.findall(r"\d+(?:\.\d+)?", facts)
    assert real, "事实清单里应当有数字"
    _fake_model(monkeypatch, {
        "digest": "x",
        "insights": [{
            "category": "profit", "severity": "medium",
            "title": "预算利用情况",
            "insight": "本次预算的使用值得复核。",
            "evidence": "预算 %s" % real[0],
            "advice": "复核预算设置",
        }],
    })
    r = ai_insight.analyze(plan)
    assert any(i["title"] == "预算利用情况" for i in r["insights"])


def test_sanitize_rejects_non_dict_entries():
    out = ai_insight._sanitize(["字符串", None, 42, {"title": "", "insight": ""}], "预算 1200")
    assert out == []


def test_sanitize_dedupes_by_title_prefix():
    """去重键是标题前 20 字 —— 前缀相同的重复项只留一条。"""
    items = [{"title": "断货风险集中在几个高流转商品上", "insight": "a", "evidence": ""},
             {"title": "断货风险集中在几个高流转商品上", "insight": "b", "evidence": ""},
             {"title": "预算没用满有闲置资金", "insight": "c", "evidence": ""}]
    out = ai_insight._sanitize(items, "预算 1200")
    titles = [i["title"] for i in out]
    assert len(out) == 2
    assert titles.count("断货风险集中在几个高流转商品上") == 1


def test_sanitize_caps_output_length():
    items = [{"title": "T%d" % i, "insight": "x" * 500, "evidence": ""} for i in range(20)]
    out = ai_insight._sanitize(items, "预算 1200")
    assert len(out) <= 6
    assert all(len(i["insight"]) <= 200 for i in out)
    assert all(len(i["title"]) <= 40 for i in out)


def test_sanitize_normalizes_bad_enums():
    """非法枚举归一到合法值，不让脏数据进页面。"""
    out = ai_insight._sanitize(
        [{"title": "T", "insight": "x", "evidence": "",
          "category": "外星类别", "severity": "巨严重"}], "预算 1200")
    assert out[0]["category"] == "stock"
    assert out[0]["severity"] == "medium"


def test_sanitize_handles_empty_input():
    assert ai_insight._sanitize(None, "预算 1200") == []
    assert ai_insight._sanitize([], "") == []


# ─────────────────────────────────────────── 核心断言：洞察不改数字

def test_analyze_does_not_mutate_the_plan(monkeypatch):
    """AI 体检是只读的：调用前后方案的补货数量必须逐位一致。"""
    _fake_model(monkeypatch, {
        "digest": "建议调高预算",
        "insights": [{"category": "profit", "severity": "high",
                      "title": "预算没用满", "insight": "有钱没花出去",
                      "evidence": "预算 1200", "advice": "上调预算"}],
    })
    plan = _plan()
    snapshot = copy.deepcopy(plan)
    ai_insight.analyze(plan)
    assert _qty_fingerprint(plan) == _qty_fingerprint(snapshot)
    assert plan.get("items") == snapshot.get("items")


def test_insight_output_has_no_mutating_api():
    """洞察结果里不允许出现任何能反写方案的字段。"""
    r = ai_insight.analyze(_plan())
    for banned in ("items", "reorder_qty", "order", "apply", "patch", "budget"):
        assert banned not in r
    for it in r["insights"]:
        for banned in ("reorder_qty", "daily_demand", "budget", "factor"):
            assert banned not in it


def test_extra_does_not_change_decision_numbers():
    """extra 只是给模型看的上下文，不能影响方案。"""
    plan_a = _plan()
    plan_b = _plan()
    ai_insight.analyze(plan_a, {"AI 事件理解": "暴雨"})
    assert _qty_fingerprint(plan_a) == _qty_fingerprint(plan_b)


# ─────────────────────────────────────────── 健壮性

def test_analyze_on_empty_plan_does_not_crash(monkeypatch):
    _fake_model(monkeypatch, {"digest": "x", "insights": []})
    r = ai_insight.analyze({})
    assert isinstance(r["insights"], list)


def test_digest_always_present(monkeypatch):
    """digest 为空时要有兜底文案，不能给页面留空。"""
    _fake_model(monkeypatch, {"insights": []})
    assert ai_insight.analyze(_plan())["digest"]


@pytest.mark.parametrize("extra", [None, {}, {"a": 1}, {"AI 事件理解": ""}])
def test_extra_variants_are_safe(monkeypatch, extra):
    _no_model(monkeypatch)
    assert ai_insight.analyze(_plan(), extra)["source"] == "rule"


# ══════════════════════════════════════════════════════════════
# 防幻觉加固：实体 + 指标 + 数字 三者绑定
# ══════════════════════════════════════════════════════════════
# 旧校验只做「evidence里的数字 ∈ facts 里的数字」，是个扁平集合，
# 丢掉了「这个数字属于哪个商品」的信息 —— 于是模型可以「借数字」：
#   facts 里矿泉水是 12、牛奶是 30
#   模型说「牛奶只剩 12 件」→ 12 确实在 facts 里 → 旧校验放行
# 下面 6 个用例逐条钉死这个漏洞。


def _idx():
    plan = _plan()
    facts = ai_insight.build_facts(plan)
    names = [str(it.get("name") or "").strip() for it in plan["items"]]
    return plan, facts, names, ai_insight._build_fact_index(facts, names)


def test_fact_index_binds_entity_metric_value():
    """结构化索引必须能定位「某个商品的某个指标」的具体数值。"""
    _plan_, facts, names, idx = _idx()
    assert idx, "索引不应为空（build_facts 每行都带【标签】+数据）"
    for name, metrics in idx.items():
        assert name in names
        for m, v in metrics.items():
            assert isinstance(v, float)
    # 至少有一个实体同时具备「现有」与「够」两个指标
    has_both = [n for n, m in idx.items() if "现有" in m and "够" in m]
    assert has_both, "至少应有一个商品能同时解析出现有库存与覆盖天数"


def test_attack_a_correct_entity_metric_value_survives(monkeypatch):
    """A. 正确商品 + 正确指标 + 正确数字 → 必须放行（防止过度过滤）。"""
    plan, facts, names, idx = _idx()
    # 找一个有「现有」的真实商品
    target = next(n for n, m in idx.items() if "现有" in m)
    val = idx[target]["现有"]
    _fake_model(monkeypatch, {
        "digest": "x",
        "insights": [{
            "category": "stock", "severity": "medium",
            "title": "%s 库存偏低" % target,
            "insight": "%s 现有库存只有 %.0f，需要关注补货节奏。" % (target, val),
            "evidence": "%s 现有%.0f" % (target, val),
            "advice": "尽快补货",
        }],
    })
    r = ai_insight.analyze(plan)
    assert any("%s 库存偏低" % target == i["title"] for i in r["insights"]), \
        "正确的洞察被误杀了（过度过滤）"


def test_attack_b_right_number_wrong_entity_dropped(monkeypatch):
    """B. 正确数字但错误商品 → 必须丢弃（这是本轮修复的核心漏洞）。"""
    plan, facts, names, idx = _idx()
    src = next(n for n, m in idx.items() if "现有" in m and m["现有"] > 0)
    val = idx[src]["现有"]
    # 找一个与src 数值不同的实体作为「冒名者」
    other = next((n for n, m in idx.items()
                  if n != src and "现有" in m and abs(m["现有"] - val) > 1e-6), None)
    if other is None:
        pytest.skip("当前数据里找不到数值不同的第二个实体")
    _fake_model(monkeypatch, {
        "digest": "x",
        "insights": [{
            "category": "stock", "severity": "high",
            "title": "%s 库存告急" % other,
            "insight": "%s 现有库存仅 %.0f 件。" % (other, val),
            # 数字属于 src，却挂在 other 名下 → 借数字
            "evidence": "%s 现有%.0f" % (other, val),
            "advice": "立即补货",
        }],
    })
    r = ai_insight.analyze(plan)
    assert not any("%s 库存告急" % other == i["title"] for i in r["insights"]), \
        "借用了别的商品数字的洞察没有被丢弃"


def test_attack_c_right_entity_and_number_wrong_metric_dropped(monkeypatch):
    """C. 正确商品 + 正确数字但错误指标 → 数字对不上任何指标就该丢。"""
    plan, facts, names, idx = _idx()
    target = next(n for n, m in idx.items() if "够" in m)
    real_cover = idx[target]["够"]
    # 凭空造一个该商品并不存在的指标值
    fake = round(real_cover + 7.77, 2)
    _fake_model(monkeypatch, {
        "digest": "x",
        "insights": [{
            "category": "stock", "severity": "high",
            "title": "%s 库存周转异常" % target,
            "insight": "%s 的库存周转天数是 %.2f 天，严重偏高。" % (target, fake),
            "evidence": "%s 周转%.2f天" % (target, fake),
            "advice": "压缩库存",
        }],
    })
    r = ai_insight.analyze(plan)
    assert not any("%s 库存周转异常" % target == i["title"] for i in r["insights"]), \
        "该商品不存在的指标数值被放行了"


def test_attack_d_number_absent_from_facts_dropped(monkeypatch):
    """D. facts 中完全不存在的数字 → 必须丢弃。"""
    plan, facts, names, idx = _idx()
    _fake_model(monkeypatch, {
        "digest": "x",
        "insights": [{
            "category": "profit", "severity": "high",
            "title": "毛利率大幅提升",
            "insight": "换了这个策略毛利率提升 37%。",
            "evidence": "毛利率提升 37%，客单价提升 12%",
            "advice": "继续保持",
        }],
    })
    r = ai_insight.analyze(plan)
    assert not any(i["title"] == "毛利率大幅提升" for i in r["insights"])


def test_attack_e_memory_number_cannot_be_borrowed(monkeypatch):
    """E. Memory 里存在相同数字，但当前商品事实不支持 → 必须丢弃。

    复现原 bug：Memory 播种后 facts 的数字集合变大，
    模型只要引用一个「恰好在 facts 里」的别的数字就能绕过旧校验。
    """
    plan, facts, names, idx = _idx()
    all_vals = {v for m in idx.values() for v in m.values()}
    # 找一个「存在于 facts 数字集合、但不属于任何商品指标」的数字
    import re as _re
    loose = {float(x) for x in _re.findall(r"\d+(?:\.\d+)?", facts)} - all_vals
    target = next((n for n, m in idx.items() if m), None)
    if not loose or target is None:
        pytest.skip("当前 facts 里没有可借的松散数字")
    borrowed = sorted(loose)[0]
    _fake_model(monkeypatch, {
        "digest": "x",
        "insights": [{
            "category": "stock", "severity": "high",
            "title": "%s 库存吃紧" % target,
            "insight": "%s 现有库存只有 %.0f。" % (target, borrowed),
            "evidence": "%s 现有%.0f" % (target, borrowed),
            "advice": "尽快补货",
        }],
    })
    r = ai_insight.analyze(plan)
    assert not any("%s 库存吃紧" % target == i["title"] for i in r["insights"]), \
        "借用了无归属数字的洞察没有被丢弃"


def test_attack_f_units_are_not_interchangeable(monkeypatch):
    """F. 单位不能互相冒用：天数不能当件数、百分比不能当件数。"""
    plan, facts, names, idx = _idx()
    target = next(n for n, m in idx.items() if "够" in m)
    cover = idx[target]["够"]
    # 把「覆盖天数 3.0」说成「库存件数 3.0」—— 语义完全错位
    _fake_model(monkeypatch, {
        "digest": "x",
        "insights": [{
            "category": "stock", "severity": "medium",
            "title": "%s 仅剩少量库存" % target,
            "insight": "%s 库存仅 %.0f 件，支撑不了几天。" % (target, cover),
            "evidence": "%s 现有%.0f件" % (target, cover),
            "advice": "补货",
        }],
    })
    r = ai_insight.analyze(plan)
    # 该商品若「现有」恰好等于覆盖天数，说明数据巧合，测试无意义
    if "现有" in idx[target] and abs(idx[target]["现有"] - cover) < 1e-6:
        pytest.skip("该商品的现有库存恰好等于覆盖天数，无法区分单位")
    assert not any("%s 仅剩少量库存" % target == i["title"] for i in r["insights"]), \
        "把覆盖天数当成库存件数放行了"


def test_no_over_filtering_real_insights_survive(monkeypatch):
    """防过度过滤：多条真实、有明确数字依据的洞察必须都能显示。"""
    plan, facts, names, idx = _idx()
    items = []
    for i, (n, m) in enumerate(list(idx.items())[:3]):
        metric = "现有" if "现有" in m else list(m.keys())[0]
        val = m[metric]
        items.append({
            "category": "stock", "severity": "medium",
            "title": "真实洞察%d" % i,
            "insight": "%s 的%s是 %.0f。" % (n, metric, val),
            "evidence": "%s %s%.0f" % (n, metric, val),
            "advice": "关注",
        })
    _fake_model(monkeypatch, {"digest": "x", "insights": items})
    r = ai_insight.analyze(plan)
    kept = {i["title"] for i in r["insights"]}
    for i in range(len(items)):
        assert "真实洞察%d" % i in kept, "有真实依据的洞察被误杀了"


def test_weak_fallback_when_no_item_names(monkeypatch):
    """拿不到商品名时退化为旧的扁平校验（不崩、不误杀）。"""
    _fake_model(monkeypatch, {
        "digest": "x",
        "insights": [{
            "category": "profit", "severity": "medium",
            "title": "预算利用情况",
            "insight": "本次预算的使用值得复核。",
            "evidence": "预算 1200",
            "advice": "复核预算设置",
        }],
    })
    out = ai_insight._sanitize(
        [{"title": "T", "insight": "x", "evidence": "预算 1200"}],
        "【本次决策】预算 ¥1200，实际花费 ¥1200", [])
    assert len(out) == 1, "没有商品名时应退化为扁平校验，而不是全丢"


# ══════════════════════════════════════════════════════════════
# advice 权限边界：AI 不能冒充最终补货决策器
# ══════════════════════════════════════════════════════════════
# 最终进货数量由 R³ 在预算、库存与民生约束下算出。advice 只是一句经营提醒。
# 修复前 _sanitize 对 advice 只做 str()[:60] 截断，零内容校验 ——
# 实测真实 DeepSeek 输出过「立即补订酱油18瓶、食醋13瓶」这种具体采购数量。
# 下面 A~G 逐条钉死这条权限边界。
#
# 注意：这里不禁止所有数字，只拦「越权句式」；
# 合法的经营建议（「覆盖 2 天」「关注补货风险」）必须原样保留。

ATTACK_ADVICES = [
    # A. 建议具体最终采购数量
    ("建议进货500件", "direct_qty"),
    ("立即补订酱油18瓶、食醋13瓶，确保覆盖3天需求。", "direct_qty"),
    ("棒棒糖补30盒", "direct_qty"),
    # B. 建议修改 / 突破当前预算
    ("把预算提高到10000元", "budget"),
    ("把预算改成10000元", "budget"),
    ("建议将预算上调到 8000 元以提高毛利", "budget"),
    # C. 建议关闭或绕过民生约束
    ("忽略民生保障", "livelihood"),
    ("不用管民生约束，优先利润", "livelihood"),
    # D. 建议关闭或绕过 R³ / 覆盖最终结果
    ("关闭R³约束", "solver"),
    ("不用R³，直接按我的建议采购", "solver"),
    ("直接覆盖R³结果", "solver"),
    # E. 把预测性判断描述成既成事实
    ("明天下雨，鸡蛋一定会断货", "false_fact"),
    ("鸡蛋已经断货了", "false_fact"),
]

LEGIT_ADVICES = [
    # F. 正常经营建议
    "牛奶库存覆盖天数偏低，建议关注补货风险。",
    "建议每日在「今天生意怎么样」录一次反馈，两个月后效果会明显",
    "下次把这类商品的补货量下调一档",
    # G. 正常风险提醒（含数字但不含具体采购数量）
    "暴雨可能导致晚间客流下降，可关注饮料和生鲜需求变化。",
    "供应商D存在断供风险，建议提前确认到货情况。",
    "当前预算使用率已超 90%，可留意下次的资金安排",
    "紧急补货大米，建议至少备足2天销量。",
    "调整采购比例，优先保障民生商品3天覆盖。",
]


@pytest.mark.parametrize("text,cat", ATTACK_ADVICES)
def test_advice_overreach_attacks_are_blocked(text, cat):
    """A~E：越权 advice 必须被识别并拦截。"""
    hits = ai_insight.advice_overreach(text)
    assert cat in hits, f"未识别出 {cat} 类越权：{text!r}（命中 {hits}）"
    safe = ai_insight._sanitize_advice(text)
    assert safe != text, "越权 advice 未被替换"
    assert "优化器" in safe, "替换文案应说明决策由优化器计算"


@pytest.mark.parametrize("text", LEGIT_ADVICES)
def test_legit_advice_survives(text):
    """F~G：正常经营建议与风险提醒必须原样保留（防过度过滤）。"""
    assert ai_insight.advice_overreach(text) == [], \
        f"合法建议被误杀：{text!r}（命中 {ai_insight.advice_overreach(text)}）"
    assert ai_insight._sanitize_advice(text) == text[:60], "合法 advice 应原样保留"


def test_advice_overreach_covers_real_model_output():
    """回归实测：真实 DeepSeek 曾输出「立即补订酱油18瓶」，必须被拦。"""
    real = "立即补订酱油18瓶、食醋13瓶，确保覆盖3天需求。"
    assert "direct_qty" in ai_insight.advice_overreach(real)
    # 同句中「覆盖3天需求」本身是合法的经营提醒，不能因此整条被丢
    assert "覆盖3天" in ai_insight._sanitize_advice(
        "补订酱油，确保覆盖3天需求。")


def _real_stock_case():
    """从**当前真实 facts** 里挑一个确实存在、且带「现有」指标的商品。

    修复前这个用例硬编码「酱油」—— 它不在正式 50 SKU 里，
    导致 evidence 绑定校验先把整条拦下，测试只能 skip，
    于是「越权 advice 被替换但 insight/evidence 保留」这条从未真正验证过。
    现在改为动态选取，任何商品数据变化都不会再退化成 skip。
    """
    plan = _plan()
    facts = ai_insight.build_facts(plan)
    names = [str(it.get("name") or "").strip() for it in plan["items"]]
    idx = ai_insight._build_fact_index(facts, names)
    for name, metrics in sorted(idx.items()):
        if "现有" in metrics and float(metrics["现有"]) >= 0:
            return plan, name, float(metrics["现有"]), metrics
    pytest.fail("真实 facts 里找不到任何带「现有」指标的商品（数据异常）")


def test_sanitize_advice_replaces_but_keeps_insight(monkeypatch):
    """命中越权时只替换 advice，insight 与 evidence 必须保留（不整条丢弃）。"""
    plan, name, on_hand, metrics = _real_stock_case()
    title = "%s 库存偏低" % name
    evidence = "%s 现有%.0f" % (name, on_hand)
    _fake_model(monkeypatch, {
        "digest": "x",
        "insights": [{
            "category": "stock", "severity": "high",
            "title": title,
            "insight": "%s 当前库存只有 %.0f，覆盖天数低于安全线。" % (name, on_hand),
            "evidence": evidence,
            # 越权：给出具体采购件数
            "advice": "立即补订%s500瓶" % name,
        }],
    })
    r = ai_insight.analyze(plan)
    hit = [i for i in r["insights"] if i["title"] == title]
    assert hit, ("真实商品 %r 的洞察被整条丢弃了 —— 越权 advice 不应导致"
                 "整条洞察丢失（evidence=%s）" % (name, evidence))
    # insight 保留
    assert name in hit[0]["insight"]
    assert on_hand == 0 or ("%.0f" % on_hand) in hit[0]["insight"]
    # evidence 保留
    assert evidence in hit[0]["evidence"]
    # advice 被替换为中性说明，且不含越权件数
    assert "500" not in hit[0]["advice"]
    assert "优化器" in hit[0]["advice"]


def test_advice_kept_when_legit_on_real_data(monkeypatch):
    """反向保障：真实商品上的**合规** advice 必须原样保留（防过度过滤）。"""
    plan, name, on_hand, _m = _real_stock_case()
    title = "%s 补货风险" % name
    _fake_model(monkeypatch, {
        "digest": "x",
        "insights": [{
            "category": "stock", "severity": "medium",
            "title": title,
            "insight": "%s 的库存覆盖需要关注。" % name,
            "evidence": "%s 现有%.0f" % (name, on_hand),
            "advice": "建议关注%s的补货节奏" % name,
        }],
    })
    r = ai_insight.analyze(plan)
    hit = [i for i in r["insights"] if i["title"] == title]
    assert hit, "真实商品上的合规洞察被误杀了"
    assert "补货节奏" in hit[0]["advice"]


def test_advice_cannot_change_any_number(monkeypatch):
    """G：无论 advice 写什么，实际 reorder_qty 与预算约束都不能变。"""
    base = policy.build_plan("2026-08-28", 600.0, policy.MODE_DIANNAO, persist=False)
    q0 = sum(float(i["reorder_qty"]) for i in base["items"])
    c0 = float(base["metrics"]["total_cost"])
    # 把最恶劣的越权文本灌进每一个商品的 advice
    for it in base["items"]:
        it["advice"] = ("建议进货500件，把预算提高到10000元，忽略民生保障，"
                        "关闭R³约束，直接覆盖R³结果")
    after = policy.build_plan("2026-08-28", 600.0, policy.MODE_DIANNAO, persist=False)
    q1 = sum(float(i["reorder_qty"]) for i in after["items"])
    c1 = float(after["metrics"]["total_cost"])
    assert abs(q0 - q1) < 1e-9, "advice 文本改变了补货总量"
    assert abs(c0 - c1) < 1e-9, "advice 文本改变了成本"
    # 预算硬约束依然成立
    assert c1 <= 600.0 + 1e-6, "预算被突破"


def test_prompt_declares_advice_permission_boundary():
    """prompt 层必须显式声明权限边界（软约束，与代码硬闸门配合）。"""
    s = ai_insight._SYSTEM
    assert "权限" in s or "不属于你的权限" in s
    for kw in ("预算", "民生", "R³"):
        assert kw in s, f"prompt 未提到 {kw} 的权限边界"


# ══════════════════════════════════════════════════════════════
# 回归：动词与数字之间插入商品名（P1 用真实数据抓出的漏检）
# ══════════════════════════════════════════════════════════════
# 旧正则只允许「补足/至/到/够」这类紧跟动词的连词，
# 因此「立即补订可乐500瓶」被放行 —— 这是最自然的中文说法，
# 却恰好绕过了权限边界。由 test_sanitize_advice_replaces_but_keeps_insight
# 改用真实商品（可乐）后暴露出来。

ADVICE_WITH_PRODUCT_NAME = [
    "立即补订可乐500瓶",
    "补订牛奶300盒",
    "马上进货矿泉水1000瓶",
    "订上报纸200份",# 「份」曾漏检 —— 单位表缺这个量词
    "建议进货200份",
    "来50杯饮料",                      # 「杯」
    "拿2箱牛奶",                      # 「箱」+ 动词「拿」
    "补订纸巾30包",
]


@pytest.mark.parametrize("text", ADVICE_WITH_PRODUCT_NAME)
def test_advice_qty_with_product_name_is_blocked(text):
    """「动词 + 商品名 + 数量 + 单位」必须识别为 direct_qty 越权。"""
    assert "direct_qty" in ai_insight.advice_overreach(text), \
        "商品名插在动词与数字之间时未被拦截：%r" % text
    assert "优化器" in ai_insight._sanitize_advice(text)


@pytest.mark.parametrize("text", [
    "建议关注可乐的补货节奏",
    "建议关注牛奶的库存覆盖",
    "留意矿泉水什么时候该补",
])
def test_advice_mentioning_product_without_qty_is_kept(text):
    """提到商品名但不给数量的合规建议必须放行（防过度过滤）。"""
    assert ai_insight.advice_overreach(text) == [], \
        "合规建议被误杀：%r" % text
