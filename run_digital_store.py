# -*- coding: utf-8 -*-
"""
小满 · Digital Store 180 天长期实验命令行入口

一次性跑完「主对比（小满 vs 传统纯利润）+ 风险压力测试 + 消融实验」，
并把真实结果落盘到 eval/：

    eval/digital_store_daily.csv       逐日逐 SKU 明细（2 策略 × 180 天 × 50 SKU）
    eval/digital_store_summary.csv     主对比长期指标汇总
    eval/digital_store_stress.csv      风险压力测试（前 / 中 / 后 三段）
    eval/ablation_results.csv          消融实验（5 个策略）
    eval/digital_store_config.json     实验配置（日期范围 / 预算 / 种子 / 策略 / 风险场景）

运行：
    python run_digital_store.py                 # 预算 ¥1800 / 天，seed=42
    python run_digital_store.py 1500 7          # 自定义预算与种子

说明：5 个策略共用同一份需求序列，只跑一遍（主对比的 2 个策略不重复跑），
     所以单次运行约需 5~8 分钟（其中完整小满每次约 100s，传统算法约 20s）。
"""

import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from core import simulator
    from core.config import CURRENCY
else:
    from .core import simulator
    from .core.config import CURRENCY

W = 96


def _setup_console():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def rule(ch="─"):
    print(ch * W)


def pct(v):
    return f"{v:.2%}"


def money(v):
    return f"{CURRENCY}{v:,.0f}"


