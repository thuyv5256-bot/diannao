# -*- coding: utf-8 -*-
"""
小满 · 离线评测引擎（可复用的仿真 + 可视化）

供两处调用：
  · eval.py   —— 命令行评测入口（打印报告 / 写 CSV / Markdown / HTML）
  · app.py    —— 网页「项目说明」页内嵌评测柱状图（跑在隔离临时库上，不动在线记忆）

核心思路：拿同一段历史需求（多随机种子取平均），把几种决策方式放到同一个
时间窗口里重演，量化每个设计点的独立贡献。
"""

import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core import evolution, memory, metrics, policy
else:
    from . import evolution, memory, metrics, policy

DAYS = 60
# 历史数据来自固定 CSV（不再随机生成），多随机种子已无意义；
# 保留单一种子以复用原评测框架（多种子取均值退化为单次重演）。
SEEDS = [42]

# 评测预算：故意设紧，让「预算一紧，传统算法砍民生」的惠民约束真正显形。
# 线上 app 用 DEFAULT_BUDGET（宽裕），离线评测用更贴近小店现实的紧预算，
# 否则预算比日需求成本高一倍，谁都买得起，三个设计点全部退化成一团。
EVAL_BUDGET = 360.0

PERISHABLE_CATEGORIES = {"生鲜", "乳品", "冷饮"}

MODES = [
    ("owner", "店主原做法"),
    ("baseline", "传统算法（纯利润）"),
    ("diannao", "小满（完整）"),
    ("no_evolve", "小满·去掉自进化"),
    ("no_potential", "小满·去掉需求还原"),
]


def _spoil_qty(left: float, est: float, prod: dict) -> float:
    """复刻 demo_flow 第五幕的损耗口径，保证评测与演示一致。"""
    perishable = prod["category"] in PERISHABLE_CATEGORIES or prod["shelf_life_days"] <= 30
    if left <= 0 or not perishable:
        return 0.0
    spoil = 0.0
    if prod["shelf_life_days"] <= 7 and left > est * prod["shelf_life_days"]:
        spoil += (left - est * prod["shelf_life_days"]) * 0.55
    stale = 5 if prod["category"] == "冷饮" else 12
    if left > est * stale:
        spoil += (left - est * stale) * 0.20
    return min(spoil, left)


def _history_context(seed: int, days: int):
    """按 seed 生成历史，返回 (start, prod_map, demand_map, owner 指标)。"""
    from seed_data import generate_history
    generate_history()

    products = memory.get_products()
    last = max(memory.available_days())
    start = date.fromisoformat(last) - timedelta(days=days - 1)
    start_s = start.isoformat()

    prod_map = {p["sku"]: p for p in products}
    demand_map = {}
    owner = {"stockout_cnt": 0.0, "stockout_qty": 0.0, "spoil_cnt": 0.0,
             "spoil_qty": 0.0, "gross_margin": 0.0, "revenue": 0.0}

    for p in products:
        rows = memory.get_sales_range(p["sku"], start_s, last)
        demand_map[p["sku"]] = {r["day"]: (r["qty_sold"] + r["qty_stockout"]) for r in rows}
        margin = p["sell_price"] - p["cost_price"]
        for r in rows:
            owner["gross_margin"] += metrics.gross_margin(r["qty_sold"], margin, r["qty_spoilage"], p["cost_price"])
            owner["revenue"] += r["qty_sold"] * p["sell_price"]
            if r["qty_stockout"] > 0.5:
                owner["stockout_cnt"] += 1
                owner["stockout_qty"] += r["qty_stockout"]
            if r["qty_spoilage"] > 0.5:
                owner["spoil_cnt"] += 1
                owner["spoil_qty"] += r["qty_spoilage"]

    return start, prod_map, demand_map, owner


def _simulate(mode: str, start: date, prod_map: dict, demand_map: dict,
              days: int, seed: int, persist: bool = True) -> dict:
    """把某决策方式放到时间窗口里重演一遍，返回汇总指标。

    persist 控制落库行为：
      · False —— 评测重演专用。全程不写正式 store_memory.db：
        不调generate_history() 重建、不重置 inventory、不写 sales/经验。
        前提是调用方已把 memory.DB_PATH 指向隔离副本。
      · True（默认，保持旧行为）—— 只有调用方明确知道自己在隔离库时才安全。
    """
    if not persist:
        on_hand = {sku: p.get("on_hand", 0.0) for sku, p in prod_map.items()}
    else:
        from seed_data import generate_history
        generate_history()
        on_hand = dict(memory.get_inventory())

    plan_mode = policy.MODE_BASELINE if mode == "baseline" else policy.MODE_DIANNAO
    restore = mode != "no_potential"
    do_evolve = mode != "no_evolve"

    m = defaultdict(float)
    cur = start
    for _ in range(days):
        day = cur.isoformat()
        if persist:
            memory.set_inventory_bulk(list(on_hand.items()))
        plan = policy.build_plan(day, EVAL_BUDGET, plan_mode, persist=False,
                                 restore_potential=restore)
        m["cost"] += plan["metrics"]["total_cost"]
        m["livelihood_index"] += plan["metrics"]["livelihood_index"]

        feedback = []
        for it in plan["items"]:
            sku = it["sku"]
            prod = prod_map[sku]
            inv = on_hand.get(sku, 0.0) + it["reorder_qty"]
            demand = demand_map[sku].get(day, 0.0)
            sold = min(demand, inv)
            stockout = max(0.0, demand - sold)
            left = inv - sold
            spoil = _spoil_qty(left, max(demand, 0.3), prod)

            on_hand[sku] = left - spoil
            m["sold_qty"] += sold
            m["revenue"] += sold * prod["sell_price"]
            m["gross_margin"] += metrics.gross_margin(sold, prod["sell_price"] - prod["cost_price"], spoil, prod["cost_price"])
            if stockout > 0.5:
                m["stockout_cnt"] += 1
                m["stockout_qty"] += stockout
                if prod["is_livelihood"]:
                    m["stockout_qty_livelihood"] += stockout
                else:
                    m["stockout_qty_nonlivelihood"] += stockout
            if spoil > 0.5:
                m["spoil_cnt"] += 1
                m["spoil_qty"] += spoil
            feedback.append({"sku": sku, "qty_sold": sold,
                             "qty_stockout": stockout, "qty_spoilage": spoil})

        # 评测重演不得污染正式 Memory 库：显式 persist=False。
        # （评测读历史答案做指标统计，不需要把重演过程沉淀成经营经验。）
        if do_evolve:
            evolution.process_feedback(day, feedback, persist=False)
        else:
            # 「去掉自进化」只是冻结策略参数，销量照常入记忆，
            # 否则预测会永远停在店主旧历史，把"自进化"和"记忆"两个变量混在一起。
            evolution.apply_sales_only(day, feedback, persist=False)
        cur += timedelta(days=1)

    m["livelihood_index"] = m["livelihood_index"] / days
    return m


