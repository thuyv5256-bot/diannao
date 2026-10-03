# -*- coding: utf-8 -*-
"""
小满 · 长期记忆模块（创新点 2 的载体）

门店的所有经营信息在这里沉淀下来，跨会话、跨时间持久存在：
  · products      商品档案（含民生商品标记）
  · policy        可进化的策略参数（每 SKU 一组 base_days / safety_factor）
  · sales         历史销量与经营事件（断货量、损耗量）
  · inventory     当前库存
  · evolution_log 策略进化轨迹（可可视化，是"自进化真的发生了"的证据）
  · plan_log      历史补货方案留痕
"""

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterable

from .config import DB_PATH


def _stable_uid(day, sku, sold=0.0, stockout=0.0, spoilage=0.0) -> str:
    """稳定、可复现的反馈唯一标识（内容哈希）：同一反馈重复提交 → 同一 uid。"""
    raw = (f"{str(day)[:10]}|{sku}|{float(sold):.4f}|"
           f"{float(stockout):.4f}|{float(spoilage):.4f}")
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    sku             TEXT PRIMARY KEY,
    name            TEXT    NOT NULL,
    category        TEXT    NOT NULL,
    unit            TEXT    NOT NULL DEFAULT '件',
    cost_price      REAL    NOT NULL,
    sell_price      REAL    NOT NULL,
    is_livelihood   INTEGER NOT NULL DEFAULT 0,
    shelf_life_days INTEGER NOT NULL DEFAULT 365,
    pack_size       INTEGER NOT NULL DEFAULT 1,
    traffic_pull    REAL    NOT NULL DEFAULT 1.0,
    supplier        TEXT    NOT NULL DEFAULT '',
    lead_time_days  INTEGER NOT NULL DEFAULT 1,
    base_daily_demand REAL  NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS policy (
    sku           TEXT PRIMARY KEY,
    base_days     REAL NOT NULL,
    safety_factor REAL NOT NULL,
    version       INTEGER NOT NULL DEFAULT 1,
    updated_at    TEXT
);

CREATE TABLE IF NOT EXISTS sales (
    day          TEXT NOT NULL,
    sku          TEXT NOT NULL,
    qty_sold     REAL NOT NULL DEFAULT 0,
    qty_stockout REAL NOT NULL DEFAULT 0,
    qty_spoilage REAL NOT NULL DEFAULT 0,
    is_promo     INTEGER NOT NULL DEFAULT 0,
    is_holiday   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, sku)
);

CREATE TABLE IF NOT EXISTS inventory (
    sku     TEXT PRIMARY KEY,
    on_hand REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS evolution_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    day       TEXT NOT NULL,
    sku       TEXT NOT NULL,
    param     TEXT NOT NULL,
    old_value REAL,
    new_value REAL,
    trigger   TEXT,
    reason    TEXT
);

CREATE TABLE IF NOT EXISTS plan_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    day               TEXT NOT NULL,
    mode              TEXT NOT NULL,
    sku               TEXT NOT NULL,
    forecast_daily    REAL,
    target_cover_days REAL,
    target_stock      REAL,
    on_hand           REAL,
    reorder_qty       REAL,
    cost              REAL,
    is_livelihood     INTEGER,
    trimmed           INTEGER
);

CREATE TABLE IF NOT EXISTS day_events (
    day                  TEXT PRIMARY KEY,
    weather              TEXT NOT NULL DEFAULT '',
    temperature_c        REAL,
    event                TEXT NOT NULL DEFAULT '正常',
    is_weekend           INTEGER NOT NULL DEFAULT 0,
    supplier_available   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS experiences (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    day         TEXT NOT NULL,
    sku         TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    signal      TEXT NOT NULL,
    forecast_qty  REAL NOT NULL DEFAULT 0,
    reorder_qty   REAL NOT NULL DEFAULT 0,
    qty_sold      REAL NOT NULL DEFAULT 0,
    qty_stockout  REAL NOT NULL DEFAULT 0,
    qty_spoilage  REAL NOT NULL DEFAULT 0,
    lesson      TEXT NOT NULL,
    adjustment  TEXT NOT NULL DEFAULT '',
    created_at  TEXT,
    uid         TEXT
);

CREATE TABLE IF NOT EXISTS feedback_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id TEXT NOT NULL,
    day           TEXT NOT NULL,
    sku           TEXT NOT NULL,
    qty_sold      REAL NOT NULL DEFAULT 0,
    qty_stockout  REAL NOT NULL DEFAULT 0,
    qty_spoilage  REAL NOT NULL DEFAULT 0,
    event         TEXT NOT NULL DEFAULT '正常',
    forecast_qty  REAL NOT NULL DEFAULT 0,
    reorder_qty   REAL NOT NULL DEFAULT 0,
    is_promo      INTEGER NOT NULL DEFAULT 0,
    is_holiday    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT,
    uid           TEXT
);

