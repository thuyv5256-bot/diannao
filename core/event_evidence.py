# -*- coding: utf-8 -*-
"""
小满 · 事件证据门控（Event Evidence Gate）

把旧版「检测到事件 → 直接乘一个固定倍率（数据缺失时回退人工先验）」升级为
「检测到事件 → 查历史证据 → 评估可信度 → 门控是否进入预测」。

证据等级（每个 event × SKU/品类各算一份）：
  Strong        历史证据充分且方向稳定 → 允许事件调整 Forecast；
  Weak          有信号但样本不足 / 方向不稳 / 效应太小 → 保持基础 Forecast，仅记风险提示；
  Insufficient  样本极少 / 首次出现 / 无可比基线 → 保持基础 Forecast，仅记风险提示。

统计口径（保守、通用，不针对本数据集反推任何阈值，也不保证任何策略"赢"）：
  · 事件日样本 = 该事件历史发生且已有销售记录的天数（只看「今天以前」的销售）；
  · 可比普通日 = 事件为「正常」、与事件日同星期几、且落在事件日前后 ±45 天内
    —— 控制「同 SKU/品类、相近星期、相近季节」，并剔除其它事件日的污染；
  · 需求口径 = 潜在需求（销量 + 缺货量），与预测模块的「断货还原」一致；
  · uplift = mean(事件日需求 ÷ 对应星期几可比普通日均值)；
  · 置信区间 = log 空间双尾 t 区间（Bessel 校正样本标准差，t 分位数取保守常数）。

供应商断供是「供给侧」事件，不经过需求 uplift 门控 —— 仍由 Supplier Tool
停采断供供应商 + 结算层环境强制拦截（core.simulator._enforce_supplier_outage）。
"""

import math
from datetime import date

from . import events, memory
from .config import (
    EVIDENCE_CI_T_CRIT,
    EVIDENCE_MIN_BASE_SAMPLES,
    EVIDENCE_MIN_CONSISTENCY,
    EVIDENCE_MIN_EVENT_SAMPLES,
    EVIDENCE_MIN_UPLIFT_DELTA,
    EVIDENCE_SEASON_WINDOW_DAYS,
)

LEVEL_STRONG = "strong"
LEVEL_WEAK = "weak"
LEVEL_INSUFFICIENT = "insufficient"

# 需求侧事件（会乘进销量预测）；供应商断供属供给侧，不走本门控
DEMAND_KEYS = events.DEMAND_EVENT_KEYS

# 应用时的乘数夹紧（复用 events 的保守收口，防止极值过度反应）
_MULT_MIN = events.MULT_MIN
_MULT_MAX = events.MULT_MAX

# 证据缓存：{f"{event_key}|{resolved_db_path}": {"sku": {...}, "category": {...}}}
_CACHE: dict[str, dict] = {}


def clear_cache() -> None:
    """数据变化后调用，使证据缓存失效（与 events.clear_impact_cache 同节奏）。"""
    _CACHE.clear()


def _wd(day: str) -> int:
    return date.fromisoformat(day).weekday()


