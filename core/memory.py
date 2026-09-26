# -*- coding: utf-8 -*-
"""
店脑 · 长期记忆模块（创新点 2 的载体）

门店的所有经营信息在这里沉淀下来，跨会话、跨时间持久存在：
  · products      商品档案（含民生商品标记）
  · policy        可进化的策略参数（每 SKU 一组 base_days / safety_factor）
  · sales         历史销量与经营事件（断货量、损耗量）
  · inventory     当前库存
  · evolution_log 策略进化轨迹（可可视化，是"自进化真的发生了"的证据）
  · plan_log      历史补货方案留痕
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterable

from .config import DB_PATH

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
    traffic_pull    REAL    NOT NULL DEFAULT 1.0
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


# ── 商品档案 ──────────────────────────────────────────────
def upsert_products(rows: Iterable[dict], db_path=None) -> None:
    sql = """
    INSERT INTO products
        (sku, name, category, unit, cost_price, sell_price,
         is_livelihood, shelf_life_days, pack_size, traffic_pull)
    VALUES (:sku, :name, :category, :unit, :cost_price, :sell_price,
            :is_livelihood, :shelf_life_days, :pack_size, :traffic_pull)
    ON CONFLICT(sku) DO UPDATE SET
        name=excluded.name, category=excluded.category, unit=excluded.unit,
        cost_price=excluded.cost_price, sell_price=excluded.sell_price,
        is_livelihood=excluded.is_livelihood,
        shelf_life_days=excluded.shelf_life_days,
        pack_size=excluded.pack_size, traffic_pull=excluded.traffic_pull
    """
    with connect(db_path) as conn:
        conn.executemany(sql, list(rows))


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
        for t in ("products", "policy", "sales", "inventory", "evolution_log", "plan_log"):
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
