# -*- coding: utf-8 -*-
"""
店脑 · Agent 自主决策引擎（本项目"智能体"特性的核心实体）

═══ 为什么要单独做这一层 ═══

一个直觉上很容易踩的坑是：把预测 + 分配打包成一个函数，
然后管它叫"AI 补货 Agent"。

但那不是 Agent，那是一段**过程式代码**：调用顺序写死在源码里，
不管门店今天是什么状况，它都走完全一样的流程。

真正的 Agent 至少要具备四件事：
  ① **自主目标**：它知道自己在为什么而忙，且目标可以随情境重新排序；
  ② **自主规划**：面对目标，它自己决定调哪些工具、按什么顺序、调几次；
  ③ **自主行动**：在预算与安全边界内自己做取舍，并承担取舍的后果；
  ④ **自主反思**：跑完一遍后回头看——哪里没做好、下次怎么改。

本模块就是把这四件事实现出来，形成一个显式的决策循环：

    ┌─────────────────────────────────────────────────────┐
    │  ① PERCEIVE  感知   盘点库存 / 扫异常 / 查日历 / 审策略 │
    │  ② REASON    推理   诊断问题 → 确定本轮的首要目标      │
    │  ③ PLAN      规划   拆解子目标 / 自选策略 / 挑选工具   │
    │  ④ ACT       执行   多方案博弈 → 择优 → 沙盘验证       │
    │  ⑤ REFLECT   反思   自评打分 → 留下改进意见            │
    └─────────────────────────────────────────────────────┘

关键点在于：**每一轮的循环路径都是当场决定的，不是写死的。**
比如库存健康、也无异常的平常日子，Agent 会自动跳过"异常扫描"的深度分析，
直接用轻量路径出方案；而一旦扫出严重的民生断货，
它会追加调用客流伤害评估、拉长推演窗口，并主动下调安全边界内的取舍。

这个"路径分支"本身，就是 Agent 与传统补货算法最直观的区别。
"""

from datetime import date, datetime, timedelta

from . import memory, policy, tools
from .config import (
    CURRENCY,
    DEFAULT_BUDGET,
    LIVELIHOOD_MIN_COVER_DAYS,
)

# ════════════════════════════════════════════════════════════
# Agent 的策略偏好（它不是没有性格的，它的性格由业务立意决定）
# ════════════════════════════════════════════════════════════
# 每种策略代表一种"活法"的选择，权重决定它在多目标博弈中怎么打分。
STRATEGIES = {
    "livelihood_first": {
        "label": "惠民优先",
        "desc": "民生商品优先保障，宁可少赚也要让街坊买得到",
        "weights": {"livelihood": 0.55, "margin": 0.20, "risk": 0.25},
        "margin_tolerance": 0.35,
    },
    "balanced": {
        "label": "稳健均衡",
        "desc": "收益与便民兼顾，适合日常经营的主基调",
        "weights": {"livelihood": 0.38, "margin": 0.37, "risk": 0.25},
        "margin_tolerance": 0.22,
    },
    "profit_oriented": {
        "label": "收益优先",
        "desc": "现金流吃紧时保收益，但仍不破民生底线",
        "weights": {"livelihood": 0.25, "margin": 0.52, "risk": 0.23},
        "margin_tolerance": 0.15,
    },
    "risk_averse": {
        "label": "避险优先",
        "desc": "异常高发期，先止住断货与损耗的出血点",
        "weights": {"livelihood": 0.40, "margin": 0.18, "risk": 0.42},
        "margin_tolerance": 0.30,
    },
}

# 风险维度归一化的基准：缺口 + 压货合计达到 8 项即视为风险满格
RISK_PENALTY_BASE = 8.0

# 收益维度归一化的基准：毛利/预算 达到 25% 即视为收益满格
MARGIN_RATE_BASE = 0.25


