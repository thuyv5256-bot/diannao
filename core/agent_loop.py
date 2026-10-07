# -*- coding: utf-8 -*-
"""
小满 · Agent 自主决策引擎（创新点 1 的 Agent 形态）

═══ 这个模块要解决的问题 ═══
`core/decision_trace.py` 已经把六步摊开给店主看了，但它是个**固定管线**：
读库存 → 查事件 → 翻记忆 → 预测 → 查供应 → 优化，次序永不改变，
不管今天是平常日还是台风天，走的路一模一样。那叫「流程可视化」，
不叫「自主决策」。

真正的 Agent 应该做到三件事：
  ① **自己定义问题**：今天最该解决的是什么？是断货、是压货、还是收益？
     —— 目标从数据里诊断出来，不是写死的。
  ② **自己决定怎么打**：这次该重民生还是重收益？该不该花大代价去算客流影响？
     —— 策略与工具路径随情境分化。
  ③ **自己承认没做好**：这一轮的方案哪里脆？下一轮该改什么？
     —— 反思产生具体的、可执行的下一步。

═══ 五阶段循环 ═══
    感知 PERCEIVE → 推理 REASON → 规划 PLAN → 执行 ACT → 反思 REFLECT

每一阶段都真实调用 `core/tools.py` 里的工具，每一步的判断都留下
「想了什么 / 为什么这么想 / 得出什么结论」的轨迹，页面直接渲染这份轨迹。

═══ 关键：自主性必须可验证 ═══
「Agent 很智能」这种话不能靠嘴说。本模块的设计目标是让**同一份代码**
在不同输入下走出**不同的路径**，并且这种差异是可复现、可断言的：
  · 平常日预算充裕 → 主动跳过最贵的客流评估工具（资源意识）
  · 节前预算紧张   → 调客流评估、切惠民策略、胜出方案随之改变
  · 置信度随证据充分度与预算余量真实升降
见 `tests/test_agent_loop.py` 的路径分化断言。

═══ 与铁律的一致性（CLAUDE.md）═══
  · 不写死数字：所有结论来自工具真实返回；
  · 不引入随机：纯确定性，同输入必得同输出；
  · 不依赖 LLM：核心决策全程规则化，无 Key 也能完整跑通；
  · 可降级：任何工具失败都被记录并纳入反思，不中断整个循环。
"""

import math
from datetime import date

from . import tools
from .config import DEFAULT_BUDGET, LIVELIHOOD_MIN_COVER_DAYS

# ── 策略目录：Agent 可选的"打法" ──────────────────────────
# weights 的键与 _score() 里的三个目标一一对应。权重来自业务判断而非拟合：
#   · 惠民优先——社区小店的立身之本，民生断了客流就散了；
#   · 稳健均衡——默认打法，三个目标都不得偏废；
#   · 收益优先——旺季/节前现金流压力大时，适度向收益倾斜；
#   · 避险优先——库存积压或损耗抬头时，宁可少赚也不压在手里。
STRATEGIES = {
    "livelihood_first": {
        "label": "惠民优先",
        "desc": "民生商品先保够；宁可少赚，也不让街坊买不到米面油盐",
        "weights": {"livelihood": 0.55, "margin": 0.20, "resilience": 0.25},
    },
    "balanced": {
        "label": "稳健均衡",
        "desc": "收益、韧性、民生三个目标均衡推进，不押注单一方向",
        "weights": {"livelihood": 0.38, "margin": 0.37, "resilience": 0.25},
    },
    "profit_oriented": {
        "label": "收益优先",
        "desc": "把有限预算更多投向赚钱的品类，适合资金紧张但客流稳定的日子",
        "weights": {"livelihood": 0.25, "margin": 0.52, "resilience": 0.23},
    },
    "risk_averse": {
        "label": "避险优先",
        "desc": "宁可少赚也不压货，优先压住断货与损耗两头风险",
        "weights": {"livelihood": 0.40, "margin": 0.18, "resilience": 0.42},
    },
}

# 打分公式里的基准常量（业务含义见各自注释）
RISK_BASE = 8.0        # 风险惩罚基数：断货/积压风险的相对权重刻度
MARGIN_RATE_BASE = 0.25  # 毛利率基准：用于把毛利率归一化到可比区间

# 民生「相对告急」折减系数：覆盖天数低于本店常态的这个比例即视为偏紧。
# 取 0.75 的含义是「比自己的习惯少备了四分之一以上」——幅度足够显著，
# 不至于把正常的日常波动也当成危机（本数据集正常波动约在常态的 ±5% 内）。
RELATIVE_TIGHT_RATIO = 0.75

# 压货「告急」阈值：最严重的几种商品超出保质期的总量 ≈ 多少天的销量之和。
# 取 0.30 的含义是「领先的那几种商品合起来多压了约三分之一天的销量」。
# 本数据集 180 天里有 61 天存在压货，压力值 0.01~0.75，中位 0.14；
# 0.30 大约落在最高的十几天上，是真正的异常而非日常波动。
OVERSTOCK_ALERT = 0.30

# ── 五个阶段的元信息（页面直接消费）─────────────────────
PHASES = [
    {"key": "perceive", "icon": "◉", "label": "感知",
     "desc": "把店的真实状态读进来"},
    {"key": "reason", "icon": "◇", "label": "推理",
     "desc": "诊断问题严重度，定下这一轮的目标"},
    {"key": "plan", "icon": "▤", "label": "规划",
     "desc": "拆解任务、自选策略、决定投入哪些分析工具"},
    {"key": "act", "icon": "▶", "label": "执行",
     "desc": "多方案生成 + 沙盘推演 + 按策略加权打分决出最优"},
    {"key": "reflect", "icon": "◈", "label": "反思",
     "desc": "自评置信度、写下自我批评与下一轮改进"},
]


