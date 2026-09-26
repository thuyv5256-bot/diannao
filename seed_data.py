# -*- coding: utf-8 -*-
"""
店脑 · 门店历史数据仿真

为了让原型可完整演示，本模块仿真一家社区夫妻店 121 天的真实经营轨迹。
仿真遵循一个原则：**Agent 看到的世界 = 店主看到的世界**。
这里的 sim_* 参数（真实日均需求、季节曲线）是"上帝视角"，只用于生成数据；
Agent 只能从生成出来的销量记录里去学 —— 这一点在答辩时要讲清楚，
否则会被质疑"数据是喂给模型的答案"。

仿真中故意埋入三类典型经营事故，供后续演示"自进化"：
  · 7 月中旬 高温期矿泉水断货（店主没跟上夏季需求增长）
  · 8 月末   天气转凉雪糕积压损耗（店主进货量没跟着降）
  · 9 月下旬 中秋备货期部分民生商品吃紧
"""

import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

# 兼容"直接运行脚本"与"作为包导入"两种方式
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from core import memory
    from core.config import HOLIDAYS
    from core.forecast import HOLIDAY_FACTOR_BY_CATEGORY, DEFAULT_HOLIDAY_FACTOR
else:
    from .core import memory
    from .core.config import HOLIDAYS
    from .core.forecast import HOLIDAY_FACTOR_BY_CATEGORY, DEFAULT_HOLIDAY_FACTOR

