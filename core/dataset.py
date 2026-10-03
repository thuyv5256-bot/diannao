# -*- coding: utf-8 -*-
"""
小满 · 经营数据集接入层（社区小店数字经营仿真数据）

数据来源：data/shopmind_products_50sku.csv（50 种商品基础配置）
          data/shopmind_180days_50sku.csv（180 天 × 50 种商品的经营仿真数据）

这两份数据属于「社区小店数字经营仿真数据」，用于演示补货决策与策略自进化，
**不是现实门店的采集数据**。本模块只负责读取、清洗并导入长期记忆库，
不参与任何随机销量生成 —— 页面里看到的历史销量全部来自 CSV。

CSV 字段映射到小满记忆库：
  products.csv
    item_id → sku；product_name → name；category → category；
    price → sell_price；cost → cost_price；essential → is_livelihood；
    shelf_life_days → shelf_life_days；supplier → supplier；
    lead_time_days → lead_time_days；base_daily_demand → base_daily_demand
  （unit / pack_size / traffic_pull 是 CSV 里没有的字段，由本模块按品类做
    确定性的业务推断，绝不随机生成。）

  180days.csv
    date → day；item_id → sku；sales → qty_sold；
    weather / temperature_c / event / is_weekend / supplier_available
        → 每日经营事件表（day_events）。
    CSV 只记录了「实际销量」，没有断货量 / 损耗量，因此导入时 qty_stockout /
    qty_spoilage 均记为 0 —— 这类反馈由店主在「今天生意怎么样」里单独录入。
"""

import csv
import math
from datetime import date
from pathlib import Path

from . import memory
from .config import DATA_DIR

PRODUCTS_CSV = DATA_DIR / "shopmind_products_50sku.csv"
SALES_CSV = DATA_DIR / "shopmind_180days_50sku.csv"

# ── CSV 未提供字段的确定性推断 ──────────────────────────────
# 单位：按商品名给一个自然的销售单位（只用于界面展示）。
UNIT_BY_SKU = {
    "P001": "瓶", "P002": "桶", "P003": "瓶", "P004": "瓶", "P005": "瓶",
    "P006": "盒", "P007": "盒", "P008": "盒",
    "P009": "袋", "P010": "桶", "P011": "袋", "P012": "袋",
    "P013": "袋", "P014": "瓶", "P015": "瓶",
    "P016": "包", "P017": "包", "P018": "根", "P019": "罐", "P020": "包",
    "P021": "个", "P022": "个",
    "P023": "盒", "P024": "包", "P025": "袋", "P026": "袋",
    "P027": "块", "P028": "支",
    "P029": "支", "P030": "支",
    "P031": "包", "P032": "提", "P033": "瓶", "P034": "瓶", "P035": "支",
    "P036": "支", "P037": "块", "P038": "卷", "P039": "节", "P040": "个",
    "P041": "斤", "P042": "斤", "P043": "斤",
    "P044": "斤", "P045": "斤", "P046": "斤",
    "P047": "袋", "P048": "袋", "P049": "包", "P050": "盒",
}

# 客流带动系数：该商品缺货会在多大程度上流失客流。
# CSV 没有这个字段，按品类做业务推断（民生粮油 / 生鲜 / 蔬菜带动最强）。
TRAFFIC_PULL_BY_CATEGORY = {
    "粮油": 1.8, "生鲜": 1.7, "蔬菜": 1.7, "乳品": 1.6, "饮料": 1.5,
    "方便食品": 1.4, "调味": 1.3, "日用品": 1.3, "应急用品": 1.2,
    "水果": 1.0, "烘焙": 1.0, "零食": 0.9, "冷饮": 0.8, "冷冻食品": 0.9,
}

# 初始库存 = 基础日均需求 × 该倍数（CSV 没有库存字段，按配置需求确定性推算）
INIT_INVENTORY_DAYS = 3.0


def _f(v, default=0.0):
    """把 CSV 字符串安全转成 float。"""
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return default


def _i(v, default=0):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return default