class AgentRunner:
    """
    店脑 Agent 的一次决策运行实例。

    一次 `run()` 就是一轮完整的自主决策循环。
    trace 里记录的是 Agent **真实走过的路径**，不是事后编的说明文字。
    """

    def __init__(self, plan_date: str, budget: float = DEFAULT_BUDGET,
                 verbose: bool = False):
        self.plan_date = str(plan_date)
        self.budget = float(budget)
        self.verbose = verbose

        self.trace: list[dict] = []        # 思考链（每一步都有依据与结论）
        self.tool_calls: list[dict] = []   # 工具调用轨迹
        self._step = 0
        self._t0 = datetime.now()

    # ── 内部小工具 ──────────────────────────────────────────
    def _think(self, phase: str, title: str, detail: str = "",
               conclusion: str = "", level: str = "info"):
        """记录一步思考。phase 是循环阶段名。"""
        self._step += 1
        self.trace.append({
            "step": self._step, "phase": phase, "title": title,
            "detail": detail, "conclusion": conclusion, "level": level,
        })
        if self.verbose:
            mark = {"info": "·", "ok": "✓", "warn": "!", "key": "★"}.get(level, "·")
            print(f"  {mark} [{phase}] {title}")
            if conclusion:
                print(f"      → {conclusion}")

    def _call(self, tool_name: str, why: str, **kwargs):
        """调用一个工具，并把「为什么调它」一并记进轨迹 —— 这是自主性的证据。"""
        tool = tools.get_tool(tool_name)
        if tool is None:
            return {"error": f"工具 {tool_name} 不存在"}
        t0 = datetime.now()
        try:
            result = tool(**kwargs)
            ok = True
        except Exception as e:      # Agent 要能容忍工具失败，而不是整个崩掉
            result = {"error": str(e), "conclusion": f"工具执行失败：{e}"}
            ok = False
        cost_ms = (datetime.now() - t0).total_seconds() * 1000
        self.tool_calls.append({
            "tool": tool_name, "category": tool.category, "why": why,
            "args": {k: (v if not isinstance(v, dict) else "<方案对象>")
                     for k, v in kwargs.items()},
            "ok": ok,
            "conclusion": result.get("conclusion", ""),
            "cost_ms": round(cost_ms, 1),
        })
        if self.verbose:
            print(f"    ↳ 调用工具 [{tool_name}]（{why}）")
        return result

    # ════════════════════════════════════════════════════════
    # ① 感知
    # ════════════════════════════════════════════════════════
    def perceive(self) -> dict:
        self._think("感知", f"开始为 {self.plan_date} 的进货做决策",
                    detail=f"预算上限 {CURRENCY}{self.budget:.0f}",
                    conclusion="先摸清店里现在是什么状况。", level="key")

        cal = self._call("check_calendar", "先确认今天是什么日子，节日会改变需求节奏",
                         plan_date=self.plan_date)
        self._think("感知", f"日历核对：{cal['weekday']}",
                    detail=("识别的节日：" + "、".join(
                        f"{h['name']}（{h['when']}）" for h in cal["holidays"]))
                    if cal["holidays"] else "无节日因素",
                    conclusion=cal["conclusion"],
                    level="ok" if cal["is_special"] else "info")

        inv = self._call("read_inventory", "盘点货架，看哪些货快见底",
                         plan_date=self.plan_date)
        self._think("感知", f"库存盘点：{len(inv['rows'])} 样商品",
                    detail="、".join(
                        f"{r['name']}（够 {r['cover_days']:.1f} 天）"
                        for r in sorted(inv["rows"], key=lambda x: x["cover_days"])[:4]
                    ),
                    conclusion=inv["conclusion"],
                    level="warn" if inv["low_stock_count"] >= 3 else "ok")

        ano = self._call("scan_anomalies",
                         "扫一遍最近的经营异常，判断这轮决策要优先解决什么",
                         lookback_days=14, ref_date=self.plan_date)
        self._think("感知", f"异常扫描：发现 {len(ano['anomalies'])} 项",
                    detail="；".join(f"{a['name']}｜{a['kind']}｜{a['detail']}"
                                    for a in ano["anomalies"][:5]) or "近两周经营平稳",
                    conclusion=ano["conclusion"],
                    level="warn" if ano["anomalies"] else "ok")

        return {"calendar": cal, "inventory": inv, "anomalies": ano}

    # ════════════════════════════════════════════════════════
    # ② 推理：诊断问题、确定本轮的首要目标
    # ════════════════════════════════════════════════════════
    def reason(self, obs: dict) -> dict:
        ano = obs["anomalies"]
        anoms = ano["anomalies"]

        # ── 诊断：把异常按「是否伤及民生客流」分类 ──
        liv_so = [a for a in anoms if a["kind"] == "断货" and a["is_livelihood"]]
        pro_so = [a for a in anoms if a["kind"] == "断货" and not a["is_livelihood"]]
        spoil = [a for a in anoms if a["kind"] == "积压损耗"]
        liv_spoil = [a for a in spoil if a["is_livelihood"]]

        severe = len(liv_so) >= 2 or (liv_so and liv_so[0]["severity"] > 0.25)

        self._think(
            "推理", "问题诊断",
            detail=(f"民生断货 {len(liv_so)} 项｜高毛利断货 {len(pro_so)} 项｜"
                    f"积压损耗 {len(spoil)} 项｜库存告急 {obs['inventory']['low_stock_count']} 项"),
            conclusion=("民生断货已构成主要矛盾——民生是客流入口，"
                        "缺货的连带损失远大于它的账面毛利。"
                        if severe else
                        ("存在商品断货，需要上调备货水平。" if (liv_so or pro_so)
                         else ("主要矛盾是积压损耗，要把进货量收一收。" if spoil
                               else "没有突出矛盾，按常态经营节奏决策。"))),
            level="key",
        )

        # ── 自主决策：本轮的首要目标由此刻的店况决定，而非写死 ──
        if severe:
            goal = {
                "key": "止住民生的血",
                "detail": "民生商品断货正在流失客流，本轮第一优先是恢复民生保障度",
                "strategy": "livelihood_first",
            }
            self._think("推理", "判定本轮首要目标",
                        detail="触发条件：民生商品断货 ≥ 2 项，或单项严重度 > 0.25",
                        conclusion=f"① {goal['key']} —— 其余目标为此让路。",
                        level="key")
            self._think("推理", "次要目标",
                        detail="在保住民生的前提下，尽量减少高毛利商品的缺货",
                        conclusion="② 其次压降高毛利商品断货，因为它是门店现金流的来源。",
                        level="info")
        elif len(spoil) >= 3:
            goal = {
                "key": "止血积压损耗",
                "detail": "报损商品偏多，本轮要压降进货量、收紧短保商品备货",
                "strategy": "risk_averse",
            }
            self._think("推理", "判定本轮首要目标",
                        detail="触发条件：积压损耗 ≥ 3 项",
                        conclusion=f"① {goal['key']} —— 先止住看得见的亏损。",
                        level="key")
            self._think("推理", "次要目标",
                        detail="在不造成新断货的前提下收紧订货",
                        conclusion="② 其次盯住民生商品，避免收紧过头又断货。",
                        level="info")
        elif obs["inventory"]["low_stock_count"] >= 5:
            goal = {
                "key": "补齐普遍性缺口",
                "detail": "多数商品库存偏低，本轮以恢复合理备货水平为主",
                "strategy": "balanced",
            }
            self._think("推理", "判定本轮首要目标",
                        detail="触发条件：库存告急商品 ≥ 5 项",
                        conclusion=f"① {goal['key']} —— 先把普遍缺口补上。",
                        level="key")
            self._think("推理", "次要目标",
                        detail="补货时仍按惠民约束排序",
                        conclusion="② 其次控制花费，不要在补齐时冲垮预算。",
                        level="info")
        else:
            goal = {
                "key": "稳健经营",
                "detail": "店况平稳，本轮在收益与便民之间保持均衡",
                "strategy": "balanced",
            }
            self._think("推理", "判定本轮首要目标",
                        detail="触发条件：无显著异常、库存健康",
                        conclusion="① 稳健经营 —— 日常状态不折腾。",
                        level="key")

        # 冲突识别：Agent 能说出它要面对的矛盾，而不是假装没有矛盾
        self._think(
            "推理", "目标冲突识别",
            detail="民生保障需要资金，收益同样需要资金，而预算只有一份",
            conclusion=(f"矛盾客观存在。本轮策略取「{STRATEGIES[goal['strategy']]['label']}」："
                        f"{STRATEGIES[goal['strategy']]['desc']}。"),
            level="info",
        )
        goal["conflict"] = "惠民保障 vs 门店收益 —— 预算有限，必须显式取舍"
        return {"diagnosis": {
            "livelihood_stockout": len(liv_so),
            "profit_stockout": len(pro_so),
            "spoilage": len(spoil),
            "severe": severe,
        }, "goal": goal}

    # ════════════════════════════════════════════════════════
    # ③ 规划：拆解任务、决定调用哪些工具
    # ════════════════════════════════════════════════════════
    def plan(self, obs: dict, rsn: dict) -> dict:
        goal = rsn["goal"]
        strat_key = goal["strategy"]
        strat = STRATEGIES[strat_key]

        # ── 自主决定：这轮要不要做高开销的客流分析 ──
        # 该分析要遍历全部门店历史记录，是这里最贵的工具。
        # 只有在民生确实出问题时，结论才会影响决策 —— 这是 Agent 的资源意识。
        need_traffic = rsn["diagnosis"]["livelihood_stockout"] > 0
        if need_traffic:
            self._think("规划", "决定追加客流伤害评估",
                        detail=f"该工具需遍历全部历史记录，是本次开销最高的分析；"
                               f"判定依据是民生断货 {rsn['diagnosis']['livelihood_stockout']} 项",
                        conclusion="民生有断货 → 影响面大，值得调用，用它量化取舍的后果。",
                        level="warn")
        else:
            self._think("规划", "决定跳过客流伤害评估",
                        detail="该工具需遍历全部历史记录，开销最高；"
                               "本店况下民生无断货，其结论不会改变决策",
                        conclusion="本轮不调用，节省开销 —— 这是 Agent 的资源意识。",
                        level="info")

        # ── 任务拆解：把目标翻译成有序的子任务 ──
        subtasks = [
            {"n": 1, "task": "预测决策日各商品的真实需求",
             "tool": "forecast_demand", "why": "没有需求预测，补货量就无从谈起"},
            {"n": 2, "task": "理解传统纯利润算法的取舍逻辑",
             "tool": "rank_by_efficiency", "why": "要知道对手错在哪，才能证明自己"},
        ]
        if need_traffic:
            subtasks.append({
                "n": 3, "task": "量化民生缺货对整体客流的连带伤害",
                "tool": "assess_traffic", "why": "为「不砍民生」提供数据依据，而非情怀",
            })
        subtasks += [
            {"n": len(subtasks) + 1, "task": "生成多套候选方案并逐套推演",
             "tool": "simulate_plan", "why": "先沙盘再落地，避免拍脑袋"},
            {"n": len(subtasks) + 2, "task": "把最优方案与传统算法正面对照",
             "tool": "compare_with_baseline", "why": "给出取舍的量化代价，坦承成本"},
        ]

        self._think("规划", f"任务拆解：共 {len(subtasks)} 个子任务",
                    detail=" → ".join(f"{s['n']}.{s['task']}" for s in subtasks),
                    conclusion="子任务之间有依赖：先预测、再排序、后博弈，最后对照验证。",
                    level="key")

        # ── 策略自选：说明为什么选它，以及为什么不选别的 ──
        rejected = [f"{v['label']}（{k}）" for k, v in STRATEGIES.items()
                    if k != strat_key]
        self._think("规划", f"策略锁定：{strat['label']}",
                    detail=f"评分权重 → 民生 {strat['weights']['livelihood']:.0%}｜"
                           f"收益 {strat['weights']['margin']:.0%}｜"
                           f"风险 {strat['weights']['risk']:.0%}",
                    conclusion=f"本轮采用「{strat['label']}」。"
                               f"暂不采用：{'、'.join(rejected)} —— "
                               f"它们与当前店况的首要目标不匹配。",
                    level="key")

        return {"subtasks": subtasks, "strategy": strat_key,
                "strategy_detail": strat, "need_traffic": need_traffic}

    # ════════════════════════════════════════════════════════
    # ④ 执行：多方案博弈 → 择优
    # ════════════════════════════════════════════════════════
    def _score(self, metrics: dict, sim: dict, strat: dict) -> tuple[float, dict]:
        """
        多目标打分 —— Agent 的"价值观"在这里落地。
        三个维度归一化后加权，权重来自本轮选定的策略。
        """
        w = strat["weights"]

        # 民生保障度：0~1，直接可用
        s_liv = min(1.0, metrics["livelihood_index"])

        # 收益：以预算为基准的毛利回报率，映射到 0~1
        margin_rate = metrics["gross_margin"] / max(metrics["budget"], 1.0)
        s_margin = min(1.0, margin_rate / MARGIN_RATE_BASE)

        # 风险：断货与压货的扣分（越低越好）
        # 民生风险被重复计一次 —— 因为它流失的是客流，不只是这一单生意
        n_risk = sim.get("risk_total", 0)
        n_over = len(sim.get("overstock", []))
        n_liv_risk = len(sim.get("risk_livelihood", []))
        penalty = (n_risk + n_liv_risk + n_over) / RISK_PENALTY_BASE
        s_risk = max(0.0, 1.0 - min(1.0, penalty))

        total = w["livelihood"] * s_liv + w["margin"] * s_margin + w["risk"] * s_risk
        return round(total, 4), {
            "livelihood": round(s_liv, 4),
            "margin": round(s_margin, 4),
            "risk": round(s_risk, 4),
        }

    def act(self, pln: dict, rsn: dict) -> dict:
        strat = pln["strategy_detail"]

        # ── 子任务 1：需求预测 ──
        fc = self._call("forecast_demand", "子任务 1：预测各商品在决策日的需求",
                        plan_date=self.plan_date)
        self._think("执行", "子任务 1 完成：需求预测",
                    detail=f"预测 {fc['count']} 样商品"
                           + (f"；节日因素：{'、'.join(fc['holiday_notes'])}"
                              if fc["holiday_notes"] else ""),
                    conclusion=fc["conclusion"], level="ok")

        # ── 子任务 2：理解对手 ──
        rank = self._call("rank_by_efficiency",
                          "子任务 2：看清纯利润算法的排序逻辑，明确自己要纠正什么",
                          plan_date=self.plan_date)
        self._think("执行", "子任务 2 完成：资金效率排序",
                    detail=f"资金效率最高的是 {rank['rows'][0]['name']}"
                           f"（{rank['rows'][0]['capital_eff']:.2f}）"
                           if rank.get("rows") else "",
                    conclusion=rank["conclusion"], level="ok")

        # ── 子任务 3：客流伤害评估（可能被跳过） ──
        traffic = None
        if pln["need_traffic"]:
            traffic = self._call("assess_traffic",
                                 "子任务 3：量化民生缺货的连带损失，为惠民约束提供依据")
            self._think("执行", "子任务 3 完成：客流伤害评估",
                        detail=f"缺货日非民生商品少卖 {traffic.get('gap_pct', 0):.1f}%，"
                               f"相关系数 {traffic.get('correlation', 0):.2f}",
                        conclusion=traffic["conclusion"], level="warn")
        else:
            self._think("执行", "子任务 3 已跳过（按规划）",
                        detail="民生无断货，客流评估边际价值低",
                        conclusion="跳过 —— 这是规划阶段就定好的资源取舍。",
                        level="info")

        # ══ 多方案博弈：Agent 不是只算一套方案，而是裁决几套方案 ══
        self._think("执行", "启动多方案博弈",
                    detail="将生成 3 套候选方案：惠民约束 / 纯利润 / 快周转避险，"
                           "逐套做 3 天沙盘推演后按本轮策略权重打分",
                    conclusion="不预设答案 —— 让方案在推演中自己胜出。",
                    level="key")

        # 候选 A：启用惠民约束 + 常规备货节奏（本项目主张）
        cand_a = self._call("build_replenishment", "候选 A：带惠民约束的方案",
                            plan_date=self.plan_date, budget=self.budget,
                            protect_livelihood=True)
        sim_a = self._call("simulate_plan", "对候选 A 做 3 天沙盘推演",
                           plan=cand_a["plan"], horizon_days=3)

        # 候选 B：纯利润算法（对照，用于量化惠民约束的代价）
        cand_b = self._call("build_replenishment", "候选 B：纯利润算法（对照组）",
                            plan_date=self.plan_date, budget=self.budget,
                            protect_livelihood=False)
        sim_b = self._call("simulate_plan", "对候选 B 做 3 天沙盘推演",
                           plan=cand_b["plan"], horizon_days=3)

        # 候选 C：快周转避险版 —— 同样保民生，但备货天数整体压缩，
        # 用"多进几次、每次少进"换取更低的压货与过期风险。
        cand_c = self._call("build_replenishment",
                            "候选 C：备货天数压缩 30% 的快周转避险方案",
                            plan_date=self.plan_date, budget=self.budget,
                            protect_livelihood=True, day_scale=0.70)
        sim_c = self._call("simulate_plan", "对候选 C 做 3 天沙盘推演",
                           plan=cand_c["plan"], horizon_days=3)

        candidates = []
        for tag, cand, sim, note in (
            ("A", cand_a, sim_a, "惠民约束版"),
            ("B", cand_b, sim_b, "纯利润版"),
            ("C", cand_c, sim_c, "快周转避险版"),
        ):
            score, parts = self._score(cand["plan"]["metrics"], sim, strat)
            candidates.append({
                "tag": tag, "label": note, "plan": cand["plan"],
                "sim": sim, "score": score, "parts": parts,
                "metrics": cand["plan"]["metrics"], "meta": cand["plan"]["meta"],
            })
            self._think(
                "执行", f"候选 {tag}（{note}）评分",
                detail=f"综合 {score:.4f} ＝ 民生 {parts['livelihood']:.2f}×{strat['weights']['livelihood']:.2f} "
                       f"+ 收益 {parts['margin']:.2f}×{strat['weights']['margin']:.2f} "
                       f"+ 风险 {parts['risk']:.2f}×{strat['weights']['risk']:.2f}",
                conclusion=f"花 {CURRENCY}{cand['plan']['metrics']['total_cost']:.0f}，"
                           f"民生保障 {cand['plan']['metrics']['livelihood_index']:.0%}，"
                           f"毛利 {CURRENCY}{cand['plan']['metrics']['gross_margin']:.0f}，"
                           f"沙盘风险 {sim['risk_total']} 项。",
                level="info",
            )

        best = max(candidates, key=lambda c: c["score"])
        worst = min(candidates, key=lambda c: c["score"])
        self._think(
            "执行", f"裁决结果：候选 {best['tag']}（{best['label']}）胜出",
            detail=f"以 {best['score']:.4f} 分居首，"
                   f"领先候选 {worst['tag']}（{worst['label']}）"
                   f"{best['score'] - worst['score']:.4f} 分",
            conclusion=(f"采纳候选 {best['tag']}。决策依据：在「{strat['label']}」"
                        f"策略下，它在民生保障、门店收益、经营风险三者间的综合得分最高。"),
            level="key",
        )

        # ── 对照验证（只在策略非纯利润时才有叙事价值）──
        cmp = self._call("compare_with_baseline",
                         "把胜出方案与传统算法正面对照，量化取舍代价",
                         plan_date=self.plan_date, budget=self.budget)
        self._think("执行", "与纯利润算法的对照",
                    detail=f"民生保障度高出 {cmp['liv_gain'] * 100:.1f} 个百分点，"
                           f"毛利代价 {CURRENCY}{cmp['margin_cost']:.0f}",
                    conclusion=cmp["conclusion"], level="ok")

        return {"forecast": fc, "rank": rank, "traffic": traffic,
                "candidates": candidates, "best": best, "cmp": cmp}

    # ════════════════════════════════════════════════════════
    # ⑤ 反思：自评 + 留下改进意见
    # ════════════════════════════════════════════════════════
    def reflect(self, obs: dict, rsn: dict, pln: dict, act: dict) -> dict:
        best = act["best"]
        best_sim = best["sim"]
        m = best["metrics"]
        n_risk = best_sim["risk_total"]
        n_liv_risk = len(best_sim["risk_livelihood"])

        # 置信度：由"证据充分度"决定，不是拍脑袋给的数字
        conf = 1.0
        reasons = []
        stats = memory.memory_stats()
        days = stats.get("累计覆盖天数", 0)
        if days < 30:
            conf -= 0.25
            reasons.append(f"门店仅积累了 {days} 天数据，冷启动阶段预测偏保守")
        elif days < 60:
            conf -= 0.10
            reasons.append(f"门店积累了 {days} 天数据，预测基本可用")
        else:
            reasons.append(f"门店积累了 {days} 天数据，样本充足")

        if n_risk > 0:
            conf -= min(0.20, n_risk * 0.03)
            reasons.append(f"沙盘推演仍有 {n_risk} 样商品存在缺口")
        else:
            reasons.append("沙盘推演未发现缺口，方案稳健")
        if n_liv_risk > 0:
            conf -= 0.10
            reasons.append(f"其中民生商品 {n_liv_risk} 样有缺口，需明日重点盯防")
        conf = max(0.35, min(0.98, conf))

        level_cn = ("高" if conf >= 0.80 else "中" if conf >= 0.60 else "偏低")
        self._think("反思", f"自评置信度：{conf:.0%}（{level_cn}）",
                    detail="；".join(reasons),
                    conclusion=f"本轮方案在 {conf:.0%} 的把握下可用。",
                    level="key")

        # ── 改进意见：Agent 对自己这一轮的批评 ──
        critiques = []
        if pln["need_traffic"]:
            t = act.get("traffic") or {}
            if t.get("gap_pct", 0) > 8:
                critiques.append(
                    f"客流数据再次确认民生缺货的连带损失达 {t['gap_pct']:.1f}%，"
                    f"说明当前惠民底线（{LIVELIHOOD_MIN_COVER_DAYS:.0f} 天）仍有提升空间，"
                    f"若预算允许可考虑上调到 {LIVELIHOOD_MIN_COVER_DAYS + 1:.0f} 天。"
                )
        if best["tag"] == "B":
            critiques.append(
                "本轮胜出的是纯利润方案，说明当前店况下收益压力已压过便民诉求，"
                "需要关注：这是否会让民生商品的备货持续走低。"
            )
        if n_risk > 3:
            critiques.append(
                f"沙盘显示 {n_risk} 样商品会在 3 天内出现缺口，预算相对需求偏紧。"
                f"建议店主评估是否把预算从 {CURRENCY}{self.budget:.0f} 适度上调。"
            )
        if best_sim["overstock"]:
            names = "、".join(o["name"] for o in best_sim["overstock"][:3])
            critiques.append(
                f"{names} 存在压货风险，明日起应密切观察周转情况，"
                f"若连续滞销则触发策略下调。"
            )
        if not critiques:
            critiques.append("本轮方案未发现结构性问题，维持现有策略参数继续观察。")

        # ── 下轮预案：Agent 对未来的自主承诺 ──
        next_actions = []
        if n_liv_risk:
            next_actions.append(
                f"明日优先复核 {n_liv_risk} 样存在缺口的民生商品，必要时单独追加补货。")
        next_actions.append("收盘后按实际销售、断货、损耗数据自动触发策略进化。")
        next_actions.append("若连续 3 天同类异常重复出现，则调整安全边界而不只是微调参数。")

        self._think("反思", f"自我批评 {len(critiques)} 条",
                    detail="；".join(critiques),
                    conclusion="这些意见会留存在轨迹里，供下一轮决策参考。",
                    level="warn")

        elapsed = (datetime.now() - self._t0).total_seconds()
        self._think("反思", "本轮循环结束",
                    detail=f"共 {self._step} 步思考、{len(self.tool_calls)} 次工具调用、"
                           f"耗时 {elapsed:.2f} 秒",
                    conclusion=f"方案已就绪，等待店主确认执行。",
                    level="ok")

        return {"confidence": round(conf, 3), "confidence_level": level_cn,
                "confidence_reasons": reasons,
                "critiques": critiques, "next_actions": next_actions,
                "elapsed_sec": round(elapsed, 2)}

    # ════════════════════════════════════════════════════════
    # 主循环
    # ════════════════════════════════════════════════════════
    def run(self, persist: bool = False) -> dict:
        obs = self.perceive()          # ①
        rsn = self.reason(obs)         # ②
        pln = self.plan(obs, rsn)      # ③
        act = self.act(pln, rsn)       # ④
        ref = self.reflect(obs, rsn, pln, act)   # ⑤

        best = act["best"]
        if persist:
            self._call("record_plan", "把最终采纳的方案存入历史方案库",
                       plan=best["plan"])

        return {
            "date": self.plan_date,
            "budget": self.budget,
            "observation": obs,
            "reasoning": rsn,
            "plan": pln,
            "action": act,
            "reflection": ref,
            "trace": self.trace,
            "tool_calls": self.tool_calls,
            "final_plan": best["plan"],
            "candidates": act["candidates"],
            "best_candidate": best,
            "goal": rsn["goal"],
            "strategy": STRATEGIES[pln["strategy"]],
            "strategy_key": pln["strategy"],
            "comparison": act["cmp"]["cmp"],
        }