# ── 门店商品档案 ──────────────────────────────────────────
# is_livelihood=1 表示民生商品（低毛利、高刚需、客流入口）
# traffic_pull：客流带动系数 —— 该商品缺货会在多大程度上流失客流
PRODUCTS = [
    # ── 民生商品（9 项）──
    dict(sku="L01", name="散装大米 5kg", category="粮油", unit="袋",
         cost_price=24.00, sell_price=26.50, is_livelihood=1, shelf_life_days=180,
         pack_size=4, traffic_pull=1.80,
         sim=dict(base_daily=1.00, init_days=5.0, init_base_days=5.0)),

    dict(sku="L02", name="鲜鸡蛋 30 枚", category="生鲜", unit="盒",
         cost_price=15.50, sell_price=16.90, is_livelihood=1, shelf_life_days=15,
         pack_size=6, traffic_pull=1.70,
         sim=dict(base_daily=1.50, init_days=4.0, init_base_days=2.5)),

    dict(sku="L03", name="加碘食盐 400g", category="调味", unit="袋",
         cost_price=1.60, sell_price=2.00, is_livelihood=1, shelf_life_days=730,
         pack_size=20, traffic_pull=1.30,
         sim=dict(base_daily=0.80, init_days=6.0, init_base_days=6.0)),

    dict(sku="L04", name="生抽酱油 500ml", category="调味", unit="瓶",
         cost_price=6.80, sell_price=8.00, is_livelihood=1, shelf_life_days=540,
         pack_size=12, traffic_pull=1.20,
         sim=dict(base_daily=0.60, init_days=5.0, init_base_days=5.0)),

    dict(sku="L05", name="精制挂面 900g", category="粮油", unit="袋",
         cost_price=3.90, sell_price=4.60, is_livelihood=1, shelf_life_days=365,
         pack_size=20, traffic_pull=1.40,
         sim=dict(base_daily=1.00, init_days=4.0, init_base_days=4.0)),

    dict(sku="L06", name="纯牛奶 250ml×12", category="乳品", unit="箱",
         cost_price=29.00, sell_price=32.50, is_livelihood=1, shelf_life_days=45,
         pack_size=1, traffic_pull=1.60,
         sim=dict(base_daily=0.80, init_days=5.0, init_base_days=3.0)),

    dict(sku="L07", name="卷纸 10 卷装", category="日化", unit="提",
         cost_price=13.50, sell_price=15.90, is_livelihood=1, shelf_life_days=999,
         pack_size=8, traffic_pull=1.50,
         sim=dict(base_daily=1.00, init_days=5.0, init_base_days=4.0)),

    dict(sku="L08", name="饮用纯净水 550ml", category="饮料", unit="瓶",
         cost_price=0.85, sell_price=1.50, is_livelihood=1, shelf_life_days=365,
         pack_size=24, traffic_pull=1.90,
         sim=dict(base_daily=30.0, init_days=4.0, init_base_days=2.0)),

    dict(sku="L09", name="刀切馒头", category="生鲜", unit="个",
         cost_price=0.70, sell_price=1.00, is_livelihood=1, shelf_life_days=3,
         pack_size=10, traffic_pull=1.40,
         sim=dict(base_daily=20.0, init_days=2.0, init_base_days=1.5)),

    # ── 高毛利弹性商品（7 项）──
    dict(sku="N01", name="薯片 70g", category="零食", unit="包",
         cost_price=4.20, sell_price=6.50, is_livelihood=0, shelf_life_days=180,
         pack_size=12, traffic_pull=1.00,
         sim=dict(base_daily=2.00, init_days=4.0, init_base_days=3.0)),

    dict(sku="N02", name="可乐 330ml×6", category="饮料", unit="提",
         cost_price=12.50, sell_price=17.50, is_livelihood=0, shelf_life_days=270,
         pack_size=1, traffic_pull=1.10,
         sim=dict(base_daily=1.20, init_days=4.0, init_base_days=3.0)),

    dict(sku="N03", name="牛奶巧克力 100g", category="零食", unit="块",
         cost_price=8.60, sell_price=13.90, is_livelihood=0, shelf_life_days=300,
         pack_size=6, traffic_pull=0.90,
         sim=dict(base_daily=0.80, init_days=5.0, init_base_days=4.0)),

    dict(sku="N04", name="雪糕（冷饮）", category="冷饮", unit="支",
         cost_price=3.50, sell_price=6.00, is_livelihood=0, shelf_life_days=200,
         pack_size=20, traffic_pull=0.80,
         sim=dict(base_daily=8.00, init_days=3.0, init_base_days=2.0)),

    dict(sku="N05", name="啤酒 500ml", category="酒饮", unit="瓶",
         cost_price=3.50, sell_price=4.80, is_livelihood=0, shelf_life_days=240,
         pack_size=12, traffic_pull=1.00,
         sim=dict(base_daily=6.00, init_days=4.0, init_base_days=3.0)),

    dict(sku="N06", name="进口曲奇饼干", category="零食", unit="盒",
         cost_price=9.80, sell_price=16.80, is_livelihood=0, shelf_life_days=400,
         pack_size=6, traffic_pull=0.90,
         sim=dict(base_daily=0.50, init_days=6.0, init_base_days=6.0)),

    dict(sku="N07", name="每日坚果 150g", category="零食", unit="袋",
         cost_price=14.00, sell_price=25.90, is_livelihood=0, shelf_life_days=270,
         pack_size=4, traffic_pull=0.90,
         sim=dict(base_daily=0.50, init_days=6.0, init_base_days=6.0)),
]

# 店主的进货习惯系数：<1 偏保守（容易断货），>1 偏激进（容易积压）
# 这是"凭经验进货"这件事的可复现刻画 —— 也是三类经营事故的成因。
OWNER_CAUTION = {
    "L01": 0.72,   # 大米：嫌占资金，进得少
    "L02": 0.68,   # 鸡蛋：怕压货变质，进得少
    "L06": 0.78,   # 牛奶：短保，进得少
    "L08": 0.52,   # 矿泉水：夏天严重备货不足 → 高温期断货
    "L09": 0.88,   # 馒头：短保
    "N03": 1.10,
    "N04": 1.85,   # 雪糕：盛夏惯性进货，季末压货 → 积压损耗
    "N05": 1.05,
    "N06": 1.18,
    "N07": 1.18,
}
DEFAULT_CAUTION = 1.0

# 星期曲线（周一→周日）：社区店周末客流明显更高
WEEKDAY_BASE = [0.95, 0.95, 0.98, 1.02, 1.10, 1.18, 1.10]
WEEKDAY_WEEKEND_HEAVY = [0.90, 0.90, 0.94, 1.00, 1.14, 1.34, 1.24]
WEEKEND_HEAVY_CATEGORIES = {"饮料", "冷饮", "酒饮", "零食"}