def read_products() -> list[dict]:
    """读取商品配置 CSV，映射为小满商品档案。"""
    out = []
    with open(PRODUCTS_CSV, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            sku = r["item_id"].strip()
            category = r["category"].strip()
            out.append({
                "sku": sku,
                "name": r["product_name"].strip(),
                "category": category,
                "unit": UNIT_BY_SKU.get(sku, "件"),
                "cost_price": _f(r["cost"]),
                "sell_price": _f(r["price"]),
                "is_livelihood": _i(r["essential"]),
                "shelf_life_days": _i(r["shelf_life_days"], 365),
                "pack_size": 1,
                "traffic_pull": TRAFFIC_PULL_BY_CATEGORY.get(category, 1.0),
                "supplier": r["supplier"].strip(),
                "lead_time_days": _i(r["lead_time_days"], 1),
                "base_daily_demand": _f(r["base_daily_demand"]),
            })
    return out


def read_sales() -> tuple[list[dict], list[dict]]:
    """
    读取 180 天经营仿真 CSV。

    返回 (sales_rows, day_events)：
      sales_rows   每行 = {day, sku, qty_sold, qty_stockout, qty_spoilage,
                           is_promo, is_holiday}
      day_events   每日一行 = {day, weather, temperature_c, event,
                              is_weekend, supplier_available}
    """
    sales_rows: list[dict] = []
    day_events: dict[str, dict] = {}
    with open(SALES_CSV, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            day = r["date"].strip()
            sku = r["item_id"].strip()
            event = r["event"].strip()

            sales_rows.append({
                "day": day,
                "sku": sku,
                "qty_sold": _f(r["sales"]),
                "qty_stockout": 0.0,   # CSV 未记录，反馈由店主单独录入
                "qty_spoilage": 0.0,   # 同上
                "is_promo": 0,
                "is_holiday": 1 if event == "节假日" else 0,
            })

            day_events.setdefault(day, {
                "day": day,
                "weather": r["weather"].strip(),
                "temperature_c": _f(r["temperature_c"]),
                "event": event,
                "is_weekend": _i(r["is_weekend"]),
                "supplier_available": _i(r["supplier_available"], 1),
            })

    events = [day_events[d] for d in sorted(day_events)]
    return sales_rows, events


def import_dataset(db_path=None) -> dict:
    """
    把两份 CSV 导入长期记忆库（清空后重建）。

    这是「数据源替换」的唯一入口：seed_data.py / app.py 首次启动都走这里，
    不再随机生成销量。
    """
    products = read_products()
    sales_rows, day_events = read_sales()

    memory.init_db(db_path)
    memory.reset_all(db_path)

    # 商品档案
    memory.upsert_products(products, db_path)

    # 初始策略参数：全部从同一个温和起点出发（进化的起点）
    for p in products:
        base_days = 4.0 if p["is_livelihood"] else 3.0
        memory.set_policy(p["sku"], base_days, 0.15, db_path=db_path)

    # 每日经营事件
    memory.upsert_day_events(day_events, db_path)

    # 历史销量
    for i in range(0, len(sales_rows), 500):
        memory.add_sales(sales_rows[i:i + 500], db_path=db_path)

    # 当前库存 = 基础日均需求 × 3 天（确定性推算，非随机）
    memory.set_inventory_bulk(
        [(p["sku"], math.ceil(p["base_daily_demand"] * INIT_INVENTORY_DAYS))
         for p in products],
        db_path=db_path,
    )

    return {
        "products": len(products),
        "records": len(sales_rows),
        "days": len(day_events),
        "start": day_events[0]["day"] if day_events else "",
        "end": day_events[-1]["day"] if day_events else "",
    }


def available_date_range(db_path=None) -> tuple[str, str]:
    days = memory.available_days(db_path)
    return (days[0], days[-1]) if days else ("", "")


if __name__ == "__main__":
    info = import_dataset()
    print("小满 · CSV 经营数据已导入")
    for k, v in info.items():
        print(f"  {k}: {v}")
    print(f"  民生商品数: {sum(1 for p in memory.get_products() if p['is_livelihood'])}")