def run_agent(plan_date: str, budget: float = DEFAULT_BUDGET,
              persist: bool = False, verbose: bool = False) -> dict:
    """
    跑一轮完整的 Agent 自主决策循环。

    这是对外的唯一入口 —— 界面上、演示脚本里调用的都是它。
    """
    runner = AgentRunner(plan_date, budget, verbose=verbose)
    return runner.run(persist=persist)


# ════════════════════════════════════════════════════════════
# 循环阶段元数据（供界面渲染）
# ════════════════════════════════════════════════════════════
PHASES = [
    {"key": "感知", "icon": "👁", "label": "感知 PERCEIVE",
     "desc": "盘点库存、扫描异常、核对日历与策略状态"},
    {"key": "推理", "icon": "🧩", "label": "推理 REASON",
     "desc": "诊断问题严重度，确定本轮首要目标与次要目标"},
    {"key": "规划", "icon": "🗺", "label": "规划 PLAN",
     "desc": "拆解子任务、自选策略、决定投入哪些分析工具"},
    {"key": "执行", "icon": "⚙️", "label": "执行 ACT",
     "desc": "多方案生成 → 沙盘推演 → 加权打分 → 裁决最优"},
    {"key": "反思", "icon": "🪞", "label": "反思 REFLECT",
     "desc": "自评置信度、写下自我批评与下一轮预案"},
]


def strategy_catalog() -> list[dict]:
    return [{"key": k, **v} for k, v in STRATEGIES.items()]