# 会因滞销/过期产生损耗的品类（调味品、日化等长保商品不会坏）
PERISHABLE_CATEGORIES = {"生鲜", "乳品", "冷饮"}

CHECK_INTERVAL = 2      # 店主每 2 天盘点一次货架（凭经验，不是每天看数据）

PROMO_DAYS = {8, 18, 28}          # 每月会员日
PROMO_LIFT = 1.25                 # 会员日拉动
PROMO_CATEGORIES = {"零食", "饮料", "冷饮", "酒饮"}


def _parse(d):
    return d if isinstance(d, date) else date.fromisoformat(str(d)[:10])


def season_factor(category: str, d: date) -> float:
    """季节曲线：饮料/冷饮夏季走高，9 月后回落。"""
    doy = d.timetuple().tm_yday
    peak = 201  # 约 7 月 20 日
    if category in ("饮料", "冷饮"):
        return 0.72 + 0.58 * math.exp(-((doy - peak) ** 2) / (2 * 46 ** 2))
    if category == "酒饮":
        return 0.84 + 0.40 * math.exp(-((doy - peak) ** 2) / (2 * 60 ** 2))
    if category == "生鲜":
        return 1.02 - 0.03 * math.sin(doy / 365 * 2 * math.pi)
    return 1.0


def holiday_lift(category: str, d: date) -> float:
    """节日拉动（仿真用真实节日日历 + 随机扰动，体现真实世界的不确定性）。"""
    day_str = d.strftime("%Y-%m-%d")
    pre1 = (d + timedelta(days=1)).strftime("%Y-%m-%d")
    pre2 = (d + timedelta(days=2)).strftime("%Y-%m-%d")
    pre_f, day_f = HOLIDAY_FACTOR_BY_CATEGORY.get(category, DEFAULT_HOLIDAY_FACTOR)

    if day_str in HOLIDAYS:
        base = day_f
    elif pre1 in HOLIDAYS:
        base = pre_f
    elif pre2 in HOLIDAYS:
        base = 1.0 + (pre_f - 1.0) * 0.65
    else:
        return 1.0
    return base * random.uniform(0.93, 1.07)   # 真实世界不是精确的


def weekday_factor(category: str, d: date) -> float:
    table = WEEKDAY_WEEKEND_HEAVY if category in WEEKEND_HEAVY_CATEGORIES else WEEKDAY_BASE
    base = table[d.weekday()]
    return base * random.uniform(0.94, 1.06)


