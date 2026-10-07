# -*- coding: utf-8 -*-
"""
演示门店 · 模拟经营历史 初始化脚本（seed / demo bootstrap）
================================================================================
【这是什么】
    为**比赛演示环境**补一段「演示门店·模拟经营历史」的经营反馈记录，
    让「它学会了什么」「店里的老账本」两个页面能展示小满的长期学习能力。

【诚信声明 —— 请勿删除本段】
    1. 本脚本产出的经营反馈属于**模拟经营历史**（demo/simulated），
       来自项目自带的 180 天仿真数据集，**不是**现实商户采集的数据。
    2. 页面会显示「演示门店 · 模拟经营历史」标识，评委可明确区分。
    3. experience / evolution 记录**全部由core/evolution.py 的现有业务逻辑
       自动生成**（derive_experiences → upsert_experience → _log_calibration），
       本脚本**不向 experiences /evolution_log 表直接写任何一行**。
    4. 本脚本**不修改**任何 Memory / Forecast / R³ / Policy 核心算法与阈值
       （STOCKOUT_TRIGGER / SPOILAGE_TRIGGER / MEMORY_BIAS_* 全部只读）。
    5. 输入的是**经营反馈**（销量/断货/损耗），与「今天生意怎么样」页面
       提交的字段完全一致，走的是同一条业务闭环。

【走的是哪条路（与 app.py 提交反馈完全一致）】
    历史经营结果
      → 构造 feedback 列表（sku / qty_sold / qty_stockout / qty_spoilage）
      → policy.build_plan(day) 复算当天的 forecast_qty / reorder_qty  ← plan_context
      → evolution.process_feedback(day, feedback, plan_context=...)
      → memory.add_feedback_log()   正常落库
      → derive_experiences()        按真实触发规则判定是否形成经验
      → upsert_experience()         经验入库
      → _log_calibration()          校准量变化才写evolution_log
      → 下一次 build_plan(use_memory=True) 读回经验 → memory_delta → 影响补货

【幂等性】
    经验去重键是 (day, sku)，且内容相同的重复提交会被 existing 分支跳过。
    evolution_log 只在「校准量真的变了」时写入。
    因此**重复执行本脚本不会重复制造经验**，只会稳定在同样数量。
    如需完全清空演示数据：用 --reset 参数（会删除本脚本自己写入的记录）。

【用法】
    python seed_demo_history.py            # 幂等地补齐演示历史
    python seed_demo_history.py --reset    # 先清空本脚本写入的记录再补
    python seed_demo_history.py --dry-run  # 只打印将要做什么，不写库
"""
from __future__ import annotations

import argparse
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from core import evolution, memory, policy, config  # noqa: E402

# ══════════════════════════════════════════════════════════════
# 演示门店 · 模拟经营历史（demo / simulated）
#
# 设计原则：
#   · 只挑 4 个代表性商品，覆盖 3 种可解释的经验类型，不给所有商品乱填
#   · 数值必须满足现有触发规则（STOCKOUT_TRIGGER / SPOILAGE_TRIGGER = 0.10）
#   · 每个场景都对应 day_events 里真实存在的经营日，让 scene 匹配有意义
# ══════════════════════════════════════════════════════════════
#
# 触发公式（来自 core/evolution.py，不做任何修改）：
#   断货： qty_stockout / (qty_sold + qty_stockout) > 0.10
#   损耗： qty_spoilage / (qty_sold + qty_spoilage) > 0.10
#   （断货与损耗同时出现时只按断货计，避免自我抵消 —— evolution.py 第116 行）
#
# 场景匹配（来自 core/policy.py memory_safety_calibration）：
#   经验按 event_type 聚合，当前决策的场景标签必须与经验 event_type 相同才被读回
#   正常日→ event_type='正常'；高温日 → event_type='高温'，以此类推

DEMO_TAG = "演示门店 · 模拟经营历史"

