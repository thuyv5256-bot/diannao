# -*- coding: utf-8 -*-
"""小满 · AI 业务洞察与风险识别（AI 决策中枢 · 第二环）

═══ 它和第一环的区别 ═══

`ai_events` 回答「明天会发生什么」——是**向前看**的事件预判。
`ai_insight` 回答「这次决策有什么问题」——是**回头看**的经营体检。

═══ 为什么要它 ═══

规则引擎能算对数，但算不出「数背后的经营含义」。举三个真实场景：

    1. 预算没花完
       规则只知道「剩 80 元」，不知道这是「天气好、没人来，风险锁得太死」
       还是「模型近期高估了需求」。前者该放松，后者该校准。

    2. 民生达标但结构变了
       达标率 100% 看着完美，但可能是「进的民生货恰好都在临期打折」，
       而真正该保的盐/醋反而没进 —— 指标好看，门店体验在恶化。

    3. 断货与损耗同时出现
       同一个品今天又断货又报损，说明的是「补货节奏与保质期不匹配」，
       而不是两个独立的小问题。规则会分别报，模型能看出关联。

═══ 职责边界（与 ai_events 同一条铁律）═══

**只做「指出问题 + 给建议」，绝不改数字。**

    允许：跨指标关联、发现异常组合、指出参数需要调整的方向、给经营建议
    禁止：修改任何补货数量、预算分配、覆盖天数、安全库存系数

每条洞察都必须带 `evidence`（来自哪几个真实字段），否则不允许输出 ——
这是为了防止模型编造经营事实。没证据的"洞察"是幻觉，不是洞察。

无 Key / 调用失败时降级为 `rule_insight()`（纯规则算账，永远可用）。
"""

from __future__ import annotations

import re

from . import llm
from .config import CURRENCY, LLM_MODEL, LIVELIHOOD_MIN_COVER_DAYS

# 洞察等级：直接决定前端徽标颜色语义
SEVERITIES = ("high", "medium", "low")

_SYSTEM = """你是社区夫妻小店的资深经营顾问。你会看到店主的真实经营数据（补货方案、\
库存、历史销量、事件、经验库、预算约束）。请指出店主自己可能没意识到的问题。

规则：
1. 每条洞察必须基于给定数据中的真实数字，禁止编造数据里没有的事实。
2. insight 要说清「哪个商品 / 哪个指标 + 意味着什么」，不要空泛。
3. advice 是给店主的可执行建议，一句话，不超过 30 字。
4. category 只能从 demand（需求判断）/ stock（库存结构）/ profit（成本收益）/ \
liveliness（民生保障）/ supply（供应）里选。
5. severity 只能是 high / medium / low。
6. 没有值得说的就返回空数组，不要为了凑数而编。
7. 权限边界（重要）：你只是经营顾问，**最终补货数量由系统的R³ 优化器在预算、库存和
   民生约束下算出，不属于你的权限**。因此 advice 里禁止出现：
   - 具体进货件数/瓶数/箱数（如「补订酱油 18 瓶」「进货 500 件」）
   - 修改或突破预算的建议（如「把预算提高到 10000 元」）
   - 忽略、关闭或绕过民生保障/ R³ 约束的说法
   - 覆盖或推翻系统最终结果的表述（如「不用 R³，按我的建议采购」）
   可以写的是经营层面的观察与提醒，如「牛奶库存覆盖天数偏低，建议关注补货风险」
   「可留意饮料和生鲜需求变化」「建议提前确认到货情况」。

只输出 JSON，格式：
{"insights":[{"category":"stock","severity":"high","title":"一句话结论",\
"insight":"具体分析，带数字","evidence":"依据的字段与数值","advice":"可执行建议"}],\
"digest":"两三句话的整体经营判断"}"""


# ══════════════════════════════════════════════════════════════
# 一、事实提取：把真实决策结果压成给模型看的事实清单
# ══════════════════════════════════════════════════════════════

