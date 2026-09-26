# -*- coding: utf-8 -*-
"""店脑 · 全局配置与业务常量"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "store_memory.db"

APP_NAME = "店脑"
APP_SLOGAN = "社区夫妻小店的智能补货决策 Agent"

# ── 经营默认参数 ──────────────────────────────────────────
DEFAULT_BUDGET = 600.0      # 店主每次进货的预算上限（元）
CURRENCY = "¥"

# ── 创新点 1：惠民约束 ────────────────────────────────────
# 民生商品即使毛利低，也必须保证的最低覆盖天数。
# 这是"不逐利砍便民货品"的技术落地形式。
LIVELIHOOD_MIN_COVER_DAYS = 3.0
# 预算极端不足时，民生底线至少保到该比例（宁可少进高毛利货）
LIVELIHOOD_FLOOR_RATIO = 0.85

# ── 创新点 2：自进化边界（防震荡） ────────────────────────
SAFETY_FACTOR_MIN = 0.05
SAFETY_FACTOR_MAX = 0.60
BASE_DAYS_MIN = 2.0
BASE_DAYS_MAX = 12.0
LIVELIHOOD_BASE_DAYS_MIN = 4.0   # 民生商品备货天数下限更高
EVOLVE_UP_STEP = 0.06            # 断货 → 上调安全系数步长
EVOLVE_DOWN_STEP = 0.04          # 积压损耗 → 下调步长
EVOLVE_UP_MAX_MULT = 2.5         # 单次上调的严重程度上限倍数
STOCKOUT_TRIGGER = 0.15          # 缺货率超过该阈值触发进化
SPOILAGE_TRIGGER = 0.10          # 损耗率超过该阈值触发进化

# ── 预测参数 ──────────────────────────────────────────────
LOOKBACK_DAYS = 28               # 预测回看窗口
DECAY_ALPHA = 0.06               # 指数衰减系数（近期权重更高）

# ── 节日日历（日期 → 节日名）──────────────────────────────
# 节日因子按品类配置，写在 forecast.py 里
HOLIDAYS = {
    "2026-05-30": "周末",
    "2026-06-01": "儿童节",
    "2026-06-19": "端午节",
    "2026-06-20": "端午节假期",
    "2026-06-21": "端午节假期",
    "2026-09-01": "开学季",
    "2026-09-25": "中秋节",
    "2026-09-26": "中秋节假期",
    "2026-09-27": "中秋节假期",
    "2026-10-01": "国庆节",
    "2026-10-02": "国庆假期",
    "2026-10-03": "国庆假期",
}

# ── 界面配色 ──────────────────────────────────────────────
COLOR_LIVELIHOOD = "#c0392b"     # 民生商品标记色（红，公益感）
COLOR_PROFIT = "#2c7a4b"         # 高毛利商品标记色