CREATE INDEX IF NOT EXISTS idx_sales_sku_day ON sales(sku, day);
CREATE INDEX IF NOT EXISTS idx_evo_day      ON evolution_log(day);
"""


@contextmanager
def connect(db_path=None):
    """带行工厂的 SQLite 连接上下文管理器。"""
    conn = sqlite3.connect(str(db_path or DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path=None) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
        _dedup_learning(conn)


def _dedup_learning(conn) -> None:
    """一次性去重：修复「同一反馈重复提交导致重复学习」留下的脏数据。

    · experiences：同一 (day, sku) 只保留最新一条（重复提交的经验合并为一条）；
    · evolution_log：同一 (day, sku, param) 只保留最早一条（首次校准值，即只学一次）。
    幂等：重复执行无副作用；修复后新代码会从源头阻止再产生重复。
    """
    dup_exps = conn.execute(
        "SELECT day, sku FROM experiences GROUP BY day, sku HAVING COUNT(*) > 1"
    ).fetchall()
    for r in dup_exps:
        keep_id = conn.execute(
            "SELECT id FROM experiences WHERE day=? AND sku=? ORDER BY id DESC LIMIT 1",
            (r["day"], r["sku"])).fetchone()[0]
        conn.execute(
            "DELETE FROM experiences WHERE day=? AND sku=? AND id != ?",
            (r["day"], r["sku"], keep_id))

    dup_evos = conn.execute(
        "SELECT day, sku, param FROM evolution_log GROUP BY day, sku, param HAVING COUNT(*) > 1"
    ).fetchall()
    for r in dup_evos:
        keep_id = conn.execute(
            "SELECT id FROM evolution_log WHERE day=? AND sku=? AND param=? ORDER BY id ASC LIMIT 1",
            (r["day"], r["sku"], r["param"])).fetchone()[0]
        conn.execute(
            "DELETE FROM evolution_log WHERE day=? AND sku=? AND param=? AND id != ?",
            (r["day"], r["sku"], r["param"], keep_id))


def _migrate(conn) -> None:
    """为旧版记忆库补齐新增列（幂等：已存在的列不会重复添加）。"""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(products)")}
    additions = {
        "supplier": "TEXT NOT NULL DEFAULT ''",
        "lead_time_days": "INTEGER NOT NULL DEFAULT 1",
        "base_daily_demand": "REAL NOT NULL DEFAULT 0",
    }
    for col, decl in additions.items():
        if col not in cols:
            conn.execute(f"ALTER TABLE products ADD COLUMN {col} {decl}")

    # experiences 表补充「完整经营经验」所需字段
    exp_cols = {r["name"] for r in conn.execute("PRAGMA table_info(experiences)")}
    exp_additions = {
        "forecast_qty": "REAL NOT NULL DEFAULT 0",
        "reorder_qty": "REAL NOT NULL DEFAULT 0",
        "qty_sold": "REAL NOT NULL DEFAULT 0",
        "qty_stockout": "REAL NOT NULL DEFAULT 0",
        "qty_spoilage": "REAL NOT NULL DEFAULT 0",
        "adjustment": "TEXT NOT NULL DEFAULT ''",
    }
    for col, decl in exp_additions.items():
        if col not in exp_cols:
            conn.execute(f"ALTER TABLE experiences ADD COLUMN {col} {decl}")

    # uid：稳定唯一标识（去重键），并为经验/反馈建唯一索引（NULL 不冲突，兼容旧数据）
    if "uid" not in exp_cols:
        conn.execute("ALTER TABLE experiences ADD COLUMN uid TEXT")
    fb_cols = {r["name"] for r in conn.execute("PRAGMA table_info(feedback_log)")}
    if "uid" not in fb_cols:
        conn.execute("ALTER TABLE feedback_log ADD COLUMN uid TEXT")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_exp_uid ON experiences(uid)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_fb_uid ON feedback_log(uid)")


# ── 商品档案 ──────────────────────────────────────────────
def upsert_products(rows: Iterable[dict], db_path=None) -> None:
    sql = """
    INSERT INTO products
        (sku, name, category, unit, cost_price, sell_price,
         is_livelihood, shelf_life_days, pack_size, traffic_pull,
         supplier, lead_time_days, base_daily_demand)
    VALUES (:sku, :name, :category, :unit, :cost_price, :sell_price,
            :is_livelihood, :shelf_life_days, :pack_size, :traffic_pull,
            :supplier, :lead_time_days, :base_daily_demand)
    ON CONFLICT(sku) DO UPDATE SET
        name=excluded.name, category=excluded.category, unit=excluded.unit,
        cost_price=excluded.cost_price, sell_price=excluded.sell_price,
        is_livelihood=excluded.is_livelihood,
        shelf_life_days=excluded.shelf_life_days,
        pack_size=excluded.pack_size, traffic_pull=excluded.traffic_pull,
        supplier=excluded.supplier, lead_time_days=excluded.lead_time_days,
        base_daily_demand=excluded.base_daily_demand
    """
    defaults = {"unit": "件", "pack_size": 1, "traffic_pull": 1.0,
                "supplier": "", "lead_time_days": 1, "base_daily_demand": 0.0}
    payload = []
    for r in rows:
        d = dict(defaults)
        d.update(r)
        payload.append(d)
    with connect(db_path) as conn:
        conn.executemany(sql, payload)


def get_products(db_path=None) -> list[dict]:
    with connect(db_path) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM products ORDER BY is_livelihood DESC, sku")]


def get_product(sku: str, db_path=None) -> dict | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM products WHERE sku=?", (sku,)).fetchone()
        return dict(row) if row else None


# ── 策略参数（可进化） ────────────────────────────────────
def set_policy(sku: str, base_days: float, safety_factor: float,
               bump_version: bool = False, db_path=None) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with connect(db_path) as conn:
        if bump_version:
            conn.execute(
                """INSERT INTO policy (sku, base_days, safety_factor, version, updated_at)
                   VALUES (?, ?, ?, 1, ?)
                   ON CONFLICT(sku) DO UPDATE SET
                       base_days=excluded.base_days,
                       safety_factor=excluded.safety_factor,
                       version=policy.version+1,
                       updated_at=excluded.updated_at""",
                (sku, base_days, safety_factor, now),
            )
        else:
            conn.execute(
                """INSERT INTO policy (sku, base_days, safety_factor, version, updated_at)
                   VALUES (?, ?, ?, 1, ?)
                   ON CONFLICT(sku) DO UPDATE SET
                       base_days=excluded.base_days,
                       safety_factor=excluded.safety_factor,
                       updated_at=excluded.updated_at""",
                (sku, base_days, safety_factor, now),
            )


def get_policy(sku: str, db_path=None) -> dict | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM policy WHERE sku=?", (sku,)).fetchone()
        return dict(row) if row else None


def get_all_policy(db_path=None) -> dict[str, dict]:
    with connect(db_path) as conn:
        return {r["sku"]: dict(r) for r in conn.execute("SELECT * FROM policy")}


# ── 库存 ──────────────────────────────────────────────────
def set_inventory(sku: str, on_hand: float, db_path=None) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """INSERT INTO inventory (sku, on_hand) VALUES (?, ?)
               ON CONFLICT(sku) DO UPDATE SET on_hand=excluded.on_hand""",
            (sku, on_hand),
        )


def set_inventory_bulk(pairs: Iterable[tuple[str, float]], db_path=None) -> None:
    with connect(db_path) as conn:
        conn.executemany(
            """INSERT INTO inventory (sku, on_hand) VALUES (?, ?)
               ON CONFLICT(sku) DO UPDATE SET on_hand=excluded.on_hand""",
            list(pairs),
        )


def get_inventory(db_path=None) -> dict[str, float]:
    with connect(db_path) as conn:
        return {r["sku"]: r["on_hand"] for r in conn.execute("SELECT * FROM inventory")}


# ── 销量与经营事件 ────────────────────────────────────────
def add_sales(rows: Iterable[dict], db_path=None) -> None:
    sql = """
    INSERT INTO sales (day, sku, qty_sold, qty_stockout, qty_spoilage, is_promo, is_holiday)
    VALUES (:day, :sku, :qty_sold, :qty_stockout, :qty_spoilage, :is_promo, :is_holiday)
    ON CONFLICT(day, sku) DO UPDATE SET
        qty_sold=excluded.qty_sold, qty_stockout=excluded.qty_stockout,
        qty_spoilage=excluded.qty_spoilage,
        is_promo=excluded.is_promo, is_holiday=excluded.is_holiday
    """
    with connect(db_path) as conn:
        conn.executemany(sql, list(rows))


def get_sales(sku: str, before_day: str, lookback: int = 28, db_path=None) -> list[dict]:
    """取某 SKU 在 before_day 之前（不含当天）的最近 lookback 天记录，按日期升序。"""
    with connect(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM sales WHERE sku=? AND day < ?
               ORDER BY day DESC LIMIT ?""",
            (sku, before_day, lookback),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_sales_range(sku: str, start_day: str, end_day: str, db_path=None) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM sales WHERE sku=? AND day BETWEEN ? AND ?
               ORDER BY day""",
            (sku, start_day, end_day),
        ).fetchall()
    return [dict(r) for r in rows]


def available_days(db_path=None) -> list[str]:
    with connect(db_path) as conn:
        return [r["day"] for r in conn.execute("SELECT DISTINCT day FROM sales ORDER BY day")]


# ── 每日经营事件（天气 / 温度 / 事件 / 是否周末 / 供应商是否可到货）──
def upsert_day_events(rows: Iterable[dict], db_path=None) -> None:
    sql = """
    INSERT INTO day_events (day, weather, temperature_c, event, is_weekend, supplier_available)
    VALUES (:day, :weather, :temperature_c, :event, :is_weekend, :supplier_available)
    ON CONFLICT(day) DO UPDATE SET
        weather=excluded.weather, temperature_c=excluded.temperature_c,
        event=excluded.event, is_weekend=excluded.is_weekend,
        supplier_available=excluded.supplier_available
    """
    with connect(db_path) as conn:
        conn.executemany(sql, [dict(r) for r in rows])


def get_day_event(day: str, db_path=None) -> dict | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM day_events WHERE day=?", (day,)).fetchone()
        return dict(row) if row else None


def get_day_events(db_path=None) -> list[dict]:
    with connect(db_path) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM day_events ORDER BY day")]


def get_events_summary(db_path=None) -> list[dict]:
    """按事件类型聚合历史事件（天数 + 首末日期），供「老账本」展示。"""
    with connect(db_path) as conn:
        rows = conn.execute(
            """SELECT event, COUNT(*) AS days, MIN(day) AS first_day, MAX(day) AS last_day
               FROM day_events WHERE event != '正常' GROUP BY event ORDER BY days DESC"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_suppliers(db_path=None) -> list[dict]:
    """供应商名单与各自覆盖的商品数、平均到货时间。"""
    with connect(db_path) as conn:
        rows = conn.execute(
            """SELECT supplier, COUNT(*) AS sku_count,
                      AVG(lead_time_days) AS avg_lead_days
               FROM products GROUP BY supplier ORDER BY supplier"""
        ).fetchall()
        return [dict(r) for r in rows]


