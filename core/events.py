# -*- coding: utf-8 -*-
"""
小满 · 历史事件分析与数据驱动的风险因子

店主的先验判断（勾选「高温 / 暴雨 / 节假日」）只是起点；更可信的做法是
翻历史账本，看这类事件当年真实地把销量抬/压了多少。本模块从记忆库里的
180 天经营事件里算出「事件日销量 ÷ 同星期几非事件日均值」的品类乘数，
供预测模块在店主勾选风险时使用 —— 数据驱动，而不是拍脑袋的固定系数。

事件键 ↔ CSV 事件名：
  rain  ↔ 暴雨       demand（分品类：冲动/易腐消费下降，囤货刚需上升）
  heat  ↔ 高温       demand（冷饮/饮料需求↑）
  holiday ↔ 节假日   demand（全品类备货↑）
  supplier ↔ 供应商D断供   supply（停止采购断供供应商商品，不乘预测）

注意：供应商断货是「供给侧」事件，不改变需求预测，因此不计算销量乘数，
只在策略层停止采购断供供应商商品；这里只提供历史断货日供 Agent 查询与解释。
"""

from collections import defaultdict
from datetime import date

from . import memory

EVENT_KEY_TO_LABEL = {
    "rain": "暴雨",
    "heat": "高温",
    "holiday": "节假日",
    "supplier": "供应商D断供",
}
LABEL_TO_EVENT_KEY = {v: k for k, v in EVENT_KEY_TO_LABEL.items()}

# 需求侧事件（会乘进销量预测）—— 供应商断货不在其中
DEMAND_EVENT_KEYS = ("rain", "heat", "holiday")

# 乘数夹紧区间：历史样本可能极端，做保守收口
MULT_MIN, MULT_MAX = 0.5, 1.8

# 事件乘数缓存：同一进程里只算一次（预测会逐商品调用，避免反复扫库）
_IMPACT_CACHE: dict[str, dict[str, dict[str, float]]] = {}

# 逐商品事件统计缓存：{event_key|db_path: {sku: {...}}}
_SKU_STATS_CACHE: dict[str, dict[str, dict]] = {}


def _wd(day_str: str) -> int:
    return date.fromisoformat(day_str).weekday()


def _cut(as_of) -> str | None:
    """把 as_of 规整成 'YYYY-MM-DD'；None 表示不设截止（全量历史）。"""
    return None if as_of is None else str(as_of)[:10]


def historical_event_days(event_key: str, as_of=None, db_path=None) -> list[str]:
    """返回某类事件发生过的所有日期（升序）。

    as_of：决策截止日。给定后仅返回 as_of 之前、且已有完成经营记录（有销售记录）
    的事件日，保证 Day t 决策读不到 Day t 及之后（含 CSV 里尚未发生的未来事件）。
    """
    label = EVENT_KEY_TO_LABEL.get(event_key)
    if not label:
        return []
    events = memory.get_day_events(db_path)
    days = [e["day"] for e in events if e["event"] == label]
    as_of_s = _cut(as_of)
    if as_of_s is not None:
        recorded = set(memory.available_days(db_path))
        days = [d for d in days if d < as_of_s and d in recorded]
    return days


def events_summary(as_of=None, db_path=None) -> dict[str, list[str]]:
    """全部历史事件：{事件键: [日期...]}，供 Agent 与界面查询。

    as_of：决策截止日；决策路径请传 plan_date，展示全量历史时可不传。
    """
    return {k: historical_event_days(k, as_of=as_of, db_path=db_path) for k in EVENT_KEY_TO_LABEL}


def day_info(day_str: str, db_path=None) -> dict:
    """某一天的天气 / 温度 / 事件信息。"""
    e = memory.get_day_event(day_str, db_path)
    return e or {"day": day_str, "weather": "", "temperature_c": None,
                 "event": "正常", "is_weekend": 0, "supplier_available": 1}