def build_facts(plan: dict, extra: dict | None = None) -> str:
    """从真实 plan 里提取结构化事实。

    这里每一个数字都取自policy 链路算出的结果，不做任何估算或美化。

    文本里每个数字都紧跟在它所属的实体与指标后面（如「矿泉水 现有27、够1.9天」），
    `_build_fact_index` 会把这份文本解析成 {实体: {指标: 值}} 的结构化索引，
    供 `_sanitize` 做「实体 + 指标 + 数字」三者绑定的幻觉校验。
    """
    if not plan:
        return "（无决策结果）"
    m = plan.get("metrics") or {}
    items = plan.get("items") or []
    reorder = [it for it in items if float(it.get("reorder_qty") or 0) > 0]
    liv = [it for it in reorder if it.get("is_livelihood")]

    budget = float(m.get("budget") or 0.0)
    cost = float(m.get("total_cost") or 0.0)
    left = budget - cost

    lines = [
        "【本次决策】日期 %s，预算 %s%.0f，实际花费 %s%.0f，剩余 %s%.0f（使用率 %.0f%%）。"
        % (plan.get("date"), CURRENCY, budget, CURRENCY, cost, CURRENCY, left,
           (cost / budget * 100.0) if budget > 0 else 0.0),
        "【品类结构】建议进货 %d 种商品，其中民生商品 %d 种；"
        "预计毛利 %s%.0f；民生最低保障达标率 %.0f%%。"
        % (len(reorder), len(liv), CURRENCY, float(m.get("gross_margin") or 0.0),
           float(m.get("livelihood_secured_rate") or 0.0) * 100.0),
    ]

    # 库存承压：覆盖天数最短的几样
    risky = sorted(items, key=lambda x: float(x.get("final_cover_days") or 99))[:5]
    if risky:
        lines.append("【库存承压 Top5】" + "；".join(
            "%s 现有%.0f%s、够%.1f天%s"
            % (it["name"], float(it.get("on_hand") or 0), it.get("unit", ""),
               float(it.get("final_cover_days") or 0),
               "（断货风险）" if it.get("stockout_risk") else "")
            for it in risky))

    # 高积压风险：备货天数明显超过需求
    over = [it for it in items if float(it.get("expected_excess_qty") or 0) > 0]
    if over:
        lines.append("【积压/临期关注】" + "、".join(
            "%s 预计积压%.0f%s" % (it["name"], float(it.get("expected_excess_qty") or 0),
                                  it.get("unit", ""))
            for it in over[:6]))

    # 民生明细
    if liv:
        lines.append("【民生保障明细】" + "；".join(
            "%s 进%.0f%s（兜底要求%.0f%s，够%.1f天）"
            % (it["name"], float(it.get("reorder_qty") or 0), it.get("unit", ""),
               float(it.get("floor_qty") or 0), it.get("unit", ""),
               float(it.get("final_cover_days") or 0))
            for it in liv[:8]))
    lines.append("【民生兜底标准】每个民生商品至少覆盖 %.0f 天。"
                 % LIVELIHOOD_MIN_COVER_DAYS)

    # 事件与断供
    if plan.get("risks"):
        from . import events as _ev
        lines.append("【生效风险事件】" + "、".join(
            _ev.EVENT_KEY_TO_LABEL.get(k, k) for k in plan["risks"]))
    down = [it["name"] for it in items if it.get("supplier_down")]
    if down:
        lines.append("【今日断供不可采购】" + "、".join(down))

    # 经验库命中情况
    hit = [it for it in items if abs(float(it.get("memory_delta") or 0.0)) > 1e-9]
    if hit:
        lines.append("【历史经验命中】" + "、".join(
            "%s 场景「%s」校准%+.2f" % (it["name"], it.get("memory_scene") or "普通日",
                                        float(it.get("memory_delta") or 0.0))
            for it in hit[:6]))
    else:
        lines.append("【历史经验命中】本次无同类场景经验参与修正。")

    for k, v in (extra or {}).items():
        lines.append("【%s】%s" % (k, v))
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# 二、规则洞察：永远可用的基线
# ══════════════════════════════════════════════════════════════

