# -*- coding: utf-8 -*-
"""
小满 · 离线评测命令行入口

运行：python eval.py
产出：控制台对照表 + eval_report.md + eval_results.csv + eval_results.html
"""

import csv
import sys
from pathlib import Path

# Windows 控制台默认 GBK，打印「¥ / 中文」可能编码失败；统一改走 UTF-8，
# 且损坏字符替换而非崩溃（文件产物始终显式以 UTF-8 写出，不受影响）。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from core.eval_core import DAYS, MODES, SEEDS, _mean, _pct, build_figure, run_eval
else:
    from .core.eval_core import DAYS, MODES, SEEDS, _mean, _pct, build_figure, run_eval


def _report(results, days, n_seeds):
    print()
    print("=" * 92)
    print(f"  小满 · 离线评测与消融实验（{days} 天闭环 × {n_seeds} 个随机种子取均值）")
    print("=" * 92)
    print(f"{'决策方式':<22}{'断货次数':>9}{'断货量':>9}{'报损次数':>9}{'报损量':>9}"
          f"{'净毛利(¥)':>11}{'便民指数':>9}")
    print("-" * 92)
    for mode, label in MODES:
        rs = results[mode]
        liv = f"{'—':>9}" if mode == "owner" else f"{_mean(rs, 'livelihood_index'):>9.3f}"
        print(f"{label:<22}"
              f"{_mean(rs, 'stockout_cnt'):>9,.0f}"
              f"{_mean(rs, 'stockout_qty'):>9,.0f}"
              f"{_mean(rs, 'spoil_cnt'):>9,.0f}"
              f"{_mean(rs, 'spoil_qty'):>9,.0f}"
              f"{_mean(rs, 'gross_margin'):>11,.0f}"
              f"{liv}")
    print("-" * 92)
    print("  （断货/报损：越小越好；净毛利/便民指数：越大越好）")
    print()


def _ablation_notes(results):
    base_so = _mean(results["diannao"], "stockout_qty")
    base_sp = _mean(results["diannao"], "spoil_qty")
    print("消融解读 —— 相对「小满完整版」每个设计点被拿掉后差了多少：")

    # 惠民约束的价值在「便民指数 / 民生断货」，不在总断货：
    # 传统算法把总断货压得一样低，但它是靠砍低毛利民生货换来的。
    bl_liv = _mean(results["baseline"], "livelihood_index")
    dn_liv = _mean(results["diannao"], "livelihood_index")
    bl_liv_so = _mean(results["baseline"], "stockout_qty_livelihood")
    dn_liv_so = _mean(results["diannao"], "stockout_qty_livelihood")
    print(f"  · 去掉惠民约束      便民指数 {dn_liv:.3f} → {bl_liv:.3f}，"
          f"民生断货量 {dn_liv_so:,.0f} → {bl_liv_so:,.0f}")

    for mode, label in [("no_evolve", "去掉策略自进化"),
                        ("no_potential", "去掉需求还原")]:
        so = _pct(_mean(results[mode], "stockout_qty"), base_so)
        sp = _pct(_mean(results[mode], "spoil_qty"), base_sp)
        print(f"  · {label:<14} 断货量 {so:>7}，报损量 {sp:>7}")
    print("  （便民指数下降 / 民生断货变多 / 断货量上升 = 该设计点确实在起作用）")
    print()


def _write_csv(results):
    with open("eval_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["mode", "seed", "stockout_cnt", "stockout_qty", "spoil_cnt",
                    "spoil_qty", "gross_margin", "livelihood_index"])
        for mode, _ in MODES:
            for seed, r in zip(SEEDS, results[mode]):
                w.writerow([
                    mode, seed,
                    round(r.get("stockout_cnt", 0.0), 1),
                    round(r.get("stockout_qty", 0.0), 1),
                    round(r.get("spoil_cnt", 0.0), 1),
                    round(r.get("spoil_qty", 0.0), 1),
                    round(r.get("gross_margin", 0.0), 1),
                    "" if mode == "owner" else round(r.get("livelihood_index", 0.0), 4),
                ])


def _write_markdown(results, days, n_seeds):
    L = []
    L.append("# 小满 · 离线评测报告")
    L.append("")
    L.append(f"> {days} 天闭环 × {n_seeds} 个随机种子取均值。断货/报损越小越好，"
             f"净毛利/便民指数越大越好。")
    L.append("")
    L.append("## 一、核心指标对照")
    L.append("")
    L.append("| 决策方式 | 断货次数 | 断货量 | 报损次数 | 报损量 | 净毛利(¥) | 便民指数 |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for mode, label in MODES:
        rs = results[mode]
        liv = "—" if mode == "owner" else f"{_mean(rs, 'livelihood_index'):.3f}"
        L.append(f"| {label} | {_mean(rs, 'stockout_cnt'):,.0f} | {_mean(rs, 'stockout_qty'):,.0f} | "
                 f"{_mean(rs, 'spoil_cnt'):,.0f} | {_mean(rs, 'spoil_qty'):,.0f} | "
                 f"{_mean(rs, 'gross_margin'):,.0f} | {liv} |")
    L.append("")
    L.append("## 二、消融解读（相对「小满完整版」）")
    L.append("")
    base_so = _mean(results["diannao"], "stockout_qty")
    base_sp = _mean(results["diannao"], "spoil_qty")
    L.append("| 拿掉的设计点 | 关键指标变化 |")
    L.append("|---|:---|")
    bl_liv = _mean(results["baseline"], "livelihood_index")
    dn_liv = _mean(results["diannao"], "livelihood_index")
    bl_liv_so = _mean(results["baseline"], "stockout_qty_livelihood")
    dn_liv_so = _mean(results["diannao"], "stockout_qty_livelihood")
    L.append(f"| 去掉惠民约束 | 便民指数 {dn_liv:.3f} → {bl_liv:.3f}，"
             f"民生断货量 {dn_liv_so:,.0f} → {bl_liv_so:,.0f} |")
    for mode, label in [("no_evolve", "去掉策略自进化"),
                        ("no_potential", "去掉潜在需求还原")]:
        L.append(f"| {label} | 断货量 {_pct(_mean(results[mode], 'stockout_qty'), base_so)}，"
                 f"报损量 {_pct(_mean(results[mode], 'spoil_qty'), base_sp)} |")
    L.append("")
    L.append("## 三、可视化")
    L.append("")
    L.append("交互式柱状图见 [eval_results.html](./eval_results.html)。")
    L.append("")
    with open("eval_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("  Markdown 报告已写入 eval_report.md")


def main():
    results = run_eval(SEEDS, DAYS)
    _report(results, DAYS, len(SEEDS))
    _ablation_notes(results)
    _write_csv(results)
    _write_markdown(results, DAYS, len(SEEDS))
    try:
        fig = build_figure(results, DAYS, len(SEEDS))
        fig.write_html("eval_results.html")
        print("  图表已写入 eval_results.html")
    except Exception as e:
        print(f"  （图表生成失败，跳过：{e}）")

    print("  结果已写入 eval_results.csv / eval_report.md / eval_results.html；"
          "正在恢复门店初始记忆供网页演示 ...")
    from seed_data import generate_history
    generate_history()
    print("  完成。启动网页：python app.py")


if __name__ == "__main__":
    main()
