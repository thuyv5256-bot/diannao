# -*- coding: utf-8 -*-
"""小满 · AI 事件语义理解与分级（AI 决策中枢 · 第一环）

═══ 它解决什么 ═══

店主说的不是「rain / heat / holiday」，而是��

    「明天下大暴雨，晚上估计没什么人出门，顺路那家超市的货也送不来」

规则引擎只认 `risk.RISK_KEYS` 那四个固定键。要让规则用上这句话，
必须先把它**翻译**成结构化事件参数。这一步传统做法是穷举关键词
（见 `risk.parse` 与 `agent.parse_request` 的关键词表）——能认「暴雨」，
但认不出「晚上没什么人出门」这句话背后其实同时包含
「暴雨（需求侧）」「非高峰时段（客流下降）」「供应商断供（供给侧）」三重含义。

═══ 职责边界（铁律，答辩必讲）═══

**本模块只产出「参数」，绝不产出「数量」。**

    允许：判断有哪些事件 → 事件分级 → 给出受影响品类与需求乘数区间
    禁止：决定某个 SKU 进多少件、决定预算怎么分、决定最终覆盖天数

    数量永远由 policy.py / forecast.py / r3_optimizer.py 这条确定性链路算出。
    本模块的输出是**输入**给那条链路的，不是它的替代品。

这是 ADR-007「决策确定性」的延续：模型负责理解与判断，规则负责算数与执行。
好处是模型不可用（无 Key / 断网 / 超时）时，一切降级到关键词规则，
补货数字与模型在线时**完全一致**——模型只让参数更准，从不让结果漂移。

═══ 事件分级 ═══

沿用 `event_evidence.py` 的 strong / weak / insufficient 三档语义：

    strong        证据充分（历史事件日样本足、方向一致），参数直接生效
    weak          证据不足，参数打折扣后生效
    insufficient  证据不足到不该用，退回纯规则路径

模型额外产出的两个字段是它比关键词表强的地方：
    · `severity`  强度（mild / moderate / severe）→ 决定乘数取区间的哪一端
    · `lead_time_hours` 距生效还有多久 → 决定是「今天就补」还是「明早再补」
"""

from __future__ import annotations

import re

from . import llm, risk
from .config import LLM_MODEL

# ── 事件分级枚举（与 event_evidence.py 的语义保持一致）──────────────
LEVELS = ("strong", "weak", "insufficient")
SEVERITIES = ("mild", "moderate", "severe")

# 模型可用的风险键白名单 —— 越界的一律丢弃，杜绝模型发明新事件类型
_VALID_KEYS = set(risk.RISK_KEYS)

# 乘数夹紧区间：模型可以调力度，但不能把需求说成翻十倍
_FACTOR_MIN, _FACTOR_MAX = 0.60, 1.80
# 分级 → 乘数折扣（insufficient 直接不给用）
_LEVEL_DISCOUNT = {"strong": 1.0, "weak": 0.5, "insufficient": 0.0}

# 关键词兜底：模型不可用时沿用原有的四类关键词（与 agent.parse_request 同源思路）
_KEYWORDS = {
    "rain": ("暴雨", "下雨", "大雨", "雷阵雨", "台风", "积水"),
    "heat": ("高温", "酷暑", "炎热", "三十八", "35度", "热浪"),
    "holiday": ("节假日", "节日", "假期", "过年", "中秋", "国庆", "春节"),
    "supplier": ("断货", "断供", "送不来", "供应商", "缺货不送", "物流停"),
}

_SYSTEM = """你是社区夫妻小店的经营分析师。你的任务是读懂店主用自然语言描述的\
明天可能发生的情况，把它翻译成结构化的事件参数。

规则：
1. 只能使用给定的事件键：rain（暴雨/下雨）、heat（高温/酷暑）、\
holiday（节假日/假期）、supplier（供应商断供/送不来）。不要发明新键。
2. severity 只能是 mild / moderate / severe 三者之一。
3. level 只能是 strong / weak / insufficient 三者之一：\
证据充分给 strong，拿不准给 weak，信息太少给 insufficient。
4. affected_categories 只能从给定品类列表里选，没有就留空数组。
5. demand_factor 是需求乘数，必须在 0.6 ~ 1.8 之间。囤货类需求上升给 >1，\
客流下降类需求下降给 <1，拿不准就给 1.0。
6. reasoning 用一句中文说明判断依据，不要超过 40 字。
7. 供给侧事件（supplier）不要给 demand_factor，给 1.0。

只输出 JSON，格式：
{"events":[{"key":"rain","severity":"moderate","level":"strong",\
"affected_categories":["冷饮","饮料"],"demand_factor":0.85,\
"lead_time_hours":12,"reasoning":"下雨天客流下降，冲动消费减少"}],\
"summary":"一句话概括明天的情况"}"""


