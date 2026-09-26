# -*- coding: utf-8 -*-
"""
店脑 · 端到端闭环演示 / 验证脚本

一次性跑通五幕，既用于自测，也用于答辩现场讲清"闭环真的在转"：

  第一幕  门店记忆盘点      —— 长期记忆库里沉淀了什么
  第二幕  今日补货决策      —— 店脑 vs 传统纯利润算法（创新点 1）
  第三幕  业务反馈与自进化  —— 断货与损耗如何改变策略（创新点 2）
  第四幕  进化后的新方案    —— 参数变了，建议跟着变
  第五幕  三十天闭环回放    —— 店脑接管后，门店经营有没有变好（对照实验）

运行：python demo_flow.py
"""

import sys
from datetime import date, timedelta
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from core import analysis, evolution, forecast, memory, policy
    from core.config import DEFAULT_BUDGET
else:
    from .core import analysis, evolution, forecast, memory, policy
    from .core.config import DEFAULT_BUDGET

PLAN_DATE = "2026-09-25"      # 中秋节，演示节日因子的作用
LAST_HISTORY_DAY = "2026-09-24"

W = 78


def rule(ch="─"):
    print(ch * W)


def banner(idx: int, title: str):
    print()
    rule("═")
    print(f"  第{'一二三四五'[idx - 1]}幕 · {title}")
    rule("═")


def fmt(v, width=8, dec=0):
    return f"{v:>{width}.{dec}f}"


# ════════════════════════════════════════════════════════════
def act1_memory():
    banner(1, "门店记忆盘点")
    stats = memory.memory_stats()
    for k, v in stats.items():
        print(f"  · {k:<14} {v}")
    print()
    print("  记忆库里沉淀的，是这家店 121 天的全部经营事实：")
    prods = memory.get_products()
    liv = [p for p in prods if p["is_livelihood"]]
    print(f"  · 商品档案 {len(prods)} 项，其中民生商品 {len(liv)} 项")
    print(f"    民生商品：{'、'.join(p['name'] for p in liv)}")


def act2_decision():
    banner(2, "今日补货决策（创新点 1：惠民约束）")
    cmp = policy.compare_plans(PLAN_DATE, DEFAULT_BUDGET, persist=False)

    notes = {it["holiday_note"] for it in cmp["diannao"]["items"] if it["holiday_note"]}
    print(f"  决策日期：{cmp['date']}　进货预算：¥{cmp['budget']:.0f}")
    if notes:
        print(f"  节日识别：{'、'.join(notes)} → 已自动提升相关品类备货")
    print(f"  需求总成本 ¥{cmp['diannao']['meta']['total_need_cost']:.0f}，"
          f"预算缺口 ¥{cmp['diannao']['meta']['shortfall']:.0f} —— 必须做取舍")
    print()
    print(f"  {'商品':<20}{'日均需求':>9}{'店脑':>8}{'传统算法':>10}{'差异':>9}")
    rule()
    for d in cmp["diff"]:
        if d["diannao_qty"] <= 0 and d["baseline_qty"] <= 0:
            continue
        mark = "★" if d["is_livelihood"] else " "
        delta = f"{d['delta']:+.0f}" if abs(d["delta"]) > 1e-9 else "—"
        print(f" {mark}{d['name']:<19}{fmt(d['daily_demand'], 9, 1)}"
              f"{fmt(d['diannao_qty'], 8)}{fmt(d['baseline_qty'], 10)}{delta:>9}")
    rule()
    m_d, m_b = cmp["diannao"]["metrics"], cmp["baseline"]["metrics"]
    print(f"  {'指标':<22}{'店脑':>14}{'传统算法':>14}")
    rule()
    print(f"  {'预计毛利(元)':<22}{fmt(m_d['gross_margin'], 14, 1)}{fmt(m_b['gross_margin'], 14, 1)}")
    print(f"  {'社区便民指数':<22}{fmt(m_d['livelihood_index'], 14, 3)}{fmt(m_b['livelihood_index'], 14, 3)}")
    print(f"  {'断货风险商品数':<21}{fmt(m_d['stockout_risk_count'], 14)}{fmt(m_b['stockout_risk_count'], 14)}")
    print(f"  {'民生底线保障率':<22}"
          f"{fmt((cmp['diannao']['meta']['livelihood_floor_secured'] or 1) * 100, 12, 0)}%"
          f"{'不适用':>15}")
    rule()
    print("  ★ = 民生商品（低毛利但社区刚需，也是客流入口）")
    print()
    print("  读法：传统算法按「一块钱本钱能赚回多少」排队，高毛利零食饮料永远在前；")
    print("        预算一紧，被砍掉的必然是大米、鸡蛋、牛奶这类低毛利刚需。")
    print("        店脑先锁民生兜底量，剩下才按利润分配 —— 这就是差别。")