def _classify(uplifts: list[float], n_event: int, n_base: int,
              event_mean: float, baseline_mean: float,
              total_event_days: int) -> dict:
    """根据逐事件日 uplift 样本判定证据等级。"""
    n = len(uplifts)
    mean_u = sum(uplifts) / n

    # 方向一致性：与总体 uplift 同向的事件日占比
    if mean_u >= 1.0:
        same = sum(1 for u in uplifts if u >= 1.0)
    else:
        same = sum(1 for u in uplifts if u < 1.0)
    consistency = same / n

    # log 空间双尾 t 区间（Bessel 校正样本标准差）
    logs = [math.log(u) for u in uplifts if u > 0]
    if len(logs) >= 2:
        m = sum(logs) / len(logs)
        var = sum((x - m) ** 2 for x in logs) / (len(logs) - 1)
        se = math.sqrt(var / len(logs))
        half = EVIDENCE_CI_T_CRIT * se
        ci_low = math.exp(m - half)
        ci_high = math.exp(m + half)
    else:
        ci_low = ci_high = mean_u

    if n < EVIDENCE_MIN_EVENT_SAMPLES or n_base < EVIDENCE_MIN_BASE_SAMPLES:
        level = LEVEL_INSUFFICIENT
        reason = (f"历史有效样本不足（事件日 {n} 天 / 可比普通日 {n_base} 天，"
                  f"未达 {EVIDENCE_MIN_EVENT_SAMPLES}/{EVIDENCE_MIN_BASE_SAMPLES} 门槛）")
    elif abs(mean_u - 1.0) < EVIDENCE_MIN_UPLIFT_DELTA:
        level = LEVEL_WEAK
        reason = (f"需求偏移仅 {mean_u - 1.0:+.1%}，"
                  f"小于 {EVIDENCE_MIN_UPLIFT_DELTA:.0%} 门槛，不足以可靠调整")
    elif consistency < EVIDENCE_MIN_CONSISTENCY:
        level = LEVEL_WEAK
        reason = (f"需求方向不稳定（仅 {consistency:.0%} 事件日同向，"
                  f"低于 {EVIDENCE_MIN_CONSISTENCY:.0%}）")
    elif ci_low < 1.0 < ci_high:
        level = LEVEL_WEAK
        reason = f"置信区间 [{ci_low:.2f}, {ci_high:.2f}] 跨越 1.0，不能确认存在真实偏移"
    else:
        level = LEVEL_STRONG
        reason = f"历史证据充分且方向稳定（{consistency:.0%} 事件日同向，置信区间不含 1.0）"

    return {
        "sample_count": n,
        "total_event_days": total_event_days,
        "baseline_count": n_base,
        "event_mean": round(event_mean, 2),
        "baseline_mean": round(baseline_mean, 2),
        "uplift": round(mean_u, 4),
        "direction_consistency": round(consistency, 4),
        "ci_low": round(ci_low, 4),
        "ci_high": round(ci_high, 4),
        "evidence_level": level,
        "apply_to_forecast": level == LEVEL_STRONG,
        "reason": reason,
    }


def _assess_unit(day_value: dict[str, float], ev_infos, normal_infos,
                 window: int, total_event_days: int) -> dict | None:
    """对一个需求单元（SKU 或品类）评估事件证据；无可比基线时返回 None。"""
    uplifts = []
    event_vals = []
    base_vals_all = []
    for d, wd, dt in ev_infos:
        x = day_value.get(d)
        if x is None:
            continue
        bvals = []
        for dn, wdn, dtn in normal_infos:
            if wdn == wd and abs((dtn - dt).days) <= window:
                v = day_value.get(dn)
                if v is not None:
                    bvals.append(v)
        if not bvals:
            continue
        b = sum(bvals) / len(bvals)
        if b <= 0:
            continue
        uplifts.append(x / b)
        event_vals.append(x)
        base_vals_all.extend(bvals)

    if not uplifts:
        return None
    n_event = len(uplifts)
    n_base = len(base_vals_all)
    event_mean = sum(event_vals) / n_event
    baseline_mean = sum(base_vals_all) / n_base
    return _classify(uplifts, n_event, n_base, event_mean, baseline_mean,
                     total_event_days)


def _compute(event_key: str, as_of=None, db_path=None) -> dict:
    """计算某需求侧事件的逐 SKU / 逐品类证据。返回 {"sku": {...}, "category": {...}}。

    as_of：决策截止日。给定后只统计 as_of 之前（不含当天）已结算的销售记录，
    保证 Day t 的预测读不到 Day t 及之后的结果（含尚未发生的未来事件）。
    """
    empty = {"sku": {}, "category": {}}
    label = events.EVENT_KEY_TO_LABEL.get(event_key)
    if not label:
        return empty

    products = memory.get_products(db_path)
    all_days = memory.available_days(db_path)
    if not products or not all_days:
        return empty

    if as_of is None:
        days = all_days
    else:
        as_of_s = str(as_of)[:10]
        days = [d for d in all_days if d < as_of_s]
    if not days:
        return empty

    day_event = {e["day"]: e["event"] for e in memory.get_day_events(db_path)}

    ev_days = sorted(d for d in days if day_event.get(d) == label)
    normal_days = sorted(d for d in days if day_event.get(d, "正常") == "正常")
    if not ev_days:
        return empty

    window = EVIDENCE_SEASON_WINDOW_DAYS
    ev_infos = [(d, _wd(d), date.fromisoformat(d)) for d in ev_days]
    normal_infos = [(d, _wd(d), date.fromisoformat(d)) for d in normal_days]
    total_event_days = len(ev_days)

    # 逐 SKU 需求序列，同时池化到品类
    sku_day_value: dict[str, dict[str, float]] = {}
    cat_day_value: dict[str, dict[str, float]] = {}
    for p in products:
        sku = p["sku"]
        rows = memory.get_sales_range(sku, days[0], days[-1], db_path)
        dv = {r["day"]: r["qty_sold"] + r.get("qty_stockout", 0.0) for r in rows}
        sku_day_value[sku] = dv
        acc = cat_day_value.setdefault(p["category"], {})
        for d, v in dv.items():
            acc[d] = acc.get(d, 0.0) + v

    sku_out: dict[str, dict] = {}
    for sku, dv in sku_day_value.items():
        rec = _assess_unit(dv, ev_infos, normal_infos, window, total_event_days)
        if rec is not None:
            rec["scope"] = "sku"
            rec["key"] = sku
            sku_out[sku] = rec

    cat_out: dict[str, dict] = {}
    for cat, dv in cat_day_value.items():
        rec = _assess_unit(dv, ev_infos, normal_infos, window, total_event_days)
        if rec is not None:
            rec["scope"] = "category"
            rec["key"] = cat
            cat_out[cat] = rec

    return {"sku": sku_out, "category": cat_out}