# ── 反馈设计（4 个商品 / 4 种可解释场景）──────────────────────────
# 数值设计依据（重要，答辩必讲）：
#   Memory 学的是**预测残差**，而不是「断货」这件事本身（policy.py 第 175-180 行）：
#     err = (实际潜在需求 − 原预测) / 原预测
#   所以要让「断货 → 提高备货」这条因果链符合直觉，必须让
#     实际潜在需求(卖出 + 断货) > 原预测日销
#   下面每条的数值都按这个原则反推；--dry-run 会先打印残差方向。
#   注意：残差为负时系统会判定「预测偏高」而降低备货 —— 这也是正确的
#   （第② 条牛奶就是这种情形：那天确实备多了）。
DEMO_FEEDBACK = [
    # ① 民生高频品「桶装水」在高温日断货，且卖得比预测多 → 残差为正 → 提高备货
    #    高温日桶装水预测日销 11.38；实际卖出 6 + 断货 8 = 14 → 残差 +23%
    {
        "day": "2026-07-18",          # day_events 里真实存在的高温日
        "items": [
            {"sku": "P002", "qty_sold": 6.0, "qty_stockout": 8.0, "qty_spoilage": 0.0},
        ],
        "why": "高温日桶装水需求比预测更旺，货架备货不足，当天有顾客买不到",
    },
    # ② 生鲜「牛奶」出现积压损耗（保质期仅 7 天，短保品最易损耗）
    #    高温日牛奶预测日销 15.11；当天多备了，只卖出 10 又报损 3 → 残差为负
    #    → 系统降低备货（学的是「那天备多了」，不是「报损」这件事）
    {
        "day": "2026-07-17",          # 高温日
        "items": [
            {"sku": "P006", "qty_sold": 10.0, "qty_stockout": 0.0, "qty_spoilage": 3.0},
        ],
        "why": "高温日多备的牛奶没卖完，临近保质期产生损耗，说明那天备货偏多",
    },
    # ③ 民生刚需「鸡蛋」在暴雨日实际销量高于预测但没断货
    #    —— 用来证明系统不会把「卖得好」误判成异常（不形成经验）
    {
        "day": "2026-07-01",          # 暴雨日
        "items": [
            {"sku": "P008", "qty_sold": 16.0, "qty_stockout": 0.0, "qty_spoilage": 0.0},
        ],
        "why": "暴雨日顾客囤货，鸡蛋实际销量高于预测（属正常波动，不应形成经验）",
    },
    # ④ 调味「食用油5L」在普通日断货，实际需求远超预测 → 残差为正 → 提高备货
    #    普通日食用油预测日销 3.95；实际卖出 2 + 断货 4 = 6 → 残差 +52%
    {
        "day": "2026-07-05",          # 普通日
        "items": [
            {"sku": "P010", "qty_sold": 2.0, "qty_stockout": 4.0, "qty_spoilage": 0.0},
        ],
        "why": "普通日食用油销量不高但仍有顾客买不到，说明日常备货基线偏低",
    },
]


def _risk_for(day: str) -> list:
    """复算某天的生效风险事件（与 app.py 的 _day_risks 同一口径）。"""
    from core import events as _ev
    ev = memory.get_day_event(day)
    label = ev["event"] if ev else "正常"
    if label == "正常":
        return []
    return [_ev.LABEL_TO_EVENT_KEY.get(label)] and [_ev.LABEL_TO_EVENT_KEY[label]] or []


def _ratio(fb: dict) -> tuple:
    """按 evolution.py 的真实公式算出两个比例，便于打印自检。"""
    sold = float(fb.get("qty_sold", 0) or 0)
    so = float(fb.get("qty_stockout", 0) or 0)
    sp = float(fb.get("qty_spoilage", 0) or 0)
    pot = sold + so
    sup = sold + sp
    return ((so / pot) if pot > 0 else 0.0,
            (sp / sup) if sup > 0 else 0.0)


