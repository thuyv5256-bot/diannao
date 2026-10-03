# -*- coding: utf-8 -*-
"""
小满 · 门店经营数据入口（从 CSV 接入）

历史经营数据不再随机生成，而是直接读取两份「社区小店数字经营仿真数据」：

  · data/shopmind_products_50sku.csv    50 种商品的基础配置
  · data/shopmind_180days_50sku.csv     180 天 × 50 种商品的经营仿真数据

这两份数据属于社区小店数字经营仿真数据，**不是现实门店的采集数据**。
CSV 里记录了每天每种商品的实际销量，以及当天的天气 / 温度 / 事件
（高温 / 暴雨 / 节假日 / 供应商断货）与供应商到货状态。

本模块是「数据源替换」的唯一入口：app.py 首次启动、demo_flow.py、eval.py
都调用 generate_history() 把 CSV 导入长期记忆库，之后再无随机销量。

数据清洗与字段映射见 core/dataset.py。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from core import dataset, memory
else:
    from .core import dataset, memory


def generate_history(days: int | None = None, end_day=None, seed: int | None = None,
                     db_path=None) -> dict:
    """
    把 CSV 经营数据导入长期记忆库（清空后重建）。

    参数 days / end_day / seed 仅为兼容旧调用签名而保留，不再影响数据内容：
    历史销量一律来自 CSV（180 天），不随机生成。
    """
    info = dataset.import_dataset(db_path)
    return {
        "start": info["start"],
        "end": info["end"],
        "days": info["days"],
        "records": info["records"],
        "stockout_events": 0,   # CSV 未记录断货量，反馈由店主单独录入
        "spoilage_events": 0,   # 同上
        "per_sku": {},
        "recent_stockouts": [],
    }


if __name__ == "__main__":
    info = generate_history()
    print("=" * 62)
    print("小满 · 门店经营数据已从 CSV 导入")
    print("=" * 62)
    for k in ("start", "end", "days", "records"):
        print(f"  {k}: {info[k]}")
    prods = memory.get_products()
    print(f"  商品数: {len(prods)}，民生商品数: "
          f"{sum(1 for p in prods if p['is_livelihood'])}")
    from core.events import events_summary
    for k, ds in events_summary().items():
        print(f"  历史事件 [{k}]: {len(ds)} 天")
    print("=" * 62)