def _get(event_key: str, as_of=None, db_path=None) -> dict:
    resolved = str(db_path) if db_path else str(memory.DB_PATH)
    key = f"{event_key}|{as_of}|{resolved}"
    if key not in _CACHE:
        _CACHE[key] = _compute(event_key, as_of=as_of, db_path=db_path)
    return _CACHE[key]


def sku_evidence(event_key: str, as_of=None, db_path=None) -> dict[str, dict]:
    """某事件逐 SKU 的证据：{sku: EvidenceRecord}。"""
    return _get(event_key, as_of=as_of, db_path=db_path)["sku"]


def category_evidence(event_key: str, as_of=None, db_path=None) -> dict[str, dict]:
    """某事件逐品类的证据：{category: EvidenceRecord}。"""
    return _get(event_key, as_of=as_of, db_path=db_path)["category"]


def _no_evidence(event_key: str, product: dict) -> dict:
    label = events.EVENT_KEY_TO_LABEL.get(event_key, event_key)
    return {
        "scope": "sku",
        "key": product.get("sku"),
        "sample_count": 0,
        "total_event_days": 0,
        "baseline_count": 0,
        "event_mean": 0.0,
        "baseline_mean": 0.0,
        "uplift": 1.0,
        "direction_consistency": 0.0,
        "ci_low": 1.0,
        "ci_high": 1.0,
        "evidence_level": LEVEL_INSUFFICIENT,
        "apply_to_forecast": False,
        "reason": f"检测到{label}，但历史无同类事件记录",
    }


def evaluate_product(event_key: str, product: dict, as_of=None, db_path=None) -> dict:
    """评估某商品在指定事件下的证据，返回实际采用的证据记录。

    层级：SKU 级 Strong → 采用 SKU 级；否则品类级 Strong → 采用品类级；
    都不是 Strong → 返回最接近可解释的记录（apply_to_forecast=False）。

    as_of：决策截止日，只统计 as_of 之前的历史样本（防止时间穿越）。
    """
    data = _get(event_key, as_of=as_of, db_path=db_path)
    sku_rec = data["sku"].get(product.get("sku"))
    cat_rec = data["category"].get(product.get("category"))

    if sku_rec and sku_rec["evidence_level"] == LEVEL_STRONG:
        return sku_rec
    if cat_rec and cat_rec["evidence_level"] == LEVEL_STRONG:
        return cat_rec
    rec = sku_rec or cat_rec
    if rec is not None:
        return rec
    return _no_evidence(event_key, product)


def trace_entries(active_events, as_of=None, db_path=None) -> list[dict]:
    """为 Agent Decision Trace 生成每个需求侧事件的可信度摘要（品类级）。"""
    entries = []
    for k in active_events:
        if k not in DEMAND_KEYS:
            continue
        data = _get(k, as_of=as_of, db_path=db_path)
        label = events.EVENT_KEY_TO_LABEL.get(k, k)
        cats = data["category"]
        strong = [c for c, r in cats.items() if r["evidence_level"] == LEVEL_STRONG]
        weak = [c for c, r in cats.items() if r["evidence_level"] == LEVEL_WEAK]
        insuf = [c for c, r in cats.items() if r["evidence_level"] == LEVEL_INSUFFICIENT]
        total_days = next((r["total_event_days"] for r in cats.values()), 0)
        entries.append({
            "event_key": k,
            "label": label,
            "total_event_days": total_days,
            "strong_categories": strong,
            "weak_categories": weak,
            "insufficient_categories": insuf,
            "has_data": bool(cats),
            "apply": bool(strong),
        })
    return entries