def _clamp(v, lo=_FACTOR_MIN, hi=_FACTOR_MAX, default=1.0):
    """把模型给的乘数夹进合法区间；解析失败一律回中性 1.0。"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):   # NaN / inf
        return default
    return max(lo, min(hi, f))


def _as_list(v, allowed) -> list[str]:
    """把模型返回的品类列表规整成字符串数组，并过滤掉不在白名单里的。"""
    if not isinstance(v, list):
        return []
    return [str(x).strip() for x in v if str(x).strip() and str(x).strip() in allowed]


def _level_of(v) -> str:
    v = str(v or "").strip().lower()
    return v if v in LEVELS else "insufficient"


def _severity_of(v) -> str:
    v = str(v or "").strip().lower()
    return v if v in SEVERITIES else "moderate"


# ══════════════════════════════════════════════════════════════
# 一、规则兜底：无 Key / 调用失败时使用（行为与升级前完全一致）
# ══════════════════════════════════════════════════════════════

def rule_parse(text: str) -> dict:
    """关键词规则解析 —— 永远可用的基线，与模型路径共享同一输出结构。"""
    t = str(text or "")
    found = []
    for key, words in _KEYWORDS.items():
        if any(w in t for w in words):
            found.append({
                "key": key,
                "severity": "moderate",
                # 关键词命中不等于证据充分：没有历史数据支撑时只给 weak
                "level": "weak",
                "affected_categories": [],
                "demand_factor": 1.0,
                "lead_time_hours": 0,
                "reasoning": "关键词命中「%s」" % next(w for w in words if w in t),
                "source": "rule",
            })
    return {
        "events": found,
        "summary": ("识别到：" + "、".join(risk.RISK_LABELS.get(e["key"], e["key"])
                                       for e in found)) if found else "未识别到明显风险事件",
        "source": "rule",
        "model": "—",
    }


# ══════════════════════════════════════════════════════════════
# 二、模型解析：LLM 做场景理解与分级
# ══════════════════════════════════════════════════════════════

def _build_prompt(text: str, categories: list[str]) -> str:
    cat = "、".join(categories) if categories else "（无）"
    return (
        "店主描述：%s\n\n"
        "本店在售品类：%s\n\n"
        "请判断明天有哪些风险事件、分别多严重、证据是否充分。"
        % (str(text or "").strip() or "（店主没有描述）", cat)
    )


def llm_parse(text: str, categories: list[str] | None = None) -> dict | None:
    """调用大模型做事件语义理解；任何失败返回 None（调用方降级）。

    注意本函数只产出参数，不产出补货数量 —— 数量由 policy 链路计算。
    """
    if not llm.is_enabled() or not str(text or "").strip():
        return None
    try:
        data = llm.chat_json(_SYSTEM, _build_prompt(text, categories or []))
    except Exception:
        # 网络超时/连接错误/HTTP 错误/解析异常 —— 一律降级为规则路径。
        # 这里必须捕获：docstring 承诺「任何失败返回 None」，
        # 而 TimeoutError 等会向上冒泡打断整个补货主流程
        # （由 tests/test_ai_resilience.py::test_case2_llm_timeout 抓出）。
        return None
    if not isinstance(data, dict):
        return None

    raw_events = data.get("events")
    if not isinstance(raw_events, list):
        return None

    events = []
    for e in raw_events:
        if not isinstance(e, dict):
            continue
        key = str(e.get("key", "")).strip().lower()
        # 白名单校验：模型发明的键一律丢弃
        if key not in _VALID_KEYS:
            continue
        level = _level_of(e.get("level"))
        sev = _severity_of(e.get("severity"))
        # 供给侧事件不进需求侧
        factor = 1.0 if key == "supplier" else _clamp(e.get("demand_factor"))
        try:
            lead = max(0, int(e.get("lead_time_hours") or 0))
        except (TypeError, ValueError):
            lead = 0
        events.append({
            "key": key,
            "severity": sev,
            "level": level,
            "affected_categories": _as_list(e.get("affected_categories"), categories or []),
            "demand_factor": factor,
            "lead_time_hours": lead,
            "reasoning": str(e.get("reasoning") or "").strip()[:80],
            "source": "llm",
        })

    summary = str(data.get("summary") or "").strip()[:120]
    return {
        "events": events,
        "summary": summary or "模型未给出概括",
        "source": "llm",
        "model": LLM_MODEL,
    }


# ══════════════════════════════════════════════════════════════
# 三、统一入口（页面与决策链路都走这里）
# ══════════════════════════════════════════════════════════════

def parse(text: str, categories: list[str] | None = None) -> dict:
    """AI 事件语义理解统一入口：模型优先，失败降级规则。

    返回结构见 rule_parse()；额外带 `active`（生效的风险键列表）
    与 `factors`（品类 → 乘数），供下游规则模块消费。
    """
    result = llm_parse(text, categories)
    if result is None:
        result = rule_parse(text)
    return finalize(result)


def finalize(result: dict) -> dict:
    """把解析结果整形成下游可直接消费的结构（不改变事件本身）。"""
    events = result.get("events") or []
    # 按分级折扣后，才允许影响预测的乘数
    factors: dict[str, float] = {}
    for e in events:
        disc = _LEVEL_DISCOUNT.get(e.get("level", "insufficient"), 0.0)
        if disc <= 0:
            continue
        raw = float(e.get("demand_factor", 1.0) or 1.0)
        adj = 1.0 + (raw - 1.0) * disc      # 向 1.0 收缩，弱证据不敢放大
        # 乘数为 1.0 等于「没修正」——不写进 factors，免得下游和页面出现无意义的空转条目
        # （供给侧事件如断供，demand_factor 被强制为 1.0，就是走这条分支）
        if abs(adj - 1.0) < 1e-9:
            continue
        cats = e.get("affected_categories") or []
        for c in cats:
            factors[c] = factors.get(c, 1.0) * adj
    for c, f in factors.items():
        factors[c] = _clamp(f)

    active = risk.normalize([e.get("key") for e in events])
    out = dict(result)
    out["active"] = active
    out["factors"] = factors
    out["effective"] = bool(factors) or any(e.get("key") == "supplier" for e in events)
    return out


def parse_risks(text: str, categories: list[str] | None = None) -> list[str]:
    """便捷入口：只要风险键列表（policy.build_plan 的 risks 参数可直接吃）。"""
    return parse(text, categories)["active"]


def mode_label() -> str:
    """给页面显示用的模式标签（明确标注当前是 AI 模式还是规则降级）。"""
    return "AI 已连接" if llm.is_enabled() else "规则降级模式"
