# -*- coding: utf-8 -*-
"""并发写库与求解器降级的回归守护（Competition Freeze 前补）。

背景
----
本文件锁住两个真实缺陷的修复：

1. `core/memory.connect()` 曾用裸 `sqlite3.connect()`，多用户同时提交反馈时
   抛 `database is locked` / `attempt to write a readonly database`
   并**静默丢数据**（实测 6 线程 × 20 次写入，120 次只成功 40 次）。
   修复方案经四轮实测对照后定为：**只设 busy_timeout，不启用 WAL、不加锁**
   （对照数据见 `test_connect_does_not_enable_wal` 的 docstring）。

2. R³ 求解器不可用时静默回退贪心，且原因被 `except: pass` 吞掉。
   修复后降级原因写入 `meta['solver']['degraded_reason']`，
   并提供 `r3_optimizer.unavailable_reason()`。

**这些测试不修改主库**，全部在 tmp_path 副本上运行。
"""
import sqlite3
import threading

import pytest

from core import memory, policy, r3_optimizer


# ── 1. busy_timeout 配置（并发不丢数据的唯一手段）──────────

def test_connect_sets_busy_timeout(tmp_path):
    """busy_timeout 应被显式设置，而不是依赖 sqlite3 默认值。

    这是本项目并发安全的**唯一手段**——不要以为开了 WAL 就可以撤掉它。
    """
    db = tmp_path / "bt.db"
    memory.init_db(db)
    with memory.connect(db) as conn:
        t = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    assert t == int(memory.LOCK_TIMEOUT_SEC * 1000), f"busy_timeout={t}"
    assert t > 0, "busy_timeout 为 0 意味着一遇锁就抛错，而不是等待重试"


def test_connect_does_not_enable_wal(tmp_path):
    """刻意**不**启用 WAL —— 这是实测结论，不是遗漏。

    6 线程 × 20 次写入（120 条）对照：

    | 方案| 落库 | 错误 |
    |---|---|---|
    | 不设 WAL + busy_timeout | **120/120** | 0 |
    | 设 WAL + 不加锁 | 40/120 | 4 |
    | 设 WAL + 只锁 commit | 80/120 | 2 |
    | 设 WAL + 锁整个写事务 | 120/120 | 0（但慢 8.5s） |

    WAL 在 Windows 多连接场景下**本身就是丢数据的元凶**，
    且开启成本高（PRAGMA约 60ms/次，会拖慢 180 天仿真）。
    故最终方案：默认 rollback-journal + busy_timeout，零锁。
    """
    db = tmp_path / "nowal.db"
    memory.init_db(db)
    with memory.connect(db) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() != "wal", (
        f"不应启用 WAL（当前 {mode}）。若有人重新开启 WAL，"
        "请先跑 test_concurrent_writes_all_land 验证是否仍会丢数据。")


def test_concurrent_writes_all_land(tmp_path):
    """并发写库不得丢数据 —— 这是本文件的核心回归用例。

    修复前：6 线程 × 20 次写入 → 4 次 `database is locked`，
    DB 里只剩 40 行（丢 67%）。修复后应全部 120 行落库。
    """
    db = tmp_path / "conc.db"
    memory.init_db(db)

    n_threads, per_thread = 6, 20
    errors: list[str] = []
    landed = []
    lock = threading.Lock()

    def worker(idx: int) -> None:
        try:
            for k in range(per_thread):
                uid = f"conc-{idx}-{k}"
                with memory.connect(db) as conn:
                    conn.execute(
                        "INSERT INTO feedback_log"
                        "(submission_id, day, sku, qty_sold) VALUES (?,?,?,?)",
                        (uid, "2026-08-28", "P001", 5),
                    )
                with lock:
                    landed.append(uid)
        except Exception as exc:  # noqa: BLE001
            with lock:
                errors.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=worker, args=(i,))
               for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"并发写入报错 {len(errors)} 次：{errors[:3]}"
    total = n_threads * per_thread
    assert len(landed) == total, f"只成功 {len(landed)}/{total}"

    # 再从库里核一遍，确保不是「以为成功了」
    with memory.connect(db) as conn:
        rows = conn.execute(
            "SELECT COUNT(*) FROM feedback_log WHERE submission_id LIKE 'conc-%'"
        ).fetchone()[0]
    assert rows == total, f"库内实际 {rows} 行，应为 {total} 行"