def rule_insight(plan: dict) -> dict:
    """纯规则的经营体检 —— 不依赖 LLM，永远可用。

    刻意只做「能从数字直接读出来」的判断，宁少不编。
    """
    out: list[dict] = []
    if not plan:
        return {"insights": [], "digest": "暂无决策结果可分析。", "source": "rule", "model": "—"}

    m = plan.get("metrics") or {}
    items = plan.get("items") or []
    budget = float(m.get("budget") or 0.0)
    cost = float(m.get("total_cost") or 0.0)
    left = budget - cost
    reorder = [it for it in items if float(it.get("reorder_qty") or 0) > 0]

    # ① 预算没花完 —— 机会成本
    if budget > 0 and left > budget * 0.15:
        out.append({
            "category": "profit", "severity": "medium",
            "title": "预算没用满，有 %s%.0f 闲置" % (CURRENCY, left),
            "insight": "本次只花了预算的 %.0f%%，剩下 %s%.0f 没有转化为备货。"
                       "可能是所有商品的安全库存都够了，也可能是预算卡得太紧。"
                       % (cost / budget * 100.0, CURRENCY, left),
            "evidence": "预算 %s%.0f / 实际花费 %s%.0f" % (CURRENCY, budget, CURRENCY, cost),
            "advice": "若确认库存充足，可上调预算上限换取更高毛利",
        })

    # ② 民生达标但未覆盖的漏网商品
    sec = float(m.get("livelihood_secured_rate") or 0.0)
    if sec >= 1.0 - 1e-9:
        out.append({
            "category": "liveliness", "severity": "low",
            "title": "民生兜底已全部达标（%.0f%%）" % (sec * 100.0),
            "insight": "%d 种民生商品都达到了最低保障要求，这条底线守住了。"
                       "但达标只说明数量够，不代表品类结构合理。"
                       % int(m.get("livelihood_total_count") or 0),
            "evidence": "livelihood_secured_rate=%.2f，兜底标准 %.0f 天"
                        % (sec, LIVELIHOOD_MIN_COVER_DAYS),
            "advice": "定期看一眼盐/醋/纸巾这类基础品有没有断档",
        })

    # ③ 断货风险集中
    risk = [it for it in items if it.get("stockout_risk")]
    if risk:
        out.append({
            "category": "stock", "severity": "high" if len(risk) >= 5 else "medium",
            "title": "%d 种商品可能撑不过明天" % len(risk),
            "insight": "覆盖天数最短的是%s，现有 %.0f%s 只够 %.1f 天。"
                       "这类商品断货会连带影响其他商品的销售。"
                       % (risk[0]["name"], float(risk[0].get("on_hand") or 0),
                          risk[0].get("unit", ""), float(risk[0].get("final_cover_days") or 0)),
            "evidence": "stockout_risk=True 的商品共 %d 种" % len(risk),
            "advice": "优先补这 %d 种，其余可往后排" % len(risk),
        })

    # ④ 积压 / 临期
    over = [it for it in items if float(it.get("expected_excess_qty") or 0) > 0]
    if over:
        out.append({
            "category": "stock", "severity": "medium",
            "title": "%d 种商品预计会积压" % len(over),
            "insight": "按当前需求，%s 预计多出 %.0f%s。"
                       "积压会占用本就紧张的现金流，还可能临期报损。"
                       % (over[0]["name"], float(over[0].get("expected_excess_qty") or 0),
                          over[0].get("unit", "")),
            "evidence": "expected_excess_qty>0 的商品共 %d 种" % len(over),
            "advice": "下次把这类商品的补货量下调一档",
        })

    # ⑤ 断供
    down = [it for it in items if it.get("supplier_down")]
    if down:
        out.append({
            "category": "supply", "severity": "high",
            "title": "%d 种商品供应商异常，本次无法采购" % len(down),
            "insight": "%s 属于断供供应商，这些商品本次不进货。"
                       "如果它们是民生商品，需要立刻找替代供应商。"
                       % "、".join(it["name"] for it in down[:4]),
            "evidence": "supplier_down=True 的商品共 %d 种" % len(down),
            "advice": "先确认断供是否影响民生品，必要时临时调货",
        })

    # ⑥ 经验库完全没命中
    if not any(abs(float(it.get("memory_delta") or 0.0)) > 1e-9 for it in items):
        out.append({
            "category": "demand", "severity": "low",
            "title": "历史经验本次没有参与修正",
            "insight": "本次决策全部来自规则基线，说明近期没有沉淀下"
                       "「同场景同类商品」的经验，模型还处在冷启动阶段。",
            "evidence": "全部商品 memory_delta 均为 0",
            "advice": "每天在「今天生意怎么样」录一次反馈，两个月后效果会明显",
        })

    digest = ("本次建议进 %d 种商品，花费 %s%.0f，民生达标率 %.0f%%。"
              % (len(reorder), CURRENCY, cost, sec * 100.0))
    if out:
        digest += "规则体检发现 %d 项值得留意。" % len(out)
    else:
        digest += "各项指标均在合理区间。"
    return {"insights": out, "digest": digest, "source": "rule", "model": "—"}