def event_impact(as_of=None, db_path=None) -> dict[str, dict[str, float]]:
    """
    数据驱动的需求侧事件乘数。

    返回 {event_key: {category: multiplier}}，其中
      multiplier = 事件日销量均值 ÷ 同星期几非事件日销量均值（按品类汇总）。

    as_of：决策截止日；给定后只用 as_of 之前已结算的销售与事件样本。

    做法：
      1. 逐 SKU 建立「星期几 → 非事件日销量列表」的基线；
      2. 每个事件日算 当日销量 ÷ 同星期几基线，得到该 SKU 当天的偏离；
      3. 同一品类下所有 SKU × 所有事件日 的偏离取平均，得到品类乘数；
      4. 夹紧到 [MULT_MIN, MULT_MAX]。
    """
    cache_key = f"{as_of}|{db_path or ''}"
    if cache_key in _IMPACT_CACHE:
        return _IMPACT_CACHE[cache_key]

    products = memory.get_products(db_path)
    all_days = memory.available_days(db_path)
    if not all_days:
        return {}

    as_of_s = _cut(as_of)
    days = all_days if as_of_s is None else [d for d in all_days if d < as_of_s]
    if not days:
        return {}

    sku_of = {p["sku"]: p for p in products}
    cat_of = {p["sku"]: p["category"] for p in products}

    # 逐 SKU 逐日的销量 + 是否事件日
    by_sku: dict[str, dict[str, float]] = defaultdict(dict)
    event_days: dict[str, dict[str, set[str]]] = {k: {} for k in DEMAND_EVENT_KEYS}

    for p in products:
        rows = memory.get_sales_range(p["sku"], days[0], days[-1], db_path)
        for r in rows:
            # 用潜在需求（销量 + 缺货量）还原事件日的真实需求，避免缺货压扁事件系数
            by_sku[p["sku"]][r["day"]] = r["qty_sold"] + r.get("qty_stockout", 0.0)

    # 事件日集合（按 SKU 无关，同一事件日所有 SKU 都算）
    event_day_sets: dict[str, set[str]] = {}
    for k in DEMAND_EVENT_KEYS:
        event_day_sets[k] = set(historical_event_days(k, as_of=as_of, db_path=db_path))

    # 逐 SKU、逐事件键：收集 (事件日偏离值) 列表
    # baseline[w] = 该 SKU 在星期 w 的非事件日均销量
    cat_ratios: dict[str, dict[str, list[float]]] = {
        k: defaultdict(list) for k in DEMAND_EVENT_KEYS
    }

    for sku, day_map in by_sku.items():
        cat = cat_of[sku]
        for k in DEMAND_EVENT_KEYS:
            ev_days = event_day_sets[k]
            # 同星期几非事件日基线
            base: dict[int, list[float]] = defaultdict(list)
            for d, v in day_map.items():
                if d in ev_days:
                    continue
                base[_wd(d)].append(v)
            base_avg = {w: (sum(vs) / len(vs)) for w, vs in base.items() if vs}
            ratios = []
            for d in sorted(ev_days):
                if d not in day_map:
                    continue
                b = base_avg.get(_wd(d))
                if b and b > 0:
                    ratios.append(day_map[d] / b)
            if ratios:
                cat_ratios[k][cat].extend(ratios)

    out: dict[str, dict[str, float]] = {}
    for k in DEMAND_EVENT_KEYS:
        out[k] = {}
        for cat, rs in cat_ratios[k].items():
            if rs:
                mult = sum(rs) / len(rs)
                out[k][cat] = max(MULT_MIN, min(MULT_MAX, mult))
    _IMPACT_CACHE[cache_key] = out
    return out