def main():
    _setup_console()
    budget = float(sys.argv[1]) if len(sys.argv) > 1 else simulator.DEFAULT_SIM_BUDGET
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else simulator.DEFAULT_SEED

    rule("═")
    print(f"  小满 · Digital Store 180 天长期实验")
    print(f"  预算 {money(budget)}/天 · 随机种子 seed={seed} · 需求序列 = CSV 真实仿真数据（固定）")
    rule("═")

    gt = simulator.load_ground_truth()
    d0, d1 = gt["day_list"][0], gt["day_list"][-1]
    print(f"  日期范围：{d0} ~ {d1}（{len(gt['day_list'])} 天）· {len(gt['products'])} 个 SKU")
    from collections import Counter
    ev = Counter(gt["event_by_day"].values())
    print(f"  经营事件分布：{dict(ev)}")
    print()

    t0 = time.time()
    print("  正在运行 5 个策略（主对比 2 + 消融 3）…… 请稍候")
    results = simulator.run_strategies(
        simulator.ABLATION_STRATEGIES, budget=budget, seed=seed, keep_daily=True)
    print(f"  5 个策略全部跑完，耗时 {time.time() - t0:.0f}s\n")

    main_results = {k: results[k] for k in simulator.MAIN_STRATEGIES}
    paths = simulator.write_csvs(main_results, gt, budget, seed,
                                 simulator.MAIN_STRATEGIES, keep_daily=True)
    stress_rows = simulator.stress_analysis(main_results, gt)
    stress_path = simulator.write_stress_csv(stress_rows)
    ablation_path = simulator.write_ablation_csv(results)

    # ── 主对比 ──
    rule("═")
    print(" 一、主对比：小满 R³ vs 传统纯利润（180 天）")
    rule("═")
    hdr = (f"  {'指标':<22}{'小满 R³':>16}{'传统算法':>16}{'差异':>16}")
    print(hdr)
    rule()
    d, b = results["diannao"]["summary"], results["baseline"]["summary"]

    def row(label, da, ba, money_fmt=False, pct_fmt=False):
        if money_fmt:
            da_t, ba_t = money(da), money(ba)
        elif pct_fmt:
            da_t, ba_t = pct(da), pct(ba)
        else:
            da_t, ba_t = f"{da:,}", f"{ba:,}"
        delta = ""
        if isinstance(da, (int, float)) and isinstance(ba, (int, float)):
            if pct_fmt:
                delta = f"{da - ba:+.2f}pp"
            elif money_fmt:
                delta = money(da - ba)
            elif isinstance(da, int) and isinstance(ba, int):
                delta = f"{da - ba:+,d}"
            else:
                delta = f"{da - ba:+,.2f}"
        print(f"  {label:<22}{da_t:>16}{ba_t:>16}{delta:>16}")

    row("累计毛利（元）", d["cumulative_gross_margin"], b["cumulative_gross_margin"], money_fmt=True)
    row("总体缺货率", d["stockout_rate"], b["stockout_rate"], pct_fmt=True)
    row("民生最低保障达标率", d["livelihood_secured_rate"], b["livelihood_secured_rate"], pct_fmt=True)
    row("民生商品实际缺货率", d["livelihood_stockout_rate"], b["livelihood_stockout_rate"], pct_fmt=True)
    row("民生商品实际缺货件数", d["livelihood_stockout_qty"], b["livelihood_stockout_qty"])
    row("缺货件数", d["stockout_qty"], b["stockout_qty"])
    row("发生缺货的 SKU 数", d["stockout_sku_count"], b["stockout_sku_count"])
    row("缺货次数（SKU×日）", d["stockout_occurrences"], b["stockout_occurrences"])
    row("损耗率", d["spoilage_rate"], b["spoilage_rate"], pct_fmt=True)
    row("损耗/报废件数", d["spoilage_qty"], b["spoilage_qty"])
    row("平均库存资金占用（元）", d["avg_inventory_capital"], b["avg_inventory_capital"], money_fmt=True)
    row("库存周转（180 天内，次）", d["inventory_turnover"], b["inventory_turnover"])
    rule()
    print("  结论：", simulator.conclusion_text(main_results))
    print()

    # ── 压力测试 ──
    rule("═")
    print(" 二、风险压力测试（发生前 3 天 → 发生期间 → 结束后 3 天）")
    rule("═")
    by_risk = {}
    for r in stress_rows:
        by_risk.setdefault(r["risk"], []).append(r)
    print(f"  {'风险场景':<12}{'阶段':<8}{'小满总体缺货率':>12}{'传统总体缺货率':>12}"
          f"{'小满民生达标率':>12}{'传统民生达标率':>12}{'小满均库存':>12}{'传统均库存':>12}")
    rule()
    phase_label = {"before": "发生前", "during": "期间", "after": "结束后"}
    for risk in ["高温", "暴雨", "供应商D断供", "综合风险"]:
        rows = by_risk.get(risk, [])
        for ph in ["before", "during", "after"]:
            drow = next((x for x in rows if x["strategy"] == "diannao" and x["phase"] == ph), None)
            brow = next((x for x in rows if x["strategy"] == "baseline" and x["phase"] == ph), None)
            if not drow or not brow:
                continue
            print(f"  {risk:<12}{phase_label[ph]:<8}{pct(drow['stockout_rate']):>12}"
                  f"{pct(brow['stockout_rate']):>12}{pct(drow['livelihood_rate']):>12}"
                  f"{pct(brow['livelihood_rate']):>12}{money(drow['avg_inventory_capital']):>12}"
                  f"{money(brow['avg_inventory_capital']):>12}")
    rule()
    print()

    # ── 消融 ──
    rule("═")
    print(" 三、消融实验（完整小满 逐项去掉一个设计点）")
    rule("═")
    print(f"  {'策略':<22}{'累计毛利':>12}{'总体缺货率':>9}{'民生最低保障达标率':>11}"
          f"{'损耗率':>9}{'平均库存':>12}{'周转':>8}")
    rule()
    for key in simulator.ABLATION_STRATEGIES:
        s = results[key]["summary"]
        print(f"  {s['label']:<22}{money(s['cumulative_gross_margin']):>12}"
              f"{pct(s['stockout_rate']):>9}{pct(s['livelihood_secured_rate']):>11}"
              f"{pct(s['spoilage_rate']):>9}{money(s['avg_inventory_capital']):>12}"
              f"{s['inventory_turnover']:>8.1f}")
    rule()
    print()

    rule("═")
    print("  结果文件：")
    for k, p in paths.items():
        print(f"    · {k:<8} {p}")
    print(f"    · stress  {stress_path}")
    print(f"    · ablation{ablation_path}")
    rule("═")


if __name__ == "__main__":
    main()