def main() -> int:
    ap = argparse.ArgumentParser(description="演示门店 · 模拟经营历史 初始化")
    ap.add_argument("--dry-run", action="store_true", help="只打印将做什么，不写库")
    ap.add_argument("--reset", action="store_true",
                    help="先删除本脚本会写入的 (day, sku) 记录，再重新生成")
    args = ap.parse_args()

    print("=" * 84)
    print("演示门店 · 模拟经营历史 初始化（seed / demo bootstrap）")
    print("=" * 84)
    print("  性质：模拟经营数据（demo / simulated），非现实商户采集")
    print("  页面标识：%s" % DEMO_TAG)
    print("  触发阈值（只读自core/config.py）：STOCKOUT_TRIGGER=%.2fSPOILAGE_TRIGGER=%.2f"
          % (config.STOCKOUT_TRIGGER, config.SPOILAGE_TRIGGER))
    print("  校准上限（只读）：MEMORY_SAFETY_MAX_DELTA=%.2f" % config.MEMORY_SAFETY_MAX_DELTA)
    print()

    prods = {p["sku"]: p for p in memory.get_products()}

    # ── 预检：商品与日期是否存在，比例是否真的能触发 ──
    print("-" * 84)
    print("预检：按evolution.py / policy.py 的真实公式验算触发与残差方向")
    print("-" * 84)
    print("  %-6s %-10s %-11s %-7s %-8s %-8s %-9s %s"
          % ("SKU", "名称", "日期", "场景", "断货率", "损耗率", "预测残差", "预期效果"))
    ok = True
    for blk in DEMO_FEEDBACK:
        day = blk["day"]
        ev = memory.get_day_event(day)
        scene = ev["event"] if ev else "正常"
        risks = _risk_for(day)
        # 复算当天预测日销（与正式写入时完全一致）
        plan = policy.build_plan(day, config.DEFAULT_BUDGET, policy.MODE_DIANNAO,
                                 persist=False, risks=risks)
        pmap = {it["sku"]: it["daily_demand"] for it in plan["items"]}
        for it in blk["items"]:
            sku = it["sku"]
            if sku not in prods:
                print("  ✗ SKU 不存在：%s" % sku)
                ok = False
                continue
            so_r, sp_r = _ratio(it)
            if so_r > config.STOCKOUT_TRIGGER:
                expect = "断货经验"
            elif sp_r > config.SPOILAGE_TRIGGER:
                expect = "损耗经验"
            else:
                expect = "不形成经验"
            fq = float(pmap.get(sku) or 0.0)
            actual = float(it["qty_sold"]) + float(it["qty_stockout"])
            err = ((actual - fq) / fq * 100) if fq > 1e-9 else 0.0
            effect = "提高备货" if err > 0.5 else ("降低备货" if err < -0.5 else "基本不变")
            print("  %-6s %-10s %-11s %-7s %-8.1f%% %-8.1f%% %+8.1f%% %s / %s"
                  % (sku, prods[sku]["name"][:9], day, scene,
                     so_r * 100, sp_r * 100, err, expect, effect))
    print()
    if not ok:
        print("  预检失败，未写库。")
        return 2

    if args.dry_run:
        print("  --dry-run 模式：不写库，仅预检通过。")
        return 0

    # ── 可选：清空本脚本会写入的记录（保证 --reset 也能幂等）──────────
    if args.reset:
        print("-" * 84)
        print("--reset：清理本脚本目标记录")
        print("-" * 84)
        from core.memory import connect as _connect
        pairs = [(b["day"], i["sku"]) for b in DEMO_FEEDBACK for i in b["items"]]
        with _connect() as conn:
            for day, sku in pairs:
                n1 = conn.execute("DELETE FROM experiences WHERE day=? AND sku=?",
                                  (day, sku)).rowcount
                n2 = conn.execute("DELETE FROM evolution_log WHERE day=? AND sku=?",
                                  (day, sku)).rowcount
                print("  %s / %-6s  经验-%d 进化-%d" % (day, sku, n1, n2))
        print()

    # ── 正式写入：完全复用 app.py 提交反馈的同一条业务闭环 ────────────
    print("-" * 84)
    print("写入：走 evolution.process_feedback（与页面提交反馈完全同一入口）")
    print("-" * 84)
    total_exp = total_chg = 0
    for blk in DEMO_FEEDBACK:
        day = blk["day"]
        risks = _risk_for(day)
        # 关键：复算当天的 plan_context（含真实 forecast_qty），
        # 与 app.py do_feedback 的第 631-636 行完全一致
        plan = policy.build_plan(day, config.DEFAULT_BUDGET, policy.MODE_DIANNAO,
                                 persist=False, risks=risks)
        plan_context = {
            it["sku"]: {"forecast_qty": it["daily_demand"],
                        "reorder_qty": it["reorder_qty"]}
            for it in plan["items"]
        }
        feedback = [dict(i, is_promo=0, is_holiday=0) for i in blk["items"]]
        res = evolution.process_feedback(day, feedback, persist=True,
                                         plan_context=plan_context)
        s = res["summary"]
        exp_n = len(res.get("experiences") or [])
        chg_n = len(res.get("changes") or [])
        total_exp += exp_n
        total_chg += chg_n
        print("  %s（%s）  经验 +%d  策略调整 +%d  跳过 %d  更新 %d  撤销 %d"
              % (day, blk["why"][:20], exp_n, chg_n,
                 s.get("skipped", 0), s.get("updated", 0), s.get("removed", 0)))
        for e in (res.get("experiences") or []):
            nm = prods[e["sku"]]["name"]
            fq = float(e.get("forecast_qty") or 0)
            act = float(e.get("qty_sold") or 0) + float(e.get("qty_stockout") or 0)
            err = ((act - fq) / fq) if fq > 1e-9 else 0.0
            print("     · %-10s %s｜预测残差 %+.0f%%  「%s」"
                  % (nm, e["signal"], err * 100, e["lesson"]))
        for c in (res.get("changes") or []):
            print("       → %-10s 安全库存 %.3f → %.3f"
                  % (c["name"], c["safety_factor"][0], c["safety_factor"][1]))
    print()

    # ── 汇总验收 ──
    st = memory.memory_stats()
    print("=" * 84)
    print("完成")
    print("=" * 84)
    print("  本次新增 experience: %d 条" % total_exp)
    print("  本次新增 evolution  : %d 条" % total_chg)
    print()
    print("  memory_stats() 现状：")
    for k, v in st.items():
        print("     %-24s: %s" % (k, v))
    print()
    exps = memory.get_experiences(limit=20)
    print("  经验清单（共 %d 条）：" % len(exps))
    for e in exps:
        nm = prods.get(e["sku"], {}).get("name", e["sku"])
        print("     [%s] %-10s %-6s %s" % (e["day"], nm, e["event_type"], e["lesson"]))
    print()
    print("  下一步：运行 python app.py 打开「它学会了什么」「店里的老账本」查看。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