# ── 经营经验（「它学会了什么」的沉淀）──────────────────────
def add_experiences(rows: Iterable[dict], db_path=None) -> None:
    sql = """
    INSERT INTO experiences (day, sku, event_type, signal,
        forecast_qty, reorder_qty, qty_sold, qty_stockout, qty_spoilage,
        lesson, adjustment, created_at)
    VALUES (:day, :sku, :event_type, :signal,
        :forecast_qty, :reorder_qty, :qty_sold, :qty_stockout, :qty_spoilage,
        :lesson, :adjustment, :created_at)
    """
    defaults = {"forecast_qty": 0.0, "reorder_qty": 0.0, "qty_sold": 0.0,
                "qty_stockout": 0.0, "qty_spoilage": 0.0, "adjustment": ""}
    payload = []
    for r in rows:
        d = dict(defaults)
        d.update(r)
        payload.append(d)
    with connect(db_path) as conn:
        conn.executemany(sql, payload)


def get_experiences(limit: int = 200, db_path=None) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM experiences ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_experiences_for(event_type: str, db_path=None) -> list[dict]:
    """取某类事件（高温 / 暴雨 / 节假日 / 供应商断货）下的历史经验。"""
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM experiences WHERE event_type=? ORDER BY id DESC", (event_type,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_experience(day: str, sku: str, db_path=None) -> dict | None:
    """取某天某商品已沉淀的经营经验（反馈幂等去重的判据）。"""
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM experiences WHERE day=? AND sku=? ORDER BY id DESC LIMIT 1",
            (day, sku)).fetchone()
        return dict(row) if row else None