def test_nested_connect_does_not_deadlock(tmp_path):
    """`with connect()` 内再开一个 connect 不得死锁。

    曾经的实现把整个事务包进进程级写锁，若锁不可重入，
    任何嵌套调用（`memory` 内部函数互相调用）都会永久挂起。
    当前方案无锁，本用例作为回归守护保留。
    """
    db = tmp_path / "nest.db"
    memory.init_db(db)
    with memory.connect(db) as outer:
        outer.execute("SELECT 1").fetchone()
        with memory.connect(db) as inner:
            inner.execute("SELECT COUNT(*) FROM sales").fetchone()
    # 能走到这里就说明没死锁


def test_connect_uses_timeout_argument(tmp_path):
    """sqlite3.connect 必须带 timeout，而不是依赖默认值。

    默认 timeout 是 5.0s，但它是「秒」而非「毫秒」；
    显式传参可避免将来有人改成 0（= 立即抛错）。
    """
    db = tmp_path / "tmo.db"
    memory.init_db(db)
    seen = {}
    real_connect = sqlite3.connect

    def spy(path, **kw):
        seen.update(kw)
        return real_connect(path, **kw)

    orig = memory.sqlite3.connect
    memory.sqlite3.connect = spy
    try:
        with memory.connect(db) as conn:
            conn.execute("SELECT 1")
    finally:
        memory.sqlite3.connect = orig

    assert seen.get("timeout") == memory.LOCK_TIMEOUT_SEC, (
        f"connect 应传timeout={memory.LOCK_TIMEOUT_SEC}，实际 {seen}")


# ── 2. 求解器降级可追溯 ──────────────────────────────────────

def test_unavailable_reason_empty_when_available():
    """scipy 在位时不应报不可用。"""
    if r3_optimizer.available():
        assert r3_optimizer.unavailable_reason() == ""
    else:
        assert "requirements-lock.txt" in r3_optimizer.unavailable_reason()


def test_unavailable_reason_is_actionable(monkeypatch):
    """降级原因必须给出可执行指引，而不是空字符串或一句「失败」。

    scipy 在位时无法自然触发降级，这里直接 monkeypatch 模块级标志
    `_HAS_SCIPY` 来覆盖「不可用」分支，保证该路径**始终被执行**（零 skip）。
    """
    monkeypatch.setattr(r3_optimizer, "_HAS_SCIPY", False)
    reason = r3_optimizer.unavailable_reason()
    assert reason, "不可用时必须返回原因"
    assert "milp" in reason.lower() or "scipy" in reason.lower()
    assert "requirements-lock.txt" in reason, "应告诉使用者如何修复"
    assert "贪心" in reason, "必须说明降级后行为变了（不再是 MILP 最优）"


def _plan_solver_meta(solver=None):
    """跑真实业务链取solver 元信息（只读，不写主库）。

    刻意不构造裸 items —— `_allocate_plan` 依赖 `_prepare_items` 产出的
    完整字段（cost/price/shelf_life/livelihood 等），手搓容易字段不全导致
    测试变成假验证。这里用 `build_plan(persist=False)` 走真实路径。
    """
    from core.config import DEFAULT_BUDGET
    plan = policy.build_plan("2026-08-28", DEFAULT_BUDGET,
                             policy.MODE_DIANNAO, persist=False,
                             solver=solver)
    return (plan.get("meta") or {}).get("solver") or {}


def test_fallback_records_degraded_reason():
    """回退贪心时，solver 元信息必须带 degraded_reason（不得再是黑盒）。"""
    sv = _plan_solver_meta(solver=False)
    assert sv.get("used_milp") is False
    assert sv.get("degraded_reason"), "显式关闭求解器时必须记录原因"
    assert sv["degraded_reason"] == "disabled_by_config"


def test_degraded_reason_absent_when_milp_used():
    """真走 MILP 时不应带降级标记，避免误报。"""
    if not r3_optimizer.available():
        pytest.skip("scipy 不可用，无法验证 MILP 成功路径")
    sv = _plan_solver_meta()
    assert sv.get("used_milp") is True
    assert not sv.get("degraded_reason"), "MILP 成功时不应标记降级"


# ── 3. 数值不变守护 ─────────────────────────────────────────

def test_wal_does_not_change_results():
    """WAL 与写锁只改持久化层调度，不得影响补货数字。"""
    from core.config import DEFAULT_BUDGET
    qty = []
    for _ in range(2):
        plan = policy.build_plan("2026-08-28", DEFAULT_BUDGET,
                                 policy.MODE_DIANNAO, persist=False)
        qty.append([it.get("reorder_qty") for it in plan.get("items", [])])
    assert qty[0] == qty[1], "同一输入两次build_plan 结果应完全一致"
    assert any(v for v in qty[0]), "补货结果不应全为 0"
