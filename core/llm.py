# -*- coding: utf-8 -*-
"""
小满 · 可选的 LLM 说明层

设计定位（答辩点）：核心补货决策是确定性规则（可解释、零成本、不宕机），
LLM 只做"把方案翻译成人话"与"问答"的外层 —— 可失败、可降级，
失败时回退到规则模板文案，绝不影响补货建议本身。

默认对接 OpenAI 兼容的 /chat/completions 接口，因此
OpenAI / DeepSeek / 通义 DashScope(兼容模式) / 本地 vLLM 都能直接用，
只需改环境变量（见 .env.example）。未配置密钥时自动走规则模板，无需改动即可运行。

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
    url = LLM_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {LLM_API_KEY}")
    with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"].strip()


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