def upsert_experience(exp: dict, db_path=None) -> None:
    """按 (day, sku) 幂等地写入经营经验：同一天同一商品只保留一条。

    完全相同的重复提交由上层跳过；这里处理「数据修正」时的覆盖更新，
    用 DELETE + INSERT 实现，避免依赖唯一索引、兼容已有重复数据。
    """
    with connect(db_path) as conn:
        conn.execute("DELETE FROM experiences WHERE day=? AND sku=?",
                     (exp["day"], exp["sku"]))
        conn.execute(
            """INSERT INTO experiences (day, sku, event_type, signal,
                forecast_qty, reorder_qty, qty_sold, qty_stockout, qty_spoilage,
                lesson, adjustment, created_at, uid)
            VALUES (:day, :sku, :event_type, :signal,
                :forecast_qty, :reorder_qty, :qty_sold, :qty_stockout, :qty_spoilage,
                :lesson, :adjustment, :created_at, (:day || '|' || :sku))""",
            exp)


def delete_experience(day: str, sku: str, db_path=None) -> None:
    """删除某天某商品的经验（经营数据修正后不再触发阈值时使用）。"""
    with connect(db_path) as conn:
        conn.execute("DELETE FROM experiences WHERE day=? AND sku=?", (day, sku))


# ── 经营反馈记录（用户手动录入，独立于 180 天仿真 CSV 的 sales 表）────────
def add_feedback_log(rows: Iterable[dict], db_path=None) -> str:
    """
    保存一次用户手动提交的经营反馈。

    与 sales（原始 180 天仿真 CSV）分开存储：每次反馈完整记录
    「日期 + 商品 + 实际销量/断货/报损 + 当时经营场景 + 当时补货决策」，
    这样 Memory 才知道「这是一次高温情况下矿泉水发生断货」，而不是只有
    「矿泉水曾经断货」。同一批行共享一个 submission_id。
    """
    submission_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    defaults = {"submission_id": submission_id, "created_at": created_at,
                "event": "正常", "forecast_qty": 0.0, "reorder_qty": 0.0,
                "is_promo": 0, "is_holiday": 0}
    payload = []
    for r in rows:
        d = dict(defaults)
        d.update(r)
        payload.append(d)
    for d in payload:
        d["uid"] = _stable_uid(d.get("day"), d.get("sku"), d.get("qty_sold", 0), d.get("qty_stockout", 0), d.get("qty_spoilage", 0))
    sql = """
    INSERT OR IGNORE INTO feedback_log (submission_id, day, sku, qty_sold, qty_stockout,
        qty_spoilage, event, forecast_qty, reorder_qty, is_promo, is_holiday, created_at, uid)
    VALUES (:submission_id, :day, :sku, :qty_sold, :qty_stockout,
        :qty_spoilage, :event, :forecast_qty, :reorder_qty, :is_promo, :is_holiday, :created_at, :uid)
    """
    with connect(db_path) as conn:
        conn.executemany(sql, payload)
    return submission_id