def _mean(rs, key):
    vals = [r[key] for r in rs if r.get(key) is not None]
    return sum(vals) / len(vals) if vals else 0.0


def _pct(new, old):
    if old == 0:
        return "—"
    return f"{(new - old) / old:+.0%}"


def run_eval(seeds=None, days: int = DAYS, db_path=None) -> dict:
    """运行评测，返回 {mode: [指标dict, ...]}。

    隔离保证（2026-10-04 起强制）：
      本评测会**反复重建**记忆库（每个模式 × 每个种子都调 generate_history()
      清空后重导 CSV），一旦跑在正式库上就会清掉店主真实录入的经营反馈
      与「演示门店·模拟经营历史」的经验。因此这里**总是**在隔离副本上运行；
      传 db_path 只是指定副本位置，不再影响是否隔离。
    """
    import shutil
    import tempfile
    from pathlib import Path
    if seeds is None:
        seeds = SEEDS
    old_path = memory.DB_PATH
    tmp = Path(db_path) if db_path else (
        Path(tempfile.gettempdir()) / "diannao_evalcore_sandbox.db")
    try:
        if tmp.exists():
            tmp.unlink()
        else:
            src = Path(memory.DB_PATH)
            if src.exists():
                shutil.copy2(src, tmp)
        memory.DB_PATH = str(tmp)
        memory.init_db()
        if not memory.get_products():
            from seed_data import generate_history
            generate_history()
        results = {mode: [] for mode, _ in MODES}
        for seed in seeds:
            start, prod_map, demand_map, owner = _history_context(seed, days)
            results["owner"].append(owner)
            for mode in ("baseline", "diannao", "no_evolve", "no_potential"):
                results[mode].append(
                    _simulate(mode, start, prod_map, demand_map, days, seed,
                              persist=True))   # True 只因已切到沙箱
        return results
    finally:
        memory.DB_PATH = old_path
        if db_path is None:
            for sfx in ("", "-wal", "-shm"):
                p = Path(str(tmp) + sfx)
                if p.exists():
                    try:
                        p.unlink()
                    except Exception:
                        pass


def _txt(key, v):
    """柱顶数值标签的格式化。"""
    if key == "livelihood_index":
        return f"{v:.0%}"
    if key == "gross_margin":
        return f"¥{v:,.0f}"
    return f"{v:,.0f}"


def build_figure(results, days: int, n_seeds: int):
    """构建 2×2 柱状对比图，返回 Plotly Figure（不写文件）。"""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    colors = {
        "owner": "#9aa5b1",
        "baseline": "#c0392b",
        "diannao": "#2c7a4b",
        "no_evolve": "#1f4e79",
        "no_potential": "#e67e22",
    }
    specs = [
        ("stockout_qty", "断货量（件）", "越低越好"),
        ("spoil_qty", "报损量（件）", "越低越好"),
        ("gross_margin", "净毛利（¥）", "越高越好"),
        ("livelihood_index", "便民指数", "越高越好"),
    ]

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[f"{name} · {note}" for _, name, note in specs],
        vertical_spacing=0.16, horizontal_spacing=0.12,
    )

    for i, (key, _name, _note) in enumerate(specs, start=1):
        row = (i - 1) // 2 + 1
        col = (i - 1) % 2 + 1
        for mode, label in MODES:
            if key == "livelihood_index" and mode == "owner":
                continue  # 店主无方案，便民指数不适用
            v = _mean(results[mode], key)
            fig.add_trace(
                go.Bar(
                    x=[label], y=[v],
                    marker_color=colors[mode],
                    text=[_txt(key, v)], textposition="outside",
                    name=label, showlegend=(i == 1),
                ),
                row=row, col=col,
            )

    fig.update_layout(
        title=dict(
            text=f"小满 · 离线评测结果（{days} 天闭环重演，历史来自固定 CSV）",
            font=dict(size=18, color="#1f4e79"),
        ),
        height=760,
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="right", x=1),
        margin=dict(l=60, r=40, t=110, b=60),
    )
    fig.update_xaxes(tickangle=-20)
    return fig