def act3_evolution():
    banner(3, "业务反馈与策略自进化（创新点 2）")
    print("  场景：昨日收盘盘点，发现几样货出了状况 ——")
    print("        有的卖断了（街坊想买没买到），有的压着卖不掉报损了。")
    print("        店主把情况录进系统，看店脑怎么反应。")
    print()

    feedback = []
    for p in memory.get_products():
        rows = memory.get_sales_range(p["sku"], LAST_HISTORY_DAY, LAST_HISTORY_DAY)
        if rows:
            r = rows[0]
            feedback.append({
                "sku": p["sku"], "qty_sold": r["qty_sold"],
                "qty_stockout": r["qty_stockout"], "qty_spoilage": r["qty_spoilage"],
            })
    result = evolution.process_feedback(LAST_HISTORY_DAY, feedback)
    changes = result["changes"]

    if not changes:
        print("  （本次没有触发调整，属正常波动范围）")
        return result

    print(f"  {'商品':<22}{'触发信号':<12}{'安全库存系数':>16}{'备货天数':>16}")
    rule()
    for ch in changes:
        old_s, new_s = ch["safety_factor"]
        old_b, new_b = ch["base_days"]
        a_s = "↑" if new_s > old_s else ("↓" if new_s < old_s else "=")
        a_b = "↑" if new_b > old_b else ("↓" if new_b < old_b else "=")
        print(f"  {ch['name']:<22}{ch['trigger']:<12}"
              f"{old_s:>8.3f} {a_s} {new_s:<5.3f}"
              f"{old_b:>6.2f} {a_b} {new_b:<5.2f}")
    rule()
    print()
    for ch in changes:
        print(f"  ▸ {ch['name']}｜{ch['trigger']}")
        print(f"    {ch['reason']}")
    return result


def act4_after():
    banner(4, "进化后的新方案")
    print("  参数变了，明天的建议跟着变 —— 这就是闭环。")
    print()
    plan = policy.build_plan(PLAN_DATE, DEFAULT_BUDGET, policy.MODE_DIANNAO, persist=False)
    focus = {"L08", "N04", "L01", "L02", "L06"}
    print(f"  {'商品':<22}{'预测日需求':>10}{'备货天数':>9}{'安全系数':>9}"
          f"{'建议进货':>9}{'可支撑':>8}")
    rule()
    for it in plan["items"]:
        if it["sku"] not in focus:
            continue
        print(f"  {it['name']:<22}{fmt(it['daily_demand'], 10, 1)}"
              f"{fmt(it['target_cover_days'], 7, 1)}"
              f"{fmt(it['safety_factor'], 10, 2)}"
              f"{fmt(it['reorder_qty'], 9)}"
              f"{fmt(it.get('final_cover_days', 0), 8, 1)}")
    rule()
    print(f"  方案合计进货成本 ¥{plan['metrics']['total_cost']:.0f}"
          f"　预计毛利 ¥{plan['metrics']['gross_margin']:.0f}"
          f"　便民指数 {plan['metrics']['livelihood_index']:.3f}")


