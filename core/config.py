# -*- coding: utf-8 -*-
"""小满 · 全局配置与业务常量"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path=None) -> None:
    """极简 .env 加载器（避免额外依赖 python-dotenv）。

    只做最朴素的 KEY=VALUE 解析，支持 # 注释与引号；已存在的环境变量优先，
    不会覆盖用户在 shell 里显式设置的值。
    """
    env_file = path or (BASE_DIR / ".env")
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        os.environ.setdefault(k, v)


_load_dotenv()

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "store_memory.db"

APP_NAME = "小满"
APP_SUBTITLE = "面向社区小店的自进化智能补货 Agent"
APP_SLOGAN = "货架不空，库存不满，让每一次进货都恰到好处。"

# ── 经营默认参数 ──────────────────────────────────────────
DEFAULT_BUDGET = 600.0      # 店主每次进货的预算上限（元）
CURRENCY = "¥"

# ── 创新点 1：惠民约束 ────────────────────────────────────
# 民生商品即使毛利低，也必须保证的最低覆盖天数。
# 这是"不逐利砍便民货品"的技术落地形式。
LIVELIHOOD_MIN_COVER_DAYS = 3.0
# 预算极端不足时，民生底线至少保到该比例（宁可少进高毛利货）
LIVELIHOOD_FLOOR_RATIO = 0.85

# ── 目标覆盖天数（动态计算，不再由「民生固定4天」拍脑袋）──────────
# 基础覆盖 = 供应商交期 + 补货缓冲（下次检查/补货间隔），
# 再叠加民生保障缓冲，最后受保质期约束。
# 事件对需求的影响只在预测侧乘一次（见 forecast._risk_adjust），不再叠加覆盖天数。
REVIEW_BUFFER_DAYS = 1.0      # 基础补货缓冲：下次检查/补货的间隔（天）

# ── 创新点 2：自进化边界（防震荡） ────────────────────────
SAFETY_FACTOR_MIN = 0.05
SAFETY_FACTOR_MAX = 0.60
BASE_DAYS_MIN = 2.0
BASE_DAYS_MAX = 12.0
LIVELIHOOD_BASE_DAYS_MIN = 4.0   # 民生商品备货天数下限更高
EVOLVE_UP_STEP = 0.06            # 断货 → 上调安全系数步长
EVOLVE_DOWN_STEP = 0.04          # 积压损耗 → 下调步长
EVOLVE_UP_MAX_MULT = 2.5         # 单次上调的严重程度上限倍数
STOCKOUT_TRIGGER = 0.10          # 缺货率超过该阈值触发进化（≥10% 视为真实缺货，如 8/61≈13%）
SPOILAGE_TRIGGER = 0.10          # 损耗率超过该阈值触发进化

# ── 创新点 2：基于经营反馈的策略自适应（在线策略校准）──────────────
# 补货决策时，从长期记忆里检索「同场景、同商品」的经营经验：
#   · 曾断货 → 安全库存系数小幅上调；曾报损/积压 → 小幅下调；
#   · 单条 ±0.02，单商品累计幅度夹紧到 ±0.06，避免一次反馈让补货量剧烈变化。
MEMORY_SAFETY_UP_STEP = 0.02     # 每条「断货」经验的安全系数上调量
MEMORY_SAFETY_DOWN_STEP = 0.02   # 每条「积压损耗」经验的安全系数下调量
MEMORY_SAFETY_MAX_DELTA = 0.06   # 场景校准的累计最大幅度（防单次过冲）

# ── 预测参数 ──────────────────────────────────────────────
LOOKBACK_DAYS = 28               # 预测回看窗口
DECAY_ALPHA = 0.06               # 指数衰减系数（近期权重更高）

# ── Event Evidence Gate（事件证据门控）统计规则 ──────────────
# 事件工具不再「一出现就乘固定倍率」，而是先评估历史证据可信度再决定是否进入预测。
# 以下为通用、保守的统计门槛（不针对本数据集反推，也不保证任何策略"赢"）。
EVIDENCE_MIN_EVENT_SAMPLES = 3       # 事件日样本数下限（低于 → 证据不足）
EVIDENCE_MIN_BASE_SAMPLES = 5        # 可比普通日样本数下限（低于 → 证据不足）
EVIDENCE_MIN_UPLIFT_DELTA = 0.05     # 效应量下限：|uplift − 1| < 5% 视为无意义
EVIDENCE_MIN_CONSISTENCY = 0.67      # 方向一致性下限：≥2/3 事件日同向才稳定
EVIDENCE_CI_T_CRIT = 2.0             # 双尾 t 分位数（≈90% 置信，保守常数）
EVIDENCE_SEASON_WINDOW_DAYS = 45     # 相近季节窗口：事件日前后 ±45 天的同星期几普通日

# ── 预测增强：趋势外推 ──────────────────────────────────
USE_TREND = True                 # 是否启用线性趋势外推
TREND_HORIZON = 1.0              # 趋势外推天数（天）
TREND_MIN_SAMPLES = 7            # 少于该样本数不启用趋势（防过拟合）
TREND_MULT_MIN, TREND_MULT_MAX = 0.75, 1.35   # 趋势调整倍数的夹紧区间

# ── R³-Stock 多目标整数优化（MILP 求解器，创新点 1 的升级形态）──
# 把最终采购分配从「规则/贪心」升级为真正的 Revenue–Resilience–Responsibility
# 整数优化模型；求解器不可用或求解异常时自动回退到原贪心算法，绝不让系统崩溃。
R3_SOLVER_ENABLED = True         # 是否启用 MILP 求解器升级分配层
R3_SOLVER_TIMEOUT = 30           # 单次求解超时（秒），超时视为失败并回退
RESILIENCE_SHORTFALL_PENALTY = 1.0  # 韧性目标：相对目标库存每缺口 1 件折算的惩罚（元）

# ── 潜在需求还原（消融实验开关，见 eval.py）──────────────
RESTORE_POTENTIAL = True         # True=断货日销量还原为潜在需求（默认）

# ── LLM 说明层（可选；未配置密钥则自动降级为规则模板）────
LLM_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "8"))

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