# ══════════════════════════════════════════════════════════════
# 三、模型洞察
# ══════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════
# 一之补：结构化事实索引（防「数字冒用」幻觉的关键）
# ══════════════════════════════════════════════════════════════
#
# 漏洞背景
#   旧校验只做 `evidence里的数字 ∈ facts 里的数字`，是个**扁平集合**，
#   丢掉了「这个数字属于哪个商品」的信息。于是：
#     facts 里矿泉水有 12，牛奶有 30
#     模型说「牛奶只剩 12 件」→ 12 确实在 facts 里 → 旧校验放行
#   这类「借数字」的数字必须被拦住。
#
# 本索引的做法
#   把 facts 文本按「实体 → 指标 → 数值」解析成字典：
#     {"矿泉水": {"现有": 27.0, "够卖天": 1.9, "建议进": 10.0}, "牛奶": {...}}
#   校验时要求模型声称的每个数字，必须在**它自己提到的那个实体**的某个指标上找到。
#   若模型提到了实体 A 却引用了实体 B 的数字 → 放行逻辑不成立 → 丢弃。

_NUM = r"(\d+(?:\.\d+)?)"


def _build_fact_index(facts: str, item_names: list[str] | None = None) -> dict[str, dict[str, float]]:
    """把 facts 文本解析成 {实体名: {指标: 数值}}。

    实体识别用**商品名精确匹配**（而不是靠正则猜边界）—— 因为
    「卷纸 现有0提」里"卷纸"是实体、"现有"是指标，字符类正则会贪婪吞掉指标词。
    传入 `item_names`（来自 plan 的真实商品名）时按最长优先匹配，
    匹配不到的行直接忽略：宁可漏判不可错判。

    每个实体的每个指标都从「指标词 + 紧邻数字」里取，格式与 build_facts 一致：
        现有0 / 够2.1天 / 进10 / 兜底要求3 / 预计积压5 / 校准+0.06 / 日销11.1
    """
    idx: dict[str, dict[str, float]] = {}
    names = sorted({str(n).strip() for n in (item_names or []) if str(n).strip()},
                   key=len, reverse=True)
    if not names:
        # 退化：无商品名时不做实体绑定（调用方会跳过绑定校验）
        return idx

    # 指标词表：按长度降序，保证「预计积压」优先于「积压」、「够卖天」优先于「够」
    metric_words = sorted(
        ["预计积压", "预计过剩", "兜底要求", "现有库存", "剩余库存", "建议进",
         "够卖天", "覆盖天数", "日均需求", "预计日销", "日销", "库存", "现有",
         "够卖", "够", "覆盖", "进", "积压", "过剩", "兜底", "底线", "最低",
         "校准", "修正", "调整", "天数", "件", "天"],
        key=len, reverse=True)

    for raw in str(facts or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        # 去掉行首的【段落名】标签（build_facts 每行都有），但**保留**该行携带的数据。
        # 注意：不能整行跳过 —— 含商品名的数据行也以【开头，跳过会导致索引恒为空。
        line = re.sub(r"^【[^】]*】\s*", "", line)
        if not line:
            continue
        # 逐个「商品名」定位，绑定其后直到下一个商品名的部分
        for name in names:
            for m in re.finditer(re.escape(name), line):
                tail = line[m.end():]
                # 截到下一个商品名为止
                cut = len(tail)
                for other in names:
                    if other == name:
                        continue
                    nxt = tail.find(other)
                    if 0 <= nxt < cut:
                        cut = nxt
                seg = tail[:cut]
                bucket = idx.setdefault(name, {})
                for mw in metric_words:
                    mm = re.search(re.escape(mw) + r"\s*(\d+(?:\.\d+)?)", seg)
                    if mm:
                        try:
                            bucket.setdefault(mw, float(mm.group(1)))
                        except ValueError:
                            pass
    return {k: v for k, v in idx.items() if v}


# ══════════════════════════════════════════════════════════════
# 指标词表：把evidence 里的自然语言说法映射到 facts 的指标 key
# ══════════════════════════════════════════════════════════════
# facts 里的指标 key 是「现有 / 够 / 进 / 兜底要求」这类短词，
# 而模型写出来的evidence 可能说「库存」「覆盖天数」「建议进」等。
# 这里建立别名表，把它们归一化后再比对，避免「量纲冒用」：
#   facts:雪糕 够 2.4（天）    模型说:「雪糕 现有 2 件」→ 指标族不同 → 拦
_METRIC_ALIASES = {
    "现有": "现有", "库存": "现有", "现在有": "现有", "手上有": "现有",
    "现有库存": "现有", "当前库存": "现有", "剩余库存": "现有", "剩余": "现有",
    "够": "够", "够卖": "够", "够用": "够", "覆盖": "够", "覆盖天数": "够",
    "可卖": "够", "能撑": "够", "还能卖": "够", "支撑": "够",
    "进": "进", "建议进": "进", "补货": "进", "采购": "进", "下单": "进",
    "进货量": "进", "进量": "进",
    "兜底要求": "兜底要求", "兜底": "兜底要求", "底线": "兜底要求",
    "最低要求": "兜底要求",
}

# 指标族：同一族内的不同叫法视为等价（避免误杀）
_METRIC_FAMILY = {
    "现有": "stock_qty", "够": "cover_days",
    "进": "reorder_qty", "兜底要求": "floor_qty",
}


def _metric_family(word: str) -> str:
    """指标词的族；无法归一化时返回原词（小写去空格）。"""
    w = (word or "").strip()
    if w in _METRIC_ALIASES:
        return _METRIC_FAMILY[_METRIC_ALIASES[w]]
    for alias, canon in _METRIC_ALIASES.items():
        if alias and alias in w:
            return _METRIC_FAMILY[canon]
    return w.lower()


def _metric_matches(claimed: str, actual: str) -> bool:
    """evidence 自称的指标与 facts 实际指标是否同名。"""
    return _metric_family(claimed) == _metric_family(actual)


def _num_with_metric(text: str) -> dict[str, str]:
    """把 evidence 解析成 {数字字符串: 它前面紧邻的指标词}。

    没有紧邻指标词时值取空串，表示「不限定指标」，保持旧的宽松行为。
    """
    out: dict[str, str] = {}
    for m in re.finditer(r"([一-龥A-Za-z]{1,6}?)\s*(" + _NUM + r")", text or ""):
        word = (m.group(1) or "").strip()
        # 去掉可能粘连的实体名尾字（如「牛奶库存」→ 保留「库存」）
        canon = None
        for alias in _METRIC_ALIASES:
            if alias in word:
                canon = alias
                break
        out[m.group(2)] = canon or ""
    # 补上没有被指标词前缀的数字
    for n in re.findall(_NUM, text or ""):
        out.setdefault(n, "")
    return out


def _evidence_is_bound(evidence: str, insight: str, index: dict[str, dict[str, float]],
                       all_nums: set[str]) -> bool:
    """校验 evidence 里的数字是否「绑定」在正确的实体与指标上。

    规则（任一条不满足即视为幻觉并丢弃该条洞察）：
      1. evidence 为空 → 不做数字校验。
      2. **evidence 里的每一个数字**都必须在 facts 中真实存在
         （旧逻辑是「至少一个命中就放行」，会被「1 个真数字 + N 个编造数字」绕过）。
      3. 若evidence 点名了某个真实实体，则每个数字还必须能在这个实体的
         某个指标上找到 —— 引用别的实体的数字 → 幻觉。
      4. 若 evidence 没点名任何实体，但 insight 提到了实体，则用 insight 的实体做绑定。
    """
    ev_nums = set(re.findall(_NUM, evidence))
    if not ev_nums:
        return True                      # 无数字可校验
    # ② 全部数字都必须真实存在（不允许「真数字掩护假数字」）
    if not ev_nums.issubset(all_nums):
        return False

    # 从 evidence（或 insight）里识别它声称的实体
    mentioned = [name for name in index if name and (name in evidence or name in insight)]
    if not mentioned:
        # 模型没点名任何实体 —— 数字都已确认存在，放行（避免误杀整体性洞察）。
        return True

    # 点名了实体：每个数字都必须在**至少一个被点名实体**的某个指标上找到，
    # 且如果 evidence 明确写了指标词，就必须与该指标对得上（防量纲冒用）。
    for n, claimed in _num_with_metric(evidence).items():
        try:
            val = float(n)
        except ValueError:
            return False
        ok = False
        for name in mentioned:
            for metric, v in index.get(name, {}).items():
                val_ok = (abs(v - val) < 1e-6 or abs(v * 100 - val) < 1e-6
                          or abs(v - val / 100.0) < 1e-9)
                if not val_ok:
                    continue
                # 量纲校验：evidence 若指明了指标，该指标必须就是这个值的来源。
                # 例：facts 里「雪糕 够2.4天」，模型说「雪糕 现有2件」——
                # 数值能被找到（就是「够」），但指标词对不上 → 幻觉。
                if claimed and not (_metric_matches(claimed, metric)
                                    or _metric_family(claimed) == _metric_family(metric)):
                    continue
                ok = True
                break
            if ok:
                break
        if not ok:
            return False
    return True


# ══════════════════════════════════════════════════════════════
# advice 权限边界：AI 可以解释与提醒，但不能冒充最终补货决策器
# ══════════════════════════════════════════════════════════════
# 最终进货数量由 R³ 在预算、库存与民生约束下算出。advice 只是一句经营提醒，
# 一旦它给出具体件数 / 建议突破预算 / 要求关闭约束，UI 上就会造成
# 「AI 拥有最终决策权」的错觉。因此这里做一道**展示层**的硬闸门。
#
# 设计原则（避免过度过滤）：
#   · 只拦「越权句式」，不拦所有数字 —— 「覆盖 2 天」「毛利率偏低」照常显示；
#   · 命中后不是丢掉整条洞察（那会连带丢掉有价值的 insight/evidence），
#     而是只把 advice 替换成中性的合规提醒。
_ADVICE_UNITS = (r"(?:件|瓶|袋|包|盒|个|支|提|斤|公斤|kg|升|罐|听|块|根|只|条|箱|卷"
                 r"|份|杯|碗|双|板|桶|扎|棵|颗|粒|串|袋装|瓶装|条装)")
_ADVICE_ACT = r"(?:进|补|采购|进货|订|下单|备|加|调|拿|上)"

# (类别, 编译后的正则) —— 命中即视为越权
_ADVICE_OVERREACH = [
    # ① 冒充当最终采购数量：动词+数字+单位，或商品名+数字+单位并列
    ("direct_qty",
     # 动词与数字之间允许插入商品名（2~8 字），如「补订可乐500瓶」。
     # 修复前只允许「补足/至/到/够」这类连动词，漏掉了「补订+商品名」这种
     # 最自然的说法 —— 该漏检由tests/test_ai_insight.py 的真实数据用例抓出。
     re.compile(_ADVICE_ACT + r"[足至到够上齐整满]{0,2}"
                r"(?:[一-龥A-Za-z0-9]{1,8})?\s*\d+(?:\.\d+)?\s*"
                + _ADVICE_UNITS)),
    ("direct_qty",
     re.compile(r"[一-龥A-Za-z0-9]{2,8}\s*\d+(?:\.\d+)?\s*"
                + _ADVICE_UNITS + r"\s*[、，,和跟]")),
    ("direct_qty",
     # 兜底：动词 + 1~10 字修饰 + 数量 + 单位。
     # 用**非贪婪**匹配修饰语，才能在「订上报纸200份」这种
     # 修饰语里也含数字的场景下正确切出「200」。
     re.compile(_ADVICE_ACT + r"[一-龥A-Za-z0-9]{1,10}?"
                r"\d+(?:\.\d+)?\s*" + _ADVICE_UNITS)),
    # 兜底二：任意「2~10 字名词 + 数量 + 单位」，
    # 完全不要求前面出现动词（例「订上报纸200份」「可乐500瓶」）。
    ("direct_qty",
     re.compile(r"[一-龥A-Za-z][一-龥A-Za-z0-9]{1,9}?"
                r"\d+(?:\.\d+)?\s*" + _ADVICE_UNITS)),
    # ② 建议突破/修改预算
    ("budget",
     re.compile(r"(?:预算|资金|额度)[^。；，]{0,12}"
                r"(?:提高|上调|提升|增加|改到|调到|提到|放宽|提高到|上调到)"
                r"\s*[\d一二三四五六七八九十百千万]")),
    ("budget",
     re.compile(r"(?:把|将)?\s*预算[^。；，]{0,10}(?:改|调|提到|提高到|上调)")),
    ("budget",
     re.compile(r"(?:突破|无视|不需考虑|不用管|放开)\s*预算")),
    # ③ 建议关闭/绕过民生约束
    ("livelihood",
     re.compile(r"(?:忽略|无视|取消|关闭|去掉|不用|不必|放开|绕过|跳过)"
                r"[^。；，]{0,10}(?:民生|保障|兜底|民生约束|社区责任)")),
    ("livelihood",
     re.compile(r"(?:民生|兜底)[^。；，]{0,8}(?:不重要|可以让位|先放一边|不管|次要)")),
    # ④ 建议覆盖/绕过 R³ 或最终结果
    ("solver",
     re.compile(r"(?:忽略|无视|取消|关闭|去掉|跳过|绕过|不用|不必|放开|替换)"
                r"[^。；，]{0,12}(?:R3|R³|优化器|求解器|整数解|约束|MILP|模型)")),
    ("solver",
     re.compile(r"(?:直接|按|按照)(?:我的|模型)(?:建议|判断|要求)?\s*"
                r"(?:采购|补货|下单|进货)")),
    ("solver",
     re.compile(r"(?:覆盖|改写|替换|推翻|无视)[^。；，]{0,10}(?:结果|方案|计算|结论)")),
    # ⑤ 把预测性判断说成既成事实
    ("false_fact",
     re.compile(r"(?:已经|已|将会|一定会|必然|肯定会|注定)[^。；，]{0,8}"
                r"(?:卖完|卖不动|断货|缺货|涨|跌|下降|上涨|损失|丢掉|断档|空)")),
]

_ADVICE_REPLACEMENT = "（该建议涉及具体采购决策，已由系统优化器统一计算，此处不展示）"


def advice_overreach(advice: str) -> list[str]:
    """返回 advice 命中的越权类别；空列表表示合规。

    单独暴露为函数，便于测试与答辩演示逐条核验。
    """
    text = str(advice or "")
    if not text:
        return []
    hits = []
    for name, rx in _ADVICE_OVERREACH:
        if rx.search(text) and name not in hits:
            hits.append(name)
    return hits


def _sanitize_advice(advice) -> str:
    """把越权 advice 替换为中性说明；合规 advice 原样保留（截断 60 字）。"""
    text = str(advice or "").strip()
    if not text:
        return ""
    if advice_overreach(text):
        return _ADVICE_REPLACEMENT
    return text[:60]


def _sanitize(items, facts: str, item_names: list[str] | None = None) -> list[dict]:
    """校验模型输出：必须有依据、字段合法、去重，且依据与实体绑定。

    防幻觉的关键闸门是「**实体 + 指标 + 数字** 三者绑定」：
    仅校验「数字存在于 facts」会被「借数字」绕过 —— 例如 facts 里矿泉水是 12、
    牛奶是 30，模型说「牛奶只剩 12 件」在旧逻辑下会被放行。

    item_names：plan 里的真实商品名列表，用于精确切分事实文本、定位实体。
    传空时退化为旧的扁平数字校验（保持向后兼容，但不再有绑定校验）。
    """
    valid_cats = {"demand", "stock", "profit", "liveliness", "supply"}
    nums = set(re.findall(_NUM, facts))
    index = _build_fact_index(facts, item_names)
    bind = bool(index)                   # 能否做实体绑定校验
    out, seen = [], set()
    for it in items or []:
        if not isinstance(it, dict):
            continue
        title = str(it.get("title") or "").strip()
        insight = str(it.get("insight") or "").strip()
        evidence = str(it.get("evidence") or "").strip()
        if not title or not insight:
            continue
        if evidence and nums:
            if bind:
                # 强校验：数字必须绑定在它自己点名的实体上
                if not _evidence_is_bound(evidence, insight, index, nums):
                    continue
            else:
                # 弱校验（无商品名可索引时）：每一个数字都必须是真实存在的
                # （不放宽成「至少一个命中」，否则真数字会掩护假数字）
                ev_nums = set(re.findall(_NUM, evidence))
                if ev_nums and not ev_nums.issubset(nums):
                    continue
        cat = str(it.get("category") or "stock").strip().lower()
        sev = str(it.get("severity") or "medium").strip().lower()
        key = title[:20]
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "category": cat if cat in valid_cats else "stock",
            "severity": sev if sev in SEVERITIES else "medium",
            "title": title[:40],
            "insight": insight[:200],
            "evidence": evidence[:80] or "（模型未给出依据）",
            "advice": _sanitize_advice(it.get("advice")),
        })
    return out[:6]


