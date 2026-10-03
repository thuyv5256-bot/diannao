# -*- coding: utf-8 -*-
# 小满 · 全项目唯一指标口径（single source of truth）。
# 单日决策 / 180天 Digital Store / 消融 / R³ vs Traditional / 离线评测
# 一律调用本模块，禁止各自重算。单位：件数=件，金额=元，比率=0~1 小数。
# 所有除法在分母<=0 时安全返回 0.0。

def _div(num, den):
    return (num / den) if den and den > 0 else 0.0


def stockout_rate(stockout_qty, demand_qty):
    """缺货率 = 未满足需求件数 / 实际需求件数。"""
    return _div(stockout_qty, demand_qty)


def fill_rate(sold_qty, demand_qty):
    """需求满足率 = 实际销售件数 / 实际需求件数。"""
    return _div(sold_qty, demand_qty)


def livelihood_stockout_rate(liv_stockout_qty, liv_demand_qty):
    """民生商品缺货率 = 民生未满足需求件数 / 民生实际需求件数。"""
    return _div(liv_stockout_qty, liv_demand_qty)


def livelihood_fill_rate(liv_sold_qty, liv_demand_qty):
    """民生商品需求满足率 = 民生实际销售件数 / 民生实际需求件数。"""
    return _div(liv_sold_qty, liv_demand_qty)


def spoilage_rate(spoil_qty, sold_qty):
    """损耗率 = 过期报损件数 / 可供销售总件数（= 实际销量 + 报损量）。"""
    return _div(spoil_qty, (sold_qty or 0.0) + (spoil_qty or 0.0))


def spoilage_cost(spoil_qty, cost_price):
    """损耗成本（元）= Σ(报损件数 × 商品成本价)。"""
    return float(spoil_qty or 0.0) * float(cost_price or 0.0)


def gross_margin(sold_qty, unit_margin, spoil_qty, cost_price):
    """实现毛利（元）= 销量×单件毛利 − 报损件数×成本价。"""
    return float(sold_qty or 0.0) * float(unit_margin or 0.0) - spoilage_cost(spoil_qty, cost_price)


def inventory_value(qty, cost_price):
    """库存成本金额（元）= 库存件数 × 成本价（口径：成本价，非售价）。"""
    return float(qty or 0.0) * float(cost_price or 0.0)


def avg_inventory_capital(daily_closing_values):
    """平均库存资金占用（元）= 每日期末库存成本金额的平均值。"""
    vals = list(daily_closing_values)
    return (sum(vals) / len(vals)) if vals else 0.0


def inventory_turnover(cogs, avg_inventory_capital_value):
    """库存周转率（次）= 销售成本(COGS) / 平均库存资金占用。"""
    return _div(cogs, avg_inventory_capital_value)


def livelihood_secured_rate(secured_count, total_count):
    """民生最低保障达标率（决策阶段）= 达标民生SKU数 / 全部民生SKU数。

    注意：这是「本次补货是否达到最低保障补货量 floor_qty」的**决策**指标，
    与「民生商品需求满足率/缺货率」（实际经营结果）是两个不同指标，不可混用。
    """
    return _div(secured_count, total_count) if total_count else 1.0


def expected_stockout_rate(shortfall_qty, horizon_need_qty):
    """预计缺货率（决策阶段，单日页面）= 预计缺口件数 / 目标覆盖期预计需求件数。

    仅用于「补货方案是否够覆盖下一周期」的前瞻评估，不是实际缺货率；
    实际缺货率请用 stockout_rate。命名区分以防两口径混淆。
    """
    return _div(shortfall_qty, horizon_need_qty)


def expected_spoilage_cost(over_qty, cost_price):
    """预计损耗成本（决策阶段）= 预计超额件数 × 成本价（短保商品前瞻评估用）。"""
    return spoilage_cost(over_qty, cost_price)
