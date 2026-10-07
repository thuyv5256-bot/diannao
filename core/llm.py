# -*- coding: utf-8 -*-
"""
小满 · 大模型接入层（含可选的人话解释层）

═══ 分层定位（重要，答辩讲这个）═══

    第一层  决策数值：预测 → R³ 优化 → 补货数量
            由确定性规则算出（policy.py / forecast.py / r3_optimizer.py），
            **可复现、可审计、零成本、不宕机**。

    第二层  AI 决策中枢：事件语义理解 + 业务洞察
            由大模型参与 —— 它读懂店主的自然语言描述、做事件分级、
            给出风险识别与经营建议，产出**结构化参数**。
            见 ai_events.py / ai_insight.py。

    第三层  人话解释：把方案翻译成店主听得懂的话（本文件的 explain_plan 等）

═══ 为什么数值不放给大模型 ═══
补货是要真金白银花钱的决策，必须可复现、可审计、可追责。
让模型算数量，同一份输入两次可能给两个答案，出了问题无法定位。
所以：**模型负责"理解与判断"，规则负责"算数与执行"**。
模型不可用时（无 Key / 断网 / 超时），全部降级到规则路径，功能不降级。

依赖说明：只用标准库 urllib，不引入 requests / openai 等额外依赖。
"""

import json
import urllib.error
import urllib.request

from .config import (
    CURRENCY,
    LIVELIHOOD_MIN_COVER_DAYS,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_TIMEOUT,
)


def is_enabled() -> bool:
    return bool(LLM_API_KEY)


def _chat(messages: list[dict], temperature: float = 0.3, max_tokens: int = 500) -> str:
    """调用 OpenAI 兼容的 chat/completions 接口（标准库实现，零额外依赖）。"""
    return _post(messages, temperature=temperature, max_tokens=max_tokens,
                 json_mode=False)


def _post(messages: list[dict], temperature: float = 0.3, max_tokens: int = 500,
          json_mode: bool = False) -> str:
    """底层请求：可选 JSON 响应模式（OpenAI 兼容接口的 response_format）。"""
    url = LLM_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if json_mode:
        # 老服务端不认这个字段会报 400，因此失败时由 _chat_json 兜底重试
        payload["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {LLM_API_KEY}")
    with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"].strip()


def _extract_json(text: str):
    """从模型输出里抠出 JSON 对象。

    模型即使被要求「只输出 JSON」，也常带 ```json 围栏或前后寒暄，
    这里做纯文本级容错，不引入任何依赖。
    """
    if not text:
        return None
    s = text.strip()
    # 去掉 ```json ... ``` 围栏
    if s.startswith("```"):
        s = s.split("\n", 1)[-1] if "\n" in s else s
        if s.endswith("```"):
            s = s[: -3]
        s = s.strip()
        if s.startswith("json"):
            s = s[4:].strip()
    # 直接解析
    try:
        return json.loads(s)
    except Exception:
        pass
    # 退而求其次：截取最外层大括号
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(s[start:end + 1])
        except Exception:
            return None
    return None


def chat_json(system: str, user: str, max_tokens: int = 800,
              temperature: float = 0.2) -> dict | None:
    """要求模型返回 JSON 对象；任何环节失败都返回 None（调用方负责降级）。

    这是 AI 决策中枢（ai_events / ai_insight）的公共底座：
    模型只负责产出**结构化参数**，不负责算数，也不直接决定补货数量。
    """
    if not is_enabled():
        return None
    msgs = [{"role": "system", "content": system},
            {"role": "user", "content": user}]
    # 第一次带 json_object；服务端不支持该字段时去掉重试一次
    for use_json_mode in (True, False):
        try:
            raw = _post(msgs, temperature=temperature,
                        max_tokens=max_tokens, json_mode=use_json_mode)
        except Exception:
            continue
        data = _extract_json(raw)
        if isinstance(data, dict):
            return data
    return None