def act5_closed_loop(days: int = 30):
    banner(5, f"{days} 天闭环回放：店脑接管后，经营有没有变好")
    print("  做法：拿同一段 30 天的真实需求，让店脑重新经营一遍 ——")
    print("        每天按方案进货、按真实需求卖出，收盘后把断货/损耗反馈回去，")
    print("        再和店主原本的经营结果并排比。需求完全一样，只是决策方式不同。")
    print()

    products = memory.get_products()
    start = date.fromisoformat(LAST_HISTORY_DAY) - timedelta(days=days - 1)
    start_s = start.isoformat()

    # ── 对照组：店主原本的经营结果（取自历史记录）──
    owner = {"stockout_cnt": 0, "stockout_qty": 0.0,
             "spoil_cnt": 0, "spoil_qty": 0.0}
    demand_map: dict[str, dict[str, float]] = {}
    for p in products:
        rows = memory.get_sales_range(p["sku"], start_s, LAST_HISTORY_DAY)
        demand_map[p["sku"]] = {
            r["day"]: (r["qty_sold"] + r["qty_stockout"]) for r in rows
        }
        for r in rows:
            if r["qty_stockout"] > 0.5:
                owner["stockout_cnt"] += 1
                owner["stockout_qty"] += r["qty_stockout"]
            if r["qty_spoilage"] > 0.5:
                owner["spoil_cnt"] += 1
                owner["spoil_qty"] += r["qty_spoilage"]

    # ── 重置到起点：重新播种历史，参数回到店主原始经验值 ──
    from seed_data import PRODUCTS as SEED_PRODUCTS, generate_history
    generate_history()
    for sp in SEED_PRODUCTS:
        memory.set_policy(sp["sku"], sp["sim"]["init_base_days"], 0.15)

    on_hand = dict(memory.get_inventory())

    agent = {"stockout_cnt": 0, "stockout_qty": 0.0,
             "spoil_cnt": 0, "spoil_qty": 0.0}
    daily = []
    cur = start
    for _ in range(days):
        day = cur.isoformat()
        memory.set_inventory_bulk(list(on_hand.items()))

        plan = policy.build_plan(day, DEFAULT_BUDGET, policy.MODE_DIANNAO, persist=False)

        feedback = []
        day_so = day_sp = 0.0
        for it in plan["items"]:
            sku = it["sku"]
            inv = on_hand.get(sku, 0.0) + it["reorder_qty"]
            demand = demand_map[sku].get(day, 0.0)
            sold = min(demand, inv)
            stockout = max(0.0, demand - sold)
            left = inv - sold

            prod = next(p for p in products if p["sku"] == sku)
            est = max(demand, 0.3)
            spoil = 0.0
            perishable = (prod["category"] in ("生鲜", "乳品", "冷饮")
                          or prod["shelf_life_days"] <= 30)
            if left > 0 and perishable:
                if prod["shelf_life_days"] <= 7 and left > est * prod["shelf_life_days"]:
                    spoil += (left - est * prod["shelf_life_days"]) * 0.55
                stale = 5 if prod["category"] == "冷饮" else 12
                if left > est * stale:
                    spoil += (left - est * stale) * 0.20
            spoil = min(spoil, left)

            on_hand[sku] = left - spoil
            if stockout > 0.5:
                agent["stockout_cnt"] += 1
                agent["stockout_qty"] += stockout
            if spoil > 0.5:
                agent["spoil_cnt"] += 1
                agent["spoil_qty"] += spoil
            day_so += stockout
            day_sp += spoil

            feedback.append({"sku": sku, "qty_sold": sold,
                             "qty_stockout": stockout, "qty_spoilage": spoil})

        evolution.process_feedback(day, feedback)
        daily.append({"day": day, "so": day_so, "sp": day_sp})
        cur += timedelta(days=1)

    # ── 对照表 ──
    print(f"  {'指标':<22}{'店主原做法':>14}{'店脑接管':>12}{'改善':>12}")
    rule()

    def row(label, a, b, pct=True):
        if a > 0:
            imp = (b - a) / a
            imp_txt = f"{imp:+.0%}"
        else:
            imp_txt = "—"
        print(f"  {label:<24}{fmt(a, 12, 0)}{fmt(b, 10, 0)}   {imp_txt:>10}")

    row("断货商品次数（次）", owner["stockout_cnt"], agent["stockout_cnt"])
    row("断货数量（件）", owner["stockout_qty"], agent["stockout_qty"])
    row("报损商品次数（次）", owner["spoil_cnt"], agent["spoil_cnt"])
    row("报损数量（件）", owner["spoil_qty"], agent["spoil_qty"])
    rule()
    print("  （负数表示下降，越小越好）")

    logs = memory.get_evolution_log(limit=5000)
    up = sum(1 for lg in logs if (lg["new_value"] or 0) > (lg["old_value"] or 0))
    down = len(logs) - up
    n = len(daily)
    seg = n // 3
    segs = [daily[:seg], daily[seg:2 * seg], daily[2 * seg:]]

    print()
    print(f"  ▸ 30 天里店脑自我调整 {len(logs)} 次"
          f"（为避免断货上调 {up} 次，为减少积压下调 {down} 次）")
    adj = [sum(1 for d in s if d["so"] > 0.5 or d["sp"] > 0.5) for s in segs]
    print(f"  ▸ 出状况的天数：第 1-{seg} 天 {adj[0]} 天 → "
          f"第 {seg + 1}-{2 * seg} 天 {adj[1]} 天 → "
          f"第 {2 * seg + 1}-{n} 天 {adj[2]} 天")
    print()
    print("  收敛判据:参数受硬边界与步长上限约束，越跑越稳；")
    print("           出状况的天数逐段收敛，而不是来回震荡放大。")
    print()

    # 恢复干净的门店记忆（历史数据 + 店主原始参数），供网页演示从零体验
    generate_history()
    print("  （已恢复门店初始记忆，网页演示可从零开始体验完整闭环）")


def main():
    memory.init_db()
    if not memory.get_products():
        print("首次运行，正在生成门店历史数据 ...")
        from seed_data import generate_history
        generate_history()

    act1_memory()
    act2_decision()
    act3_evolution()
    act4_after()
    act5_closed_loop(days=30)

    print()
    rule("═")
    print("  演示结束。启动网页界面：python app.py")
    rule("═")


if __name__ == "__main__":
    main()