def _step(p: dict, cur: date, st: dict, is_promo: bool,
          demand_mult: float = 1.0, reorder_scale: float = 1.0) -> tuple[dict, float, float]:
    """
    推进一个商品在一天内的经营过程：估需求 → 店主进货 → 成交 → 损耗 → 更新经验。
    返回 (当日记录, 缺货量, 损耗量)。

    reorder_scale：当天补货量的折扣。节前店主忙不过来、想"明天再补"时会上打折，
    这正是"偏偏最忙的一天出状况"的成因。
    """
    sku = p["sku"]
    sim = p["sim"]
    caution = OWNER_CAUTION.get(sku, DEFAULT_CAUTION)

    # ── 真实需求（上帝视角）──
    demand = sim["base_daily"]
    demand *= weekday_factor(p["category"], cur)
    demand *= season_factor(p["category"], cur)
    demand *= holiday_lift(p["category"], cur)
    if is_promo and p["category"] in PROMO_CATEGORIES:
        demand *= PROMO_LIFT
    demand *= random.uniform(0.85, 1.15)      # 日常噪声
    demand *= demand_mult
    demand = max(0.0, demand)

    # ── 店主进货决策（凭滞后经验 + 进货习惯，这是断货/积压的根源）──
    if st["day_index"] % CHECK_INTERVAL == 0:
        est = st["ema"]
        if st["inv"] < est * 1.7:             # 库存低于 1.7 天用量就补货
            need = est * 4.2 * caution * reorder_scale - st["inv"]
            if need > 0:
                qty = max(p["pack_size"], math.ceil(need / p["pack_size"]) * p["pack_size"])
                st["inv"] += qty

    # ── 当天的成交 ──
    sold = min(demand, st["inv"])
    stockout = max(0.0, demand - sold)
    st["inv"] -= sold

    # ── 损耗：短保过期 + 生鲜/冷饮滞销 ──
    spoil = 0.0
    perishable = p["category"] in PERISHABLE_CATEGORIES or p["shelf_life_days"] <= 30
    if st["inv"] > 0 and perishable:
        est = max(st["ema"], 0.3)
        if p["shelf_life_days"] <= 7:
            turnover_days = st["inv"] / est
            if turnover_days > p["shelf_life_days"]:
                spoil += (st["inv"] - est * p["shelf_life_days"]) * 0.55
        stale_days = 5 if p["category"] == "冷饮" else 12
        if st["inv"] > est * stale_days:
            spoil += (st["inv"] - est * stale_days) * (
                0.28 if p["category"] == "冷饮" else 0.20)
        spoil = min(spoil, st["inv"])
        if spoil > 0 and random.random() > 0.35:
            spoil = 0.0        # 不是每天盘点都能发现
        st["inv"] -= spoil

    # ── 店主更新心里那本账（滞后 EMA，反应慢）──
    observed = sold + stockout * 0.4        # 店主对缺货损失只有模糊感知
    st["ema"] = st["ema"] * 0.82 + observed * 0.18

    row = {
        "day": cur.strftime("%Y-%m-%d"),
        "sku": sku,
        "qty_sold": round(sold, 1),
        "qty_stockout": round(stockout, 1),
        "qty_spoilage": round(spoil, 1),
        "is_promo": int(is_promo and p["category"] in PROMO_CATEGORIES),
        "is_holiday": int(cur.strftime("%Y-%m-%d") in HOLIDAYS),
    }
    return row, stockout, spoil