def llm_insight(plan: dict, extra: dict | None = None) -> dict | None:
    """调用大模型做经营洞察；失败或产出不可用时返回 None（调用方降级）。"""
    if not llm.is_enabled():
        return None
    facts = build_facts(plan, extra)
    try:
        data = llm.chat_json(_SYSTEM,
                             "以下是店主店铺的真实经营数据，请分析：\n\n" + facts,
                             max_tokens=900)
    except Exception:
        # 与 ai_events.llm_parse 同理：超时/网络错误必须降级，
        # 不能打断补货主流程（docstring 已承诺「失败返回 None」）。
        return None
    if not isinstance(data, dict):
        return None
    names = [str(it.get("name") or "").strip()
             for it in (plan.get("items") or []) if str(it.get("name") or "").strip()]
    items = _sanitize(data.get("insights"), facts, names)
    digest = str(data.get("digest") or "").strip()[:200]
    # 模型给了结构但内容全被校验干掉（幻觉数字 / 字段非法 / 空列表）时，
    # 不能拿一个「零条洞察」的结果糊弄页面—— 降级到规则体检，至少有真话可说。
    if not items and not digest:
        return None
    return {
        "insights": items,
        "digest": digest or "模型未给出整体判断",
        "source": "llm",
        "model": LLM_MODEL,
        "facts": facts,
    }


def analyze(plan: dict, extra: dict | None = None) -> dict:
    """AI 业务洞察统一入口：模型优先，失败降级规则。"""
    result = llm_insight(plan, extra)
    if result is None:
        result = rule_insight(plan)
        result["facts"] = build_facts(plan, extra)
    return result