def sku_event_stats(event_key: str, as_of=None, db_path=None) -> dict[str, dict]:
    """
    逐商品的事件需求系数与原始均值（「普通日均 → 事件日均」）。

    返回 {sku: {"normal_avg": 普通日均销量, "event_avg": 事件日均销量,
                "multiplier": 需求系数, "event_days": 事件日样本数,
                "normal_days": 普通日样本数}}
      multiplier = event_avg ÷ normal_avg，夹紧到 [MULT_MIN, MULT_MAX]。

    as_of：决策截止日；给定后只用 as_of 之前已结算的销售与事件样本。

    与 event_impact() 的品类口径不同，这里是**每个商品各自**的历史表现 ——
    矿泉水、可乐、鸡蛋在高温下会得到各自不同的系数，而不是共享一个品类系数。
    """
    key = f"{event_key}|{as_of}|{db_path or ''}"
    if key in _SKU_STATS_CACHE:
        return _SKU_STATS_CACHE[key]

    out: dict[str, dict] = {}
    ev_days = set(historical_event_days(event_key, as_of=as_of, db_path=db_path))
    if not ev_days:
        _SKU_STATS_CACHE[key] = out
        return out

    products = memory.get_products(db_path)
    all_days = memory.available_days(db_path)
    if not all_days:
        _SKU_STATS_CACHE[key] = out
        return out

    as_of_s = _cut(as_of)
    days = all_days if as_of_s is None else [d for d in all_days if d < as_of_s]
    if not days:
        _SKU_STATS_CACHE[key] = out
        return out

    for p in products:
        rows = memory.get_sales_range(p["sku"], days[0], days[-1], db_path)
        # 用「潜在需求 = 销量 + 缺货量」而非记录销量：事件日若因缺货被压扁，
        # 用销量会低估事件系数，与预测模块的"潜在需求还原"原则不一致。
        normal = [r["qty_sold"] + r.get("qty_stockout", 0.0)
                  for r in rows if r["day"] not in ev_days]
        event = [r["qty_sold"] + r.get("qty_stockout", 0.0)
                 for r in rows if r["day"] in ev_days]
        if not normal or not event:
            continue
        normal_avg = sum(normal) / len(normal)
        event_avg = sum(event) / len(event)
        if normal_avg <= 0:
            continue
        mult = max(MULT_MIN, min(MULT_MAX, event_avg / normal_avg))
        out[p["sku"]] = {
            "normal_avg": round(normal_avg, 2),
            "event_avg": round(event_avg, 2),
            "multiplier": round(mult, 4),
            "event_days": len(event),
            "normal_days": len(normal),
        }
    _SKU_STATS_CACHE[key] = out
    return out


def event_impact_by_sku(as_of=None, db_path=None) -> dict[str, dict[str, float]]:
    """需求侧事件逐商品乘数：{event_key: {sku: multiplier}}。"""
    return {
        k: {sku: s["multiplier"]
            for sku, s in sku_event_stats(k, as_of=as_of, db_path=db_path).items()}
        for k in DEMAND_EVENT_KEYS
    }


def clear_impact_cache() -> None:
    """数据重新导入后，调用它让乘数缓存失效。"""
    _IMPACT_CACHE.clear()
    _SKU_STATS_CACHE.clear()


def event_impact_table(as_of=None, db_path=None) -> list[dict]:
    """把乘数整理成界面可展示的品类表（高温 / 暴雨 / 节假日）。"""
    impact = event_impact(as_of=as_of, db_path=db_path)
    cats = sorted({p["category"] for p in memory.get_products(db_path)})
    rows = []
    for cat in cats:
        rows.append({
            "category": cat,
            "heat": impact.get("heat", {}).get(cat),
            "rain": impact.get("rain", {}).get(cat),
            "holiday": impact.get("holiday", {}).get(cat),
        })
    return rows


def effective_factors(event_key: str, fallback: dict[str, float],
                      fallback_default: float, as_of=None, db_path=None) -> dict[str, float]:
    """
    返回某事件键的「数据驱动品类乘数」，数据缺失的品类回退到先验系数。

    这是预测模块真正要调用的入口：既有数据可信度，又保留兜底。
    """
    data = event_impact(as_of=as_of, db_path=db_path).get(event_key, {})
    merged = dict(fallback)
    merged.update(data)
    return merged, data


def risk_event_context(active_events: list[str], as_of=None, db_path=None) -> str:
    """
    把店主勾选的风险与历史事件对上号，生成一段「Agent 读到了什么历史」的说明。
    例如：勾选高温 → 找到 2026-05-15~19、07-14~18 两段高温，饮料销量平均 ×1.3。
    """
    lines = []
    for k in active_events:
        if k not in EVENT_KEY_TO_LABEL:
            continue
        days = historical_event_days(k, as_of=as_of, db_path=db_path)
        label = EVENT_KEY_TO_LABEL[k]
        if not days:
            lines.append(f"· {label}：历史里没有记录到这类事件，按先验经验处理。")
            continue
        span = f"{days[0]} ~ {days[-1]}" if len(days) > 1 else days[0]
        lines.append(f"· {label}：历史发生 {len(days)} 天（{span}）。")
    return "\n".join(lines)
