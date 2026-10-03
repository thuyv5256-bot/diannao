# -*- coding: utf-8 -*-
"""
小满 · Event-Aware vs Event-Blind 公平对照实验（验证「事件感知」的价值）

要回答的问题：
    在完全相同的外部风险事件已经真实发生的情况下，
    「能感知事件的 Agent」与「不能感知事件的 Agent」最终经营结果差多少。

公平性（与消融「无 Event」的本质区别）：
    这里不是比较「有事件的世界 vs 没事件的世界」，而是比较——
       · 外部世界完全相同：同一份 180 天真实需求（CSV sales 已内嵌高温/暴雨/节假日
         对销量的真实冲击）、同一份天气/节假日/供应商断供事件、同一初始库存、
         同一预算、同一 R³/Memory/Forecast/民生参数；
       · 唯一区别 = Agent 能否提前读取并利用事件信息。
         Event-Aware：use_events=True  → 感知高温/暴雨/节假日/供应商断供
         Event-Blind：use_events=False → 外部事件照常发生，但决策时看不到

供应商断供的「环境强制」：
    断供由仿真器结算层强制拦截（core.simulator._enforce_supplier_outage），
    与 Agent 是否知晓无关 —— 两个世界里供应商 D 在 07-29~31 都真的断供；
    区别只是 Aware 能提前停采并让 R³ 重分配，Blind 照常下单但订单被环境拦截。

运行：python run_event_awareness_ab.py
"""
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import simulator
from core.config import CURRENCY

W = 96


def _add_days(day: str, n: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=n)).isoformat()


def rule(ch="─"):
    print(ch * W)


def pct(v):
    return f"{v:.2%}"


def money(v):
    return f"{CURRENCY}{v:,.0f}"


def stockout_in_window(daily: list[dict], event_days: list[str],
                       follow_days: int = 0) -> tuple[float, float]:
    """返回某事件窗口内的 (缺货件数, 需求件数)。窗口 = 事件日 + 其后 follow_days 天。"""
    window = set(event_days)
    for d in event_days:
        for k in range(1, follow_days + 1):
            window.add(_add_days(d, k))
    stockout = sum(r["stockout_qty"] for r in daily if r["day"] in window)
    demand = sum(r["demand_qty"] for r in daily if r["day"] in window)
    return stockout, demand


def main():
    budget = simulator.DEFAULT_SIM_BUDGET
    seed = simulator.DEFAULT_SEED
    gt = simulator.load_ground_truth()
    ev = Counter(gt["event_by_day"].values())

    rule("═")
    print("  小满 · Event-Aware vs Event-Blind 公平对照实验（180 天）")
    print(f"  预算 {money(budget)}/天 · seed={seed} · 外部事件完全一致（{dict(ev)}）")
    rule("═")
    print("  Event-Aware  = 小满 R³ 感知事件；Event-Blind = 小满 R³ 决策时看不到事件")
    print("  两世界外部环境完全相同：真实需求 / 天气 / 节假日 / 供应商断供 / 初始库存一致")
    print()

    results = simulator.run_strategies(
        ["diannao", "diannao_no_event"], budget=budget, seed=seed, keep_daily=True)
    aware = results["diannao"]
    blind = results["diannao_no_event"]
    sa, sb = aware["summary"], blind["summary"]

    # ── 总表 ──
    rule("═")
    print(" 一、180 天完整结果")
    rule("═")
    hdr = f"  {'指标':<20}{'Event-Aware':>16}{'Event-Blind':>16}{'差异':>16}"
    print(hdr)
    rule()

    def row(label, va, vb, fmt):
        if fmt == "money":
            ta, tb, delta = money(va), money(vb), money(va - vb)
        elif fmt == "pct":
            ta, tb = pct(va), pct(vb)
            delta = f"{va - vb:+.2f}pp"
        else:
            ta, tb = f"{va:,.1f}", f"{vb:,.1f}"
            delta = f"{va - vb:+,.1f}"
        print(f"  {label:<20}{ta:>16}{tb:>16}{delta:>16}")

    row("累计毛利（元）", sa["cumulative_gross_margin"], sb["cumulative_gross_margin"], "money")
    row("总体缺货率", sa["stockout_rate"], sb["stockout_rate"], "pct")
    row("民生实际缺货率", sa["livelihood_stockout_rate"], sb["livelihood_stockout_rate"], "pct")
    row("民生缺货件数", sa["livelihood_stockout_qty"], sb["livelihood_stockout_qty"], "num")
    row("损耗率", sa["spoilage_rate"], sb["spoilage_rate"], "pct")
    row("平均库存资金占用（元）", sa["avg_inventory_capital"], sb["avg_inventory_capital"], "money")
    rule()
    print("  （差异 = Aware − Blind；缺货类指标为负表示 Aware 更少缺货、更优）")
    print()

    # ── 分事件表 ──
    event_days = {k: [d for d, e in gt["event_by_day"].items() if e == k]
                  for k in ("高温", "暴雨", "节假日", "供应商D断供")}
    da = aware["daily"]
    db = blind["daily"]

    rule("═")
    print(" 二、分事件缺货对比（事件期间，及事件期间 + 后 3 天后续影响窗口）")
    rule("═")
    print(f"  {'场景':<12}{'期间缺货(件)':>28}{'期间+后3天缺货(件)':>30}")
    print(f"  {'':<12}{'Aware':>9}{'Blind':>9}{'差异':>10}"
          f"{'Aware':>9}{'Blind':>9}{'差异':>11}")
    rule()
    for label in ("高温", "暴雨", "节假日", "供应商D断供"):
        days = event_days[label]
        s0_a, _ = stockout_in_window(da, days, follow_days=0)
        s0_b, _ = stockout_in_window(db, days, follow_days=0)
        s3_a, _ = stockout_in_window(da, days, follow_days=3)
        s3_b, _ = stockout_in_window(db, days, follow_days=3)
        print(f"  {label:<12}{s0_a:>9,.1f}{s0_b:>9,.1f}{s0_a - s0_b:>+10,.1f}"
              f"{s3_a:>9,.1f}{s3_b:>9,.1f}{s3_a - s3_b:>+11,.1f}")
    rule()
    print("  （差异 = Aware − Blind；负值 = Aware 缺货更少）")
    print()

    rule("═")
    print("  结论：Event Tool 是否带来可验证的价值，见运行后的综合分析。")
    rule("═")


if __name__ == "__main__":
    main()