def generate_history(days: int = 121, end_day: date | None = None,
                     seed: int = 42, db_path=None) -> dict:
    """
    生成门店历史经营轨迹并写入长期记忆库。

    关键机制 —— 客流联动（本项目"惠民价值"的数据基础）：
    民生商品是社区店的客流入口。当天的民生商品缺货越严重，进店客流越少，
    非民生商品（零食、饮料、酒水）的销量会同步下滑。这条规律被写进仿真世界，
    因此它能从历史数据中被统计出来 —— 而不是靠假设「民生商品重要」。
    """
    random.seed(seed)
    end_day = end_day or date(2026, 9, 24)
    start_day = end_day - timedelta(days=days - 1)

    memory.init_db(db_path)
    memory.reset_all(db_path)

    # 商品档案入库
    memory.upsert_products([{
        k: v for k, v in p.items() if k != "sim"
    } for p in PRODUCTS])

    # 初始策略参数 = 店主的原始经验值（这是进化的起点）
    for p in PRODUCTS:
        memory.set_policy(p["sku"], p["sim"]["init_base_days"], 0.15, db_path=db_path)

    # 运行状态
    state = {}
    for p in PRODUCTS:
        init_qty = p["sim"]["base_daily"] * p["sim"]["init_days"]
        state[p["sku"]] = {
            "inv": max(p["pack_size"], math.ceil(init_qty / p["pack_size"]) * p["pack_size"]),
            "ema": p["sim"]["base_daily"],
            "day_index": 0,
        }

    liv_products = [p for p in PRODUCTS if p["is_livelihood"]]
    non_liv_products = [p for p in PRODUCTS if not p["is_livelihood"]]

    all_rows: list[dict] = []
    stockout_events: list[tuple] = []
    spoilage_events: list[tuple] = []

    cur = start_day
    day_index = 0

    while cur <= end_day:
        is_promo = cur.day in PROMO_DAYS
        for p in PRODUCTS:
            state[p["sku"]]["day_index"] = day_index

        # 节前采购潮：临近中秋，街坊集中囤货。店主早上按滞后经验备货，
        # 白天却卖超了 —— 这正是"演示前夜突然出状况"的真实成因。
        if cur == end_day:
            pre_holiday = 1.52
        elif cur == end_day - timedelta(days=1):
            pre_holiday = 1.15
        else:
            pre_holiday = 1.0

        # ── 民生商品先行：它们的缺货会决定今天的客流 ──
        traffic_loss_raw = 0.0
        for p in liv_products:
            # 节前最忙的一天，几个"本来就进得少"的商品店主没顾上补货。
            # 偏偏这天街坊集中囤货 —— 事故就是这么发生的。
            rs = 0.0 if (cur == end_day
                         and OWNER_CAUTION.get(p["sku"], 1.0) < 0.9) else 1.0
            row, so, sp = _step(p, cur, state[p["sku"]], is_promo,
                                demand_mult=pre_holiday, reorder_scale=rs)
            all_rows.append(row)
            if so > 0.5:
                stockout_events.append((row["day"], p["sku"], round(so, 1)))
            if sp > 0.5:
                spoilage_events.append((row["day"], p["sku"], round(sp, 1)))
            potential = row["qty_sold"] + row["qty_stockout"]
            ratio = row["qty_stockout"] / potential if potential > 0 else 0.0
            traffic_loss_raw += ratio * p["traffic_pull"]

        # 客流损失折算：民生缺货越重，非民生越卖不动（上限 35%）
        traffic_loss = min(0.35, traffic_loss_raw * 0.12)
        demand_mult = pre_holiday * (1.0 - traffic_loss)

        # ── 非民生商品：承接打折后的客流 ──
        for p in non_liv_products:
            row, so, sp = _step(p, cur, state[p["sku"]], is_promo,
                                demand_mult=demand_mult)
            all_rows.append(row)
            if so > 0.5:
                stockout_events.append((row["day"], p["sku"], round(so, 1)))
            if sp > 0.5:
                spoilage_events.append((row["day"], p["sku"], round(sp, 1)))

        cur += timedelta(days=1)
        day_index += 1

    # 分批写入
    for i in range(0, len(all_rows), 500):
        memory.add_sales(all_rows[i:i + 500], db_path=db_path)

    # 当前库存 = 最后一天收盘状态
    memory.set_inventory_bulk(
        [(sku, round(st["inv"], 1)) for sku, st in state.items()], db_path=db_path
    )

    # 按商品汇总经营事故，便于校验仿真是否体现了预期剧情
    per_sku: dict[str, dict] = {}
    for _, sku, q in stockout_events:
        rec = per_sku.setdefault(sku, {"stockout_days": 0, "stockout_qty": 0.0,
                                       "spoil_days": 0, "spoil_qty": 0.0})
        rec["stockout_days"] += 1
        rec["stockout_qty"] += q
    for _, sku, q in spoilage_events:
        rec = per_sku.setdefault(sku, {"stockout_days": 0, "stockout_qty": 0.0,
                                       "spoil_days": 0, "spoil_qty": 0.0})
        rec["spoil_days"] += 1
        rec["spoil_qty"] += q

    return {
        "start": start_day.isoformat(),
        "end": end_day.isoformat(),
        "days": days,
        "records": len(all_rows),
        "stockout_events": len(stockout_events),
        "spoilage_events": len(spoilage_events),
        "per_sku": per_sku,
        "recent_stockouts": stockout_events[-8:],
    }


if __name__ == "__main__":
    info = generate_history()
    name_map = {p["sku"]: p["name"] for p in PRODUCTS}
    print("=" * 62)
    print("店脑 · 门店历史数据已生成")
    print("=" * 62)
    for k in ("start", "end", "days", "records", "stockout_events", "spoilage_events"):
        print(f"  {k}: {info[k]}")
    print("-" * 62)
    print("  按商品汇总（缺货 / 损耗）")
    print(f"  {'SKU':<5}{'商品':<18}{'缺货天数':>8}{'缺货量':>9}{'损耗天数':>9}{'损耗量':>8}")
    for sku, rec in sorted(info["per_sku"].items(),
                           key=lambda kv: -(kv[1]["stockout_qty"] + kv[1]["spoil_qty"])):
        print(f"  {sku:<5}{name_map.get(sku, sku):<18}"
              f"{rec['stockout_days']:>8}{rec['stockout_qty']:>9.0f}"
              f"{rec['spoil_days']:>9}{rec['spoil_qty']:>8.0f}")
    print("=" * 62)