def _summarize(plan: dict) -> str:
    """把补货方案压成一段紧凑的事实文本，作为 LLM 的输入上下文。"""
    items = plan["items"]
    m = plan["metrics"]
    reorder = [it for it in items if it["reorder_qty"] > 0]
    livelihood = [it for it in reorder if it["is_livelihood"]]

    lines = [
        f"决策日期 {plan['date']}，进货预算 {CURRENCY}{m['budget']:.0f}。",
        f"本次共建议 {len(reorder)} 种商品进货，花费 {CURRENCY}{m['total_cost']:.0f}，"
        f"预计毛利 {CURRENCY}{m['gross_margin']:.0f}，民生最低保障达标率 {m['livelihood_secured_rate']:.0%}。",
    ]
    if livelihood:
        names = "、".join(it["name"] for it in livelihood[:6])
        lines.append(f"优先保障的民生商品：{names}。")
    top = sorted(reorder, key=lambda x: -x["reorder_qty"])[:8]
    detail = "；".join(
        f"{it['name']}进 {it['reorder_qty']:.0f}{it['unit']}（现有 {it['on_hand']:.0f}{it['unit']}，"
        f"预计日销 {it['daily_demand']:.1f}{it['unit']}）"
        for it in top
    )
    lines.append(f"进货明细（部分）：{detail}。")
    notes = sorted({n for it in items for n in (it["holiday_note"], it.get("promo_note", "")) if n})
    if notes:
        lines.append(f"节日/促销提醒：{'、'.join(notes)}。")
    risk_notes = sorted({n for it in items for n in (it.get("risk_note", ""),) if n})
    if risk_notes:
        lines.append(f"风险事件调整：{'、'.join(risk_notes)}。")
    return "\n".join(lines)


def plan_narrative(plan: dict) -> str:
    """规则模板版解释 —— 不依赖 LLM，永远可用。"""
    m = plan["metrics"]
    reorder = [it for it in plan["items"] if it["reorder_qty"] > 0]
    liv = [it for it in reorder if it["is_livelihood"]]
    low_stock = [it for it in plan["items"] if it.get("stockout_risk")]
    notes = sorted({n for it in plan["items"] for n in (it["holiday_note"], it.get("promo_note", "")) if n})

    parts = [
        f"今天建议花 {CURRENCY}{m['total_cost']:.0f} 进货，预计能赚 {CURRENCY}{m['gross_margin']:.0f} 毛利。",
        f"先把 {len(liv)} 样街坊天天要的民生货品备够至少 {LIVELIHOOD_MIN_COVER_DAYS:.0f} 天，"
        f"剩下预算再按利润高低分配给其他商品。",
    ]
    if notes:
        parts.append(f"注意：{('、'.join(notes))}，已自动加大相关品类备货。")
    risk_notes = sorted({n for it in plan["items"] for n in (it.get("risk_note", ""),) if n})
    if risk_notes:
        parts.append(f"已按风险事件调整：{'、'.join(risk_notes)}。")
    if low_stock:
        names = "、".join(it["name"] for it in low_stock[:4])
        parts.append(f"有 {len(low_stock)} 样商品库存偏低，建议尽快补：{names}。")
    else:
        parts.append("目前各商品库存都在安全线以上。")
    return "\n".join(parts)


def explain_plan(plan: dict) -> str:
    """把补货方案讲成小店主听得懂的大白话。

    有密钥且调用成功 → LLM 生成；否则 → 规则模板。返回纯文本。
    """
    if not is_enabled():
        return plan_narrative(plan)

    system = (
        "你是一家社区夫妻小店补货系统的话术助手。店主讲中文、没有数据分析背景。"
        "请把进货建议用两三句大白话讲清楚：进了什么、为什么、花了多少钱、能赚多少。"
        "不要术语（不提安全库存系数、资金效率），直接说人话，控制在 120 字以内。"
    )
    try:
        return _chat([
            {"role": "system", "content": system},
            {"role": "user", "content": "补货方案如下，请解释：\n" + _summarize(plan)},
        ])
    except Exception:
        return plan_narrative(plan)


def answer_question(plan: dict, question: str) -> str:
    """针对当前方案回答店主的一句提问（可选问答能力）。"""
    if not is_enabled():
        return "（未配置 LLM Key，问答能力未启用。可参考下方方案明细。）"
    try:
        return _chat([
            {"role": "system", "content": "你是补货系统话术助手，用中文大白话简短回答店主的疑问，80 字以内。"},
            {"role": "user", "content": f"方案：\n{_summarize(plan)}\n\n店主问：{question}"},
        ])
    except Exception:
        return "（回答失败，请稍后再试。）"