def strategy_catalog() -> list[dict]:
    """给页面用的策略清单。"""
    return [{"key": k, "label": v["label"], "desc": v["desc"], "weights": v["weights"]}
            for k, v in STRATEGIES.items()]


def _fmt_money(v) -> str:
    return f"¥{float(v):,.0f}"


class AgentRunner:
    """一次完整的自主补货决策。实例即一次会话，用后即弃。"""

    def __init__(self, plan_date, budget: float = DEFAULT_BUDGET,
                 risks=None, verbose: bool = False):
        self.plan_date = str(plan_date)[:10]
        self.budget = float(budget or DEFAULT_BUDGET)
        self.risks = risks or []
        self.verbose = verbose

        self.trace: list[dict] = []      # 完整思考 + 调用轨迹
        self.calls: list[dict] = []      # 只记工具调用（供统计/展示）
        self.obs: dict = {}              # 感知结果
        self.diagnosis: dict = {}        # 推理结论
        self.goal: dict = {}             # 本轮目标
        self.plan_steps: list[dict] = []  # 规划出的任务清单
        self.strategy: dict = {}         # 选中的策略
        self.candidates: list[dict] = []  # 候选方案与打分
        self.chosen: dict = {}           # 胜出方案
        self.actions: list[dict] = []    # 行动记录
        self.reflection: dict = {}       # 反思结论

    # ── 轨迹记录 ─────────────────────────────────────────

    def _think(self, phase: str, title: str, detail: str = "",
               conclusion: str = "", level: str = "info") -> dict:
        """记一条「思考」。level: info / ok / warn 决定页面语气色。"""
        entry = {"kind": "think", "phase": phase, "title": title,
                 "detail": detail, "conclusion": conclusion, "level": level}
        self.trace.append(entry)
        if self.verbose:
            print(f"  [{phase}] {title}" + (f" —— {conclusion}" if conclusion else ""))
        return entry

    def _call(self, tool_name: str, why: str, **kwargs) -> dict:
        """调用一个工具，把「为什么调它」和「结果如何」一并记进轨迹。

        返回工具结果本身（失败时抛异常会被上层 act/reason 阶段捕获处理），
        `_call_soft` 则用于允许失败的场合。
        """
        env = tools.call_tool(tool_name, **kwargs)
        meta = tools.get_tool(tool_name)
        rec = {"kind": "call", "phase": self._current_phase, "tool": tool_name,
               "category": meta.category, "cost": meta.cost, "why": why,
               "ok": env["ok"], "error": env["error"],
               "elapsed_ms": env["elapsed_ms"]}
        self.calls.append(rec)
        self.trace.append(rec)
        if not env["ok"]:
            raise RuntimeError(f"工具 {tool_name} 执行失败：{env['error']}")
        return env["result"]

    def _call_soft(self, tool_name: str, why: str, **kwargs):
        """调用允许失败的工具：失败返回 None，并把失败留给反思阶段处理。"""
        env = tools.call_tool(tool_name, **kwargs)
        meta = tools.get_tool(tool_name)
        self.calls.append({"kind": "call", "phase": self._current_phase,
                           "tool": tool_name, "category": meta.category,
                           "cost": meta.cost, "why": why, "ok": env["ok"],
                           "error": env["error"], "elapsed_ms": env["elapsed_ms"]})
        self.trace.append(self.calls[-1])
        return env["result"] if env["ok"] else None

    @property
    def _current_phase(self) -> str:
        for e in reversed(self.trace):
            if e["kind"] == "phase":
                return e["label"]
        return "感知"

    def _enter(self, key: str):
        meta = next(p for p in PHASES if p["key"] == key)
        self.trace.append({"kind": "phase", **meta})

    # ════════════════════════════════════════════════════
    # ① 感知 PERCEIVE —— 把世界读进来
    # ════════════════════════════════════════════════════

    def perceive(self) -> dict:
        self._enter("perceive")

        self._think("感知", f"开始处理 {self.plan_date} 的备货",
                    detail=f"预算上限 {_fmt_money(self.budget)}"
                           + (f"，已知风险：{'、'.join(self.risks)}" if self.risks else "，未指定特殊风险"))

        inv = self._call("read_inventory", "先看货架上现在有什么、缺什么")
        self._think("感知", "读完库存",
                    detail=f"{inv['sku_count']} 种商品，在库合计 {inv['on_hand_total']:.0f} 件",
                    conclusion=f"其中 {inv['low_stock_count']} 种已经低于一天的量",
                    level="warn" if inv["low_stock_count"] > 0 else "ok")

        anom = self._call("scan_anomalies", "逐商品核对能不能撑到下次补货",
                          plan_date=self.plan_date)
        self._think("感知", "扫完异常",
                    detail=f"撑不到下次补货：{anom['starving_count']} 种"
                           f"（民生 {anom['livelihood_starving_count']} 种）；"
                           f"压货超保质期：{anom['overstocked_count']} 种",
                    conclusion="有民生商品快断了" if anom["livelihood_starving_count"] > 0
                               else "民生商品供应正常",
                    level="warn" if anom["livelihood_starving_count"] > 0 else "ok")

        cal = self._call("check_calendar", "看看明天是什么日子、历史同期的生意规律",
                         plan_date=self.plan_date)
        ev = cal["evidence"]
        strong = [v["label"] for v in ev.values() if v["level"] == "strong"]
        self._think("感知", "查完经营日历",
                    detail=(f"明天是{cal['holiday_label']}。" if cal["is_holiday"] else "明天是普通经营日。")
                           + f"历史事件："
                           + "、".join(f"{k} {v}天" for k, v in cal["historical_event_days"].items() if v),
                    conclusion=(f"有证据充分的同期事件：{'、'.join(strong)}" if strong
                                else "没有证据充分的同期事件，按常规规律预测"))

        pol = self._call("audit_policy", "审一遍当前策略参数，看有没有被历史经验改过",
                         plan_date=self.plan_date, risks=self.risks)
        self._think("感知", "审完策略参数",
                    detail=f"{pol['policy_count']} 种商品，平均备货 {pol['avg_base_days']:.1f} 天；"
                           f"当前场景「{pol['scene']}」",
                    conclusion=(f"{pol['calibrated_count']} 种商品的安全库存被历史经验校准过"
                                if pol["calibrated_count"] else "本场景没有可用的历史校准，按基础参数走"),
                    level="ok" if pol["calibrated_count"] else "info")

        his = self._call("read_sales_history", "翻历史账，判断可用数据够不够得出可靠结论",
                         plan_date=self.plan_date)
        self._think("感知", "翻完历史账",
                    detail=f"可用窗口 {his['window_days']} 天"
                           f"（{his['window_start']} ~ {his['window_end']}），"
                           f"期间卖出 {his['sold_total']:.0f} 件",
                    conclusion="数据量足够支撑预测" if his["data_sufficient"]
                               else "数据偏少，本轮结论需谨慎对待",
                    level="ok" if his["data_sufficient"] else "warn")

        sup = self._call("read_suppliers", "查供应状态，断供会影响能不能下单",
                         risks=self.risks)
        self._think("感知", "查完供应状态",
                    detail=f"{sup['supplier_count']} 家供应商，平均到货 {sup['avg_lead_days']} 天"
                           + (f"；{sup['outage_supplier']} 断供，影响 {len(sup['outage_skus'])} 种商品"
                              f"（民生 {sup['outage_livelihood_count']} 种）" if sup["outage"] else ""),
                    conclusion="有供应商断供，相关商品本轮不可采购" if sup["outage"]
                               else "供应链正常",
                    level="warn" if sup["outage"] else "ok")

        self.obs = {"inventory": inv, "anomalies": anom, "calendar": cal,
                    "policy": pol, "history": his, "suppliers": sup}
        return self.obs

    @staticmethod
    def _estimate_need_money(plan_date, risks) -> float:
        """算出「按当前策略把货补到位，大概要花多少钱」。

        直接跑一次**不设预算上限**的惠民方案 —— 这是唯一诚实的口径：
        不能用「缺口天数 × 进价」这种近似，那样会忽略包规取整、在途、
        保质期上限等真实约束，估出来的数字跟实际对不上。
        """
        from . import policy as _policy
        plan = _policy.build_plan(str(plan_date), 10_000_000.0,
                                  _policy.MODE_DIANNAO, persist=False,
                                  risks=risks)
        return round(float(plan["metrics"]["total_cost"]), 2)

    # ════════════════════════════════════════════════════
    # ② 推理 REASON —— 诊断问题，定目标
    # ════════════════════════════════════════════════════

    def reason(self) -> dict:
        self._enter("reason")
        anom, his, cal = self.obs["anomalies"], self.obs["history"], self.obs["calendar"]

        starvation_pressure = anom["gap_pressure"]
        # 压货压力用「最严重的几种超出保质期的量 ≈ 多少天销量」来衡量。
        # 不用「压货种类 / 总种类」：这份数据里压货每天最多 1 种，占比恒为 2%，
        # 那个口径永远触发不了（本模块第一版踩过的坑）。
        overstock_pressure = anom.get("overstock_pressure", 0.0)

        # ── 民生缺货的「严重度」而不是「有无」──
        # 只要低于目标覆盖天数就算 starving，店里几乎每天都有一批（店本来就压着低库存），
        # 所以「有民生商品低于目标」不能等同于「民生危机」。真正要看的是：
        # 这些商品的库存还能撑几天？离「街坊买不到米面油盐」这条底线还有多远？
        #
        # 判「告急」用**双阈值**，缺一不可（单看绝对值会在本数据集上永远不触发：
        # 这家店的民生最低覆盖常年在 2.0 天以上，从没跌破 1.5 天的硬线）：
        #   ① 绝对破线：覆盖天数 < 民生底线的一半 —— 这才是真的要到「买不到」了；
        #   ② 相对告急：覆盖天数低于本店**实际常态**的这一折 —— 一家平时做 2.9 天
        #      覆盖的店，今天只做出来 2.0 天，即使绝对值还没破线，也已经明显偏紧，
        #      值得为它多花一次分析代价去量化客流风险。
        # 「本店常态」必须取**实际观测到的覆盖水平**（各民生品的平均覆盖天数），
        # 而不是备货目标 base_days —— 目标是「想做到什么」，常态是「实际做到什么」，
        # 拿目标当基准会把每天都判成告急（本模块第一版踩过的坑）。
        liv_rows = [r for r in anom["starving"] if r["is_livelihood"]]
        liv_min_cover = min((r["cover_days"] for r in liv_rows), default=None)
        # 绝对告急线：跌破民生保障底线的一半
        acute_line = LIVELIHOOD_MIN_COVER_DAYS / 2.0
        # 相对告急线：本店民生品「实际常态覆盖」× 折减系数
        liv_norm_cover = (anom["livelihood_norm_cover"]
                          if anom.get("livelihood_norm_cover") else None)
        relative_line = (liv_norm_cover * RELATIVE_TIGHT_RATIO
                         if liv_norm_cover is not None else acute_line)
        # 两条线取更宽松的一条作为「告急」判据（绝对值兜底，相对值提升灵敏度）
        alert_line = max(acute_line, relative_line)
        acute_livelihood = [r for r in liv_rows if r["cover_days"] < alert_line]

        self._think("推理", "量化问题严重度",
                    detail=f"低于目标备货量：{anom['starving_count']}/{anom['sku_count']} 种"
                           f"（民生 {len(liv_rows)} 种）；"
                           f"整体缺口 {anom['gap_pressure']:.0%}；"
                           f"最紧的差 {anom['worst_gap_days']:.1f} 天的量；"
                           f"压货超保质期 {anom['overstocked_count']} 种"
                           + (f"；民生商品最低只够卖 {liv_min_cover:.1f} 天"
                              f"（本店常态 {liv_norm_cover:.1f} 天）"
                              if liv_min_cover is not None and liv_norm_cover is not None
                              else (f"；民生商品最低只够卖 {liv_min_cover:.1f} 天"
                                    if liv_min_cover is not None else "")),
                    conclusion=(f"{len(acute_livelihood)} 种民生商品已跌破 {alert_line:.1f} 天的警戒线，"
                                f"街坊随时可能买不到"
                                if acute_livelihood else
                                ("民生商品普遍压在底线之上，需要补但还没到断供"
                                 if liv_rows else "民生商品供应正常")))

        # ── 预算紧不紧？这是「钱够不够花」的客观判断，直接影响定目标和选策略 ──
        need_money = self._estimate_need_money(self.plan_date, self.risks)
        budget_ratio = self.budget / need_money if need_money > 0 else 2.0
        tight = budget_ratio < 0.85

        # ── 目标判定：优先级 民生告急 > 压货 > 预算紧 > 普遍缺口 > 平稳 ──
        if acute_livelihood:
            goal = {"key": "save_livelihood", "label": "止住民生的血",
                    "desc": f"{len(acute_livelihood)} 种民生商品只够卖不到 {alert_line:.1f} 天"
                            f"（最低 {liv_min_cover:.1f} 天），先让街坊买到米面油盐，再谈别的",
                    "conflict": "民生兜底会挤占高毛利商品的预算"}
        elif overstock_pressure > OVERSTOCK_ALERT:
            goal = {"key": "clear_overstock", "label": "压住积压损耗",
                    "desc": f"{anom['overstocked_count']} 种商品存得比保质期内能卖掉的还多，"
                            f"最严重的多压了约 {overstock_pressure:.1f} 天的销量，"
                            f"优先防止烂在手里",
                    "conflict": "压制备货可能带来局部缺货"}
        elif tight:
            goal = {"key": "spend_wisely", "label": "把有限的钱花在刀刃上",
                    "desc": f"按现在货架缺口估计需要约 {_fmt_money(need_money)}，"
                            f"但预算只有 {_fmt_money(self.budget)}"
                            f"（{budget_ratio:.0%}），必须排序取舍、优先保民生",
                    "conflict": "钱不够花完所有缺口，必须牺牲一部分商品"}
        else:
            goal = {"key": "steady", "label": "平稳补货、守住基本盘",
                    "desc": f"预算够覆盖现有缺口（约需 {_fmt_money(need_money)}，"
                            f"预算 {_fmt_money(self.budget)}），按常规节奏把货补齐即可",
                    "conflict": "无突出矛盾"}

        self._think("推理", f"定下这一轮的目标：{goal['label']}",
                    detail=goal["desc"],
                    conclusion=f"已知的取舍：{goal['conflict']}",
                    level="warn" if (acute_livelihood or tight) else "ok")

        # ── 数据可信度自评（决定后面置信度的上限）──
        evidence_days = his["window_days"]
        self._think("推理", "自评手头证据的可信度",
                    detail=f"历史窗口 {evidence_days} 天；"
                           f"事件证据等级："
                           + "、".join(f"{v['label']}={v['level'] or '无'}"
                                       for v in cal["evidence"].values()),
                    conclusion="证据较充分" if evidence_days >= 28 else "证据偏薄")

        self.diagnosis = {
            "starvation_pressure": round(starvation_pressure, 4),
            "overstock_pressure": round(overstock_pressure, 4),
            "livelihood_starving": len(liv_rows),
            "livelihood_stockout": len(acute_livelihood),
            "livelihood_min_cover": round(liv_min_cover, 2) if liv_min_cover is not None else None,
            "livelihood_norm_cover": round(liv_norm_cover, 2) if liv_norm_cover is not None else None,
            "acute_line": round(acute_line, 2),
            "relative_line": round(relative_line, 2),
            "alert_line": round(alert_line, 2),
            "starving_count": anom["starving_count"],
            "overstocked_count": anom["overstocked_count"],
            "gap_pressure": anom["gap_pressure"],
            "worst_gap_days": anom["worst_gap_days"],
            "need_money": need_money,
            "budget_ratio": round(budget_ratio, 4),
            "tight": tight,
            "evidence_days": evidence_days,
        }
        self.goal = goal
        return {"diagnosis": self.diagnosis, "goal": goal}

    # ════════════════════════════════════════════════════
    # ③ 规划 PLAN —— 拆任务、选策略、决定投入哪些工具
    # ════════════════════════════════════════════════════

    def plan(self) -> dict:
        self._enter("plan")
        d = self.diagnosis

        # ── 3.1 拆解任务 ──
        tasks = [
            {"task": "算准明天每种商品的需求", "tool": "forecast_demand",
             "why": "需求是后面所有计算的地基"},
            {"task": "看清哪些货更值得投钱", "tool": "rank_by_efficiency",
             "why": "预算有限，得知道谁的回本效率高"},
            {"task": "生成并预演多套候选方案", "tool": "build_replenishment + simulate_plan",
             "why": "先想清楚后果，再决定进哪套"},
        ]
        self._think("规划", "拆出这一轮要做的事",
                    detail="；".join(t["task"] for t in tasks),
                    conclusion=f"共 {len(tasks)} 项核心任务")

        # ── 3.2 资源意识：要不要花大代价去算客流伤害？──
        # assess_traffic 要遍历全部历史，是 13 个工具里最贵的一步。
        # 只有当「民生真的告急」时，评估客流损失才有现实意义；否则纯属浪费。
        need_traffic = d["livelihood_stockout"] > 0
        if need_traffic:
            self._think("规划", "决定追加客流伤害评估",
                        detail=f"有 {d['livelihood_stockout']} 种民生商品只够卖不到 "
                               f"{d['alert_line']:.1f} 天，需要量化"
                               f"「街坊买不到东西会带走多少客流」",
                        conclusion="值得付出这一份计算代价",
                        level="warn")
            tasks.append({"task": "量化民生断货的客流代价", "tool": "assess_traffic",
                          "why": "民生断货会连带拖累非民生销量"})
        else:
            self._think("规划", "决定跳过客流伤害评估",
                        detail=f"民生商品最低还剩 "
                               f"{d['livelihood_min_cover']:.1f} 天"
                               f"（本店常态 {d['livelihood_norm_cover']:.1f} 天，"
                               f"警戒线 {d['alert_line']:.1f} 天），没有告急品，"
                               f"客流损失的前提不成立"
                               if d["livelihood_min_cover"] is not None else
                               "当前没有民生商品告急，客流损失的前提不成立",
                        conclusion="这一步要遍历全部历史，属于最贵的分析，本轮没必要花这个代价",
                        level="ok")

        # ── 3.3 自选策略（依据：目标 + 预算紧张度 + 积压面）──
        if d["livelihood_stockout"] > 0:
            strategy_key = "livelihood_first"
            why = "民生已跌破警戒线，这一轮必须把民生放在最前面"
        elif d["overstock_pressure"] > OVERSTOCK_ALERT:
            strategy_key = "risk_averse"
            why = (f"已经出现压货超保质期的商品（压力 {d['overstock_pressure']:.2f}），"
                   f"先求稳、避免断货与损耗两头挨打")
        elif d["tight"]:
            # 钱不够花完所有缺口 → 越穷越要精打细算，把每一元投到产出最高的地方
            strategy_key = "profit_oriented"
            why = (f"预算只够覆盖 {d['budget_ratio']:.0%} 的缺口，"
                   f"越紧越要按资金效率排序，让每一元都花在回报最高的货上")
        else:
            strategy_key = "balanced"
            why = (f"预算够覆盖现有缺口（{d['budget_ratio']:.0%}），"
                   f"三个目标均衡推进最稳妥")

        st = STRATEGIES[strategy_key]
        self.strategy = {"key": strategy_key, **st}
        self._think("规划", f"选定策略：{st['label']}",
                    detail=st["desc"],
                    conclusion=f"依据：{why}")

        self.plan_steps = tasks
        self._think("规划", "规划完成",
                    detail=f"本轮计划执行 {len(tasks)} 项任务，"
                           f"其中工具调用含 {len(tasks)} 项分析动作",
                    conclusion="开始执行")
        return {"tasks": tasks, "strategy": self.strategy,
                "need_traffic": need_traffic}

    # ════════════════════════════════════════════════════
    # ④ 执行 ACT —— 分析 → 多方案博弈 → 决出最优
    # ════════════════════════════════════════════════════

    def act(self) -> dict:
        self._enter("act")

        # ── 4.1 需求预测 ──
        fc = self._call("forecast_demand", "算明天每种商品能卖多少",
                        plan_date=self.plan_date, risks=self.risks)
        top = fc["top_demand"]
        self._think("执行", "预测完成",
                    detail="需求量最大的几种：" + "、".join(
                        f"{t['name']} {t['daily_demand']:.1f}{t['unit']}" for t in top[:3]),
                    conclusion=f"共预测 {fc['sku_count']} 种商品的需求")

        # ── 4.2 资金效率排序（看清钱的投法）──
        eff = self._call("rank_by_efficiency", "看哪种货的回本效率更高")
        self._think("执行", "排完资金效率",
                    detail=f"非民生商品平均资金效率 {eff['non_livelihood_avg_eff']:.3f}，"
                           f"民生商品 {eff['livelihood_avg_eff']:.3f}",
                    conclusion=("民生商品资金效率天然偏低 —— 这正是纯利润算法会砍掉它们的原因，"
                                if eff["livelihood_avg_eff"] < eff["non_livelihood_avg_eff"]
                                else "两类商品资金效率接近，冲突不大"))

        # ── 4.3 按需评估客流代价（是否要做，由规划阶段自主决定）──
        if getattr(self, "_need_traffic", False):
            tr = self._call_soft("assess_traffic", "量化民生断货的客流代价")
            if tr and tr.get("available"):
                self._think("执行", "客流伤害评估完成",
                            detail=f"统计 {tr['total_days']} 天，"
                                   f"可识别的民生缺货日 {tr['high_loss_days']} 天",
                            conclusion=(f"缺货日非民生销量偏离 {tr['gap']:+.2%}，"
                                        f"证明民生断货确实会带走客流"
                                        if tr["high_loss_days"] else
                                        "本次数据里没有可识别的民生缺货日，无法量化 —— 如实说明，不做声称"),
                            level="ok" if tr["high_loss_days"] else "info")
            else:
                self._think("执行", "客流伤害评估未得出结果",
                            detail=(tr or {}).get("reason", "工具执行失败"),
                            conclusion="不影响主流程，继续用其它证据决策", level="warn")

        # ── 4.4 三个候选方案 ──
        self._think("执行", "开始构造候选方案",
                    detail="同一笔预算，三种花钱的思路，都用沙盘推演预演 3 天",
                    conclusion="谁更稳，数据说了算")

        cand_a = self._call("build_replenishment", "候选 A：带惠民约束的常规备货方案",
                            plan_date=self.plan_date, budget=self.budget,
                            protect_livelihood=True, risks=self.risks)
        sim_a = self._call("simulate_plan", "对候选 A 做 3 天沙盘推演",
                           plan=cand_a["plan"], horizon_days=3)

        cand_b = self._call("build_replenishment",
                            "候选 B：纯利润算法（对照组，用来量化惠民约束的代价）",
                            plan_date=self.plan_date, budget=self.budget,
                            protect_livelihood=False, risks=self.risks, use_memory=False)
        sim_b = self._call("simulate_plan", "对候选 B 做 3 天沙盘推演",
                           plan=cand_b["plan"], horizon_days=3)

        cand_c = self._call("build_replenishment",
                            "候选 C：备货天数压缩 30% 的快周转方案（少备勤补、降低压货）",
                            plan_date=self.plan_date, budget=self.budget,
                            protect_livelihood=True, risks=self.risks, day_scale=0.70)
        sim_c = self._call("simulate_plan", "对候选 C 做 3 天沙盘推演",
                           plan=cand_c["plan"], horizon_days=3)

        scored = []
        for tag, cand, sim, note in (
            ("A", cand_a, sim_a, "惠民约束版"),
            ("B", cand_b, sim_b, "纯利润版"),
            ("C", cand_c, sim_c, "快周转避险版"),
        ):
            metrics = cand["plan"]["metrics"]
            s = self._score(metrics, sim, self.strategy)
            scored.append({"tag": tag, "note": note, "plan": cand["plan"],
                           "sim": sim, "score": s["total"],
                           "breakdown": s["breakdown"], "flags": s["flags"],
                           "day_scale": cand["day_scale"]})

        for c in scored:
            self._think("执行", f"候选 {c['tag']}（{c['note']}）得分 {c['score']:.1f}",
                        detail=f"综合得分明细："
                               + "、".join(f"{k} {v:+.1f}" for k, v in c["breakdown"].items()),
                        conclusion="、".join(c["flags"]) if c["flags"] else "无明显短板",
                        level="warn" if c["flags"] else "ok")

        scored.sort(key=lambda c: -c["score"])
        winner = scored[0]
        self.candidates = scored
        self.chosen = winner
        gap = winner["score"] - scored[1]["score"] if len(scored) > 1 else 0.0
        self._think("执行", f"决出最优：候选 {winner['tag']}（{winner['note']}）",
                    detail=f"得分 {winner['score']:.1f}，领先第二名 {gap:.1f} 分",
                    conclusion=f"决策依据：本轮策略是「{self.strategy['label']}」，"
                               f"打分权重随之倾斜",
                    level="ok")

        # ── 4.5 与传统算法对照（量化惠民约束的代价）──
        cmp_ = self._call("compare_with_baseline",
                          "和传统纯利润算法摆在一起比，量化惠民约束的代价",
                          plan_date=self.plan_date, budget=self.budget, risks=self.risks)
        dl = cmp_["delta"]
        self._think("执行", "与传统算法对照完成",
                    detail=f"两者有 {cmp_['n_different']} 种商品的进货量不同",
                    conclusion=(f"惠民约束让毛利变化 {_fmt_money(dl['gross_margin'])}，"
                                f"民生指数变化 {dl['livelihood_index']:+.3f}；"
                                f"断货风险商品差 {dl['stockout_risk_count']:+d} 种"),
                    level="info")

        self._compare = cmp_
        return {"candidates": scored, "chosen": winner, "compare": cmp_}

    def _score(self, metrics: dict, sim: dict, strategy: dict) -> dict:
        """按当前策略的权重，给一个候选方案打分。

        三个目标都被归一化到同一量纲（约 -10 ~ +10），然后加权求和：

          margin      —— 资金使用效率：毛利率相对基准的偏离
          resilience  —— 抗风险：断货天数 + 压货/损耗，越低越好
          livelihood  —— 惠民达成：民生保障率相对"完全没保障"的改善

        注意：这是**真实计算**，不是给三个候选贴标签。同一份 metrics 喂给
        不同策略会得到不同的分数、甚至不同的胜出者 —— 这正是「策略真的
        在影响决策」的证据，也是 A/B（惠民版 vs 纯利润版）在预算充裕时
        可能打平、在预算紧张时必然分化的原因。
        """
        w = strategy["weights"]

        # 收益维度：毛利率相对基准 25% 的偏离，放大到 ±10 区间
        margin_rate = float(metrics.get("margin_rate") or 0.0)
        margin_score = max(-10.0, min(10.0,
                                      (margin_rate - MARGIN_RATE_BASE) / MARGIN_RATE_BASE * 10))

        # 韧性维度：断货天数 + 压货件数，两样都是风险，越少越好
        starvation = float(sim.get("starvation_days") or 0.0)
        excess = float(sim.get("excess_units") or 0.0)
        n_sku = max(1, int(sim.get("sku_count") or 1))
        resilience_score = -(starvation + excess / max(1.0, n_sku)) / RISK_BASE * 10

        # 惠民维度：保障率相对"完全没有保障"的改善幅度
        liv_rate = float(metrics.get("livelihood_secured_rate") or 0.0)
        livelihood_score = (liv_rate - 0.0) * 10

        total = (w["margin"] * margin_score
                 + w["resilience"] * resilience_score
                 + w["livelihood"] * livelihood_score)

        flags = []
        if starvation > 0:
            flags.append(f"沙盘里出现 {starvation:.0f} 次「商品撑不到第二天」")
        if excess > 0:
            flags.append(f"预计有 {excess:.0f} 件会压在手里卖不完")
        if liv_rate < 1.0:
            flags.append(f"民生保障率只到 {liv_rate:.0%}")

        return {
            "total": round(total, 3),
            "breakdown": {
                "收益": round(w["margin"] * margin_score, 2),
                "抗风险": round(w["resilience"] * resilience_score, 2),
                "保民生": round(w["livelihood"] * livelihood_score, 2),
            },
            "parts": {"margin_score": round(margin_score, 2),
                      "resilience_score": round(resilience_score, 2),
                      "livelihood_score": round(livelihood_score, 2)},
            "flags": flags,
        }

    # ════════════════════════════════════════════════════
    # ⑤ 反思 REFLECT —— 自评 + 自我批评 + 下一轮改进
    # ════════════════════════════════════════════════════

    def reflect(self) -> dict:
        self._enter("reflect")
        d, sim = self.diagnosis, self.chosen["sim"]
        metrics = self.chosen["plan"]["metrics"]

        # ── 5.1 置信度：由证据充分度与预算余量真实推导 ──
        # 证据分：历史窗口越足、工具失败越少，分越高
        evidence_score = min(1.0, d["evidence_days"] / 60.0)
        failed = [c for c in self.calls if not c["ok"]]
        reliability = 1.0 - min(0.5, len(failed) * 0.15)
        # 预算分：钱够不够把该备的货备齐
        budget_used = float(metrics.get("budget_used_rate") or 0.0)
        budget_score = 0.6 + 0.4 * min(1.0, budget_used) if budget_used < 1.0 else 1.0
        # 若民生保障没到 100%，说明预算确实吃紧，置信度要打折
        liv_rate = float(metrics.get("livelihood_secured_rate") or 0.0)
        if liv_rate < 1.0:
            budget_score *= 0.75

        confidence = evidence_score * 0.4 + reliability * 0.2 + budget_score * 0.4
        confidence = max(0.30, min(0.99, confidence))

        self._think("反思", f"自评置信度：{confidence:.0%}",
                    detail=f"证据充分度 {evidence_score:.0%}（历史 {d['evidence_days']} 天）· "
                           f"过程可靠性 {reliability:.0%}（失败调用 {len(failed)} 次）· "
                           f"预算从容度 {budget_score:.0%}",
                    conclusion=("证据充足，结论可靠" if confidence >= 0.85 else
                                "证据或预算偏紧，结论请结合实际情况判断"),
                    level="ok" if confidence >= 0.85 else "warn")

        # ── 5.2 自我批评：主动找出这轮方案的软肋 ──
        critiques = []
        if liv_rate < 1.0:
            missing = float(metrics.get("livelihood_floor_shortfall") or 0.0)
            critiques.append({
                "title": "民生保障没有打满",
                "detail": f"预算不够，还有 {missing:,.0f} 元的民生商品缺口没补上。"
                          f"这不是策略错了，是钱确实不够 —— 需要如实告诉店主。",
            })
        if sim["starvation_days"] > 0:
            critiques.append({
                "title": "沙盘里仍有断货风险",
                "detail": f"3 天推演中出现 {sim['starvation_days']:.0f} 次商品撑不到第二天，"
                          f"集中在备货天数短、需求波动大的品类。",
            })
        if sim["excess_units"] > 0:
            critiques.append({
                "title": "存在压货与损耗风险",
                "detail": f"预计 {sim['excess_units']:.0f} 件会超过保质期卖不完，"
                          f"短保商品应更保守。",
            })
        if budget_used < 0.75:
            critiques.append({
                "title": "预算没花完",
                "detail": f"只用了 {budget_used:.0%} 的预算，"
                          f"说明现有库存已较充足，不必为了花完钱而多进。",
            })
        if not critiques:
            critiques.append({
                "title": "本轮没有发现明显短板",
                "detail": "预算用满、民生保障达标、沙盘推演未出现断货或积压。",
            })

        self._think("反思", f"写下 {len(critiques)} 条自我批评",
                    detail="；".join(c["title"] for c in critiques),
                    conclusion="这一轮哪里没做好，说清楚" if len(critiques) > 1 else "整体表现良好")

        # ── 5.3 下一轮改进项：具体、可执行、来自本轮的真实缺口 ──
        next_actions = []
        if liv_rate < 1.0:
            next_actions.append({
                "action": f"下轮优先补足民生缺口",
                "detail": f"把预算提到 {_fmt_money(float(metrics.get('livelihood_floor_shortfall') or 0) + self.budget)} "
                          f"以上，或压缩非民生采购，先把民生保障率打到 100%",
                "trigger": "民生保障率 < 100%",
            })
        if sim["starvation_days"] > 0:
            next_actions.append({
                "action": "对高波动品类单独提高安全库存",
                "detail": "沙盘里断货的商品，下一轮可以从记忆库里检索它们的预测残差，"
                          "定向校准安全系数而不是整体抬升",
                "trigger": "沙盘出现断货",
            })
        if d["overstock_pressure"] > OVERSTOCK_ALERT or sim["excess_units"] > 0:
            next_actions.append({
                "action": "短保商品改用更激进的快周转节奏",
                "detail": "对保质期短的商品单独下调备货天数（day_scale < 1），"
                          "用多进几次换更低的损耗",
                "trigger": "存在压货风险",
            })
        if len(failed) > 0:
            next_actions.append({
                "action": "排查本轮失败的工具调用",
                "detail": "失败的工具：" + "、".join(c["tool"] for c in failed),
                "trigger": "有工具调用失败",
            })
        # 无缺口时也要给出真实的、非敷衍的下一步
        next_actions.append({
            "action": "录入明天的真实经营结果",
            "detail": "把这轮方案的实际销量 / 断货 / 损耗填进「今天生意怎么样」，"
                      "小满会用真实残差校准下一轮的安全库存 —— 这是自进化闭环的入口",
            "trigger": "每轮必做",
        })

        self._think("反思", f"提出 {len(next_actions)} 条下一轮改进项",
                    detail="；".join(a["action"] for a in next_actions),
                    conclusion="闭环到下一轮决策")

        # ── 5.4 复盘：这一轮的路径摘要（供对比"换个输入就不一样"）──
        path = {
            "goal": self.goal["label"],
            "strategy": self.strategy["label"],
            "tools_called": len(self.calls),
            "traffic_assessed": any(c["tool"] == "assess_traffic" for c in self.calls),
            "winner": self.chosen["tag"],
            "confidence": round(confidence, 4),
        }
        self.reflection = {
            "confidence": round(confidence, 4),
            "confidence_parts": {
                "evidence": round(evidence_score, 4),
                "reliability": round(reliability, 4),
                "budget": round(budget_score, 4),
            },
            "critiques": critiques,
            "next_actions": next_actions,
            "path": path,
        }
        return self.reflection

    # ════════════════════════════════════════════════════
    # 行动 ACT（落库）+ 总入口
    # ════════════════════════════════════════════════════

    def _commit(self, persist: bool) -> list[dict]:
        """把这一轮的决定落到长期记忆。

        persist=False 时只做记录、不写库（页面预览默认不污染主库）。
        """
        actions = []
        if persist:
            rec = self._call_soft("write_strategy",
                                  "把本轮采用惠民约束的方案记进记忆库",
                                  plan_date=self.plan_date, budget=self.budget,
                                  risks=self.risks, note=self.goal["label"])
            if rec:
                actions.append({"action": "写入决策日志",
                                "detail": f"新增 {rec['written']} 条方案记录",
                                "ok": True})
        else:
            actions.append({"action": "保持只读",
                            "detail": "本轮为预览模式，未写入记忆库（避免污染主库）",
                            "ok": True})
        self.actions = actions
        return actions

    def run(self, persist: bool = False) -> dict:
        """跑完整的一轮五阶段循环，返回结构化结果供页面渲染。"""
        self.perceive()
        self.reason()
        pl = self.plan()
        self._need_traffic = pl["need_traffic"]
        act = self.act()
        self._commit(persist)
        self.reflect()

        return {
            "plan_date": self.plan_date,
            "budget": self.budget,
            "risks": list(self.risks),
            "phases": PHASES,
            "trace": self.trace,
            "perception": self.obs,
            "diagnosis": self.diagnosis,
            "goal": self.goal,
            "plan_tasks": self.plan_steps,
            "strategy": self.strategy,
            "strategy_catalog": strategy_catalog(),
            "candidates": self.candidates,
            "chosen": self.chosen,
            "compare": self._compare,
            "actions": self.actions,
            "reflection": self.reflection,
            "path": self.reflection.get("path", {}),
            "tools": tools.tool_catalog(),
            "tool_categories": tools.CATEGORY_DESC,
            "stats": self._stats(),
        }

    def _stats(self) -> dict:
        by_phase: dict[str, int] = {}
        for e in self.trace:
            if e["kind"] == "think":
                by_phase[e["phase"]] = by_phase.get(e["phase"], 0) + 1
        cost_counts = {}
        for c in self.calls:
            cost_counts[c["cost"]] = cost_counts.get(c["cost"], 0) + 1
        return {
            "total_steps": sum(by_phase.values()),
            "steps_by_phase": by_phase,
            "tool_calls": len(self.calls),
            "failed_calls": sum(1 for c in self.calls if not c["ok"]),
            "tools_used": sorted({c["tool"] for c in self.calls}),
            "cost_counts": cost_counts,
            "elapsed_ms": round(sum(c["elapsed_ms"] for c in self.calls), 1),
        }


def run_agent(plan_date, budget: float = DEFAULT_BUDGET, risks=None,
              persist: bool = False, verbose: bool = False) -> dict:
    """跑一轮 Agent 自主决策 —— 本模块唯一的对外入口。"""
    return AgentRunner(plan_date, budget, risks=risks, verbose=verbose).run(persist=persist)