def get_feedback_log(limit: int = 200, db_path=None) -> list[dict]:
    """取最近的手动经营反馈记录（最新的在前）。"""
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM feedback_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# ── 进化日志 ──────────────────────────────────────────────
def log_evolution(day: str, sku: str, param: str, old_value: float,
                  new_value: float, trigger: str, reason: str, db_path=None) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """INSERT INTO evolution_log (day, sku, param, old_value, new_value, trigger, reason)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (day, sku, param, old_value, new_value, trigger, reason),
        )


def get_evolution_log(limit: int = 200, db_path=None) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM evolution_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def delete_evolution(day: str, sku: str, param: str, db_path=None) -> None:
    """删除某天某商品某参数的进化记录（经营数据修正后校准被撤销时使用）。"""
    with connect(db_path) as conn:
        conn.execute(
            "DELETE FROM evolution_log WHERE day=? AND sku=? AND param=?",
            (day, sku, param))


def evolution_series(sku: str, param: str, db_path=None) -> list[tuple[str, float, float]]:
    """
    取某 SKU 某参数的演进序列，用于画曲线。
    返回 [(day, old_value, new_value), ...]，带上 old_value 才能画出
    "从初始值出发"的完整轨迹，而不是孤零零几个点。
    """
    with connect(db_path) as conn:
        rows = conn.execute(
            """SELECT day, old_value, new_value FROM evolution_log
               WHERE sku=? AND param=? ORDER BY id""",
            (sku, param),
        ).fetchall()
    return [(r["day"], r["old_value"], r["new_value"]) for r in rows]


def evolution_details(sku: str, db_path=None) -> list[dict]:
    """某 SKU 安全库存系数的完整演进：进化日志 JOIN 经营经验。

    供「它学会了什么」页的演进曲线与悬停详情使用 —— 曲线上的每个点都要能
    回答「哪天、什么场景、卖了多少、断货多少、报损多少、为何调整」。
    只取 param='safety_factor'（当前唯一会进化的参数），按日期升序。
    """
    with connect(db_path) as conn:
        rows = conn.execute(
            """SELECT e.day, e.old_value, e.new_value, e.trigger, e.reason,
                      x.event_type, x.qty_sold, x.qty_stockout, x.qty_spoilage
               FROM evolution_log e
               LEFT JOIN experiences x ON x.day = e.day AND x.sku = e.sku
               WHERE e.sku = ? AND e.param = 'safety_factor'
               ORDER BY e.day, e.id""",
            (sku,)).fetchall()
        return [dict(r) for r in rows]


# ── 补货方案留痕 ──────────────────────────────────────────
def log_plan(day: str, mode: str, rows: Iterable[dict], db_path=None) -> None:
    sql = """
    INSERT INTO plan_log
        (day, mode, sku, forecast_daily, target_cover_days, target_stock,
         on_hand, reorder_qty, cost, is_livelihood, trimmed)
    VALUES (:day, :mode, :sku, :forecast_daily, :target_cover_days, :target_stock,
            :on_hand, :reorder_qty, :cost, :is_livelihood, :trimmed)
    """
    payload = []
    for r in rows:
        d = dict(r)
        d["day"] = day
        d["mode"] = mode
        payload.append(d)
    with connect(db_path) as conn:
        conn.executemany(sql, payload)


def reset_all(db_path=None) -> None:
    """清空全部记忆（重新开始演示用）。"""
    with connect(db_path) as conn:
        for t in ("products", "policy", "sales", "inventory", "evolution_log",
                  "plan_log", "day_events", "experiences", "feedback_log"):
            conn.execute(f"DELETE FROM {t}")


def memory_stats(db_path=None) -> dict[str, Any]:
    """记忆库规模统计，界面上用来体现"记忆在沉淀"。"""
    with connect(db_path) as conn:
        g = lambda q: conn.execute(q).fetchone()[0]
        return {
            "商品数": g("SELECT COUNT(*) FROM products"),
            "民生商品数": g("SELECT COUNT(*) FROM products WHERE is_livelihood=1"),
            "销量记录条数": g("SELECT COUNT(*) FROM sales"),
            "累计覆盖天数": g("SELECT COUNT(DISTINCT day) FROM sales"),
            "策略参数条数": g("SELECT COUNT(*) FROM policy"),
            "进化事件数": g("SELECT COUNT(*) FROM evolution_log"),
            "历史方案条数": g("SELECT COUNT(*) FROM plan_log"),
        }
