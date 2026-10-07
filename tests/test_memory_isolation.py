# -*- coding: utf-8 -*-
"""回归测试：demo / eval / audit / test 不得污染正式 Memory 库。

背景
----
`evolution.process_feedback` 的 `persist` 默认值是 `True`（生产反馈入口必须落库），
但历史上多个**非生产**调用点没有显式传 `persist=False`：

    demo_flow.py:117/245     演示脚本
    core/eval_core.py:141    legacy 评测重演

加上 `demo_flow.py` / `eval.py` / `run_digital_store.py` 会主动调用
`generate_history()`（**清空后重建**整个记忆库）来演示「从零开始 → 逐步进化」，
结果一次演示就会把店主真实录入的经营反馈、以及「演示门店·模拟经营历史」的
经验全部清掉—— 实测曾造成 `experiences` 表 2224 条污染。

修复
----
1. 非生产调用点显式 `persist=False`；
2. `apply_sales_only` 新增 `persist` 参数；
3. demo/eval/digital_store 入口默认在**临时副本**（沙箱）上运行，`--real-db` 可退回。

本文件把这条约束固化成自动化测试，防止将来再出现静默写主库的入口。
"""
import io
import os
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import config, evolution, memory  # noqa: E402

TABLES = ("experiences", "evolution_log", "feedback_log", "sales",
          "products", "day_events", "inventory", "policy", "plan_log")


def _snapshot(db_path=None):
    """给每张表取 (行数, 内容哈希)，用于逐位比对。"""
    c = sqlite3.connect(str(db_path or config.DB_PATH))
    out = {}
    try:
        for t in TABLES:
            rows = sorted(map(str, c.execute("SELECT * FROM %s" % t).fetchall()))
            out[t] = (len(rows), hash(tuple(rows)))
    finally:
        c.close()
    return out


@pytest.fixture
def sandbox(tmp_path):
    """把 memory.DB_PATH 指向临时副本，跑完自动还原。"""
    tmp = tmp_path / "sandbox.db"
    src = Path(config.DB_PATH)
    if src.exists():
        import shutil
        shutil.copy2(src, tmp)
    else:
        memory.init_db(str(tmp))
    old = memory.DB_PATH
    memory.DB_PATH = str(tmp)
    try:
        yield str(tmp)
    finally:
        memory.DB_PATH = old


# ══════════════════════════════════════════════════════════════
# 一、静态检查：非生产调用点必须显式声明不落库
# ══════════════════════════════════════════════════════════════

NON_PROD_FILES = ["demo_flow.py", "eval.py", "run_digital_store.py",
                  "core/eval_core.py"]

# 这些文件里允许出现的 process_feedback / apply_sales_only 调用形态：
#   evolution.process_feedback(..., persist=False, ...)   显式不落库
#   evolution.process_feedback(day, fb)                    仿真隔离库内，允许
# 但**不允许**出现「裸调用 + 注释说明靠隔离」之外的写法。
SAFE_CALL = "persist=False"


@pytest.mark.parametrize("rel", NON_PROD_FILES)
def test_non_prod_scripts_declare_sandbox_or_persist_false(rel):
    """demo / eval / digital_store 必须有沙箱开关或显式 persist=False。"""
    src = (ROOT / rel).read_text(encoding="utf-8")
    has_sandbox = ("--real-db" in src) or ("DB_PATH = str(" in src)
    assert has_sandbox, (
        "%s 没有任何沙箱/隔离声明 —— 运行它会污染正式 store_memory.db" % rel)


@pytest.mark.parametrize("rel", ["demo_flow.py", "core/eval_core.py"])
def test_legacy_process_feedback_calls_pass_persist_false(rel):
    """这两个文件里的裸调用必须全部带上 persist=False。"""
    import re
    src = (ROOT / rel).read_text(encoding="utf-8")
    # 匹配跨行调用：evolution.process_feedback( ... )
    bad = []
    for m in re.finditer(r"evolution\.(process_feedback|apply_sales_only)\s*\(",
                         src):
        start = m.end() - 1
        depth, i = 0, start
        while i < len(src):
            if src[i] == "(":
                depth += 1
            elif src[i] == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        call = src[start:i + 1]
        if SAFE_CALL not in call:
            line = src[:m.start()].count("\n") + 1
            bad.append("第 %d 行: %s" % (line, " ".join(call.split())[:70]))
    assert not bad, ("%s 存在会写主库的裸调用：\n    %s"
                     % (rel, "\n    ".join(bad)))


# ══════════════════════════════════════════════════════════════
# 二、行为检查：跑非生产流程后正式库必须逐位不变
# ══════════════════════════════════════════════════════════════

def test_process_feedback_persist_false_does_not_write(sandbox):
    """persist=False 时不得产生任何 experiences / evolution_log 记录。"""
    before = _snapshot(sandbox)
    fb = [{"sku": "P002", "qty_sold": 5.0, "qty_stockout": 6.0,
           "qty_spoilage": 0.0, "is_promo": 0, "is_holiday": 0}]
    evolution.process_feedback("2026-07-18", fb, persist=False)
    after = _snapshot(sandbox)
    assert before == after, (
        "persist=False 仍写库：%s"
        % [t for t in TABLES if before[t] != after[t]])


def test_apply_sales_only_persist_false_does_not_write(sandbox):
    """apply_sales_only(persist=False) 不得污染 sales / feedback_log。"""
    before = _snapshot(sandbox)
    fb = [{"sku": "P002", "qty_sold": 9.9, "qty_stockout": 0.0,
           "qty_spoilage": 0.0, "is_promo": 0, "is_holiday": 0}]
    evolution.apply_sales_only("2026-07-18", fb, persist=False)
    after = _snapshot(sandbox)
    assert before == after, (
        "apply_sales_only(persist=False) 仍写库：%s"
        % [t for t in TABLES if before[t] != after[t]])


def test_process_feedback_persist_true_still_writes(sandbox):
    """反向保障：生产路径 persist=True 必须仍然落库（防止过度封堵）。"""
    fb = [{"sku": "P002", "qty_sold": 5.0, "qty_stockout": 6.0,
           "qty_spoilage": 0.0, "is_promo": 0, "is_holiday": 0}]
    evolution.process_feedback("2026-07-18", fb, persist=True)
    c = sqlite3.connect(sandbox)
    try:
        n = c.execute("SELECT COUNT(*) FROM experiences").fetchone()[0]
    finally:
        c.close()
    assert n >= 1, "persist=True 未能落库 —— 生产反馈入口被误封堵"


@pytest.mark.slow
def test_demo_flow_entrypoint_uses_sandbox():
    """demo_flow.main() 默认走沙箱（静态确认它会切走 DB_PATH）。"""
    src = (ROOT / "demo_flow.py").read_text(encoding="utf-8")
    assert "_sandbox" in src or "sandbox" in src
    assert "--real-db" in src, "缺少 --real-db 逃生开关"
    # 沙箱必须在 finally 里清理
    assert "finally" in src and "unlink" in src, "沙箱没有在 finally 里清理"


@pytest.mark.slow
def test_eval_entrypoint_uses_sandbox():
    """eval.main() 默认走沙箱，且不再调 generate_history 清库。"""
    import re
    src = (ROOT / "eval.py").read_text(encoding="utf-8")
    assert "_sandbox" in src, "eval.py 没有沙箱入口"
    # 精确检查「真实调用」而不是文档字符串里提到它：
    # generate_history(...) 出现在代码里（前面是空白/换行且不是注释或字符串）
    real_calls = [m for m in re.finditer(r"^[ \t]*from seed_data import generate_history",
                                        src, re.M)]
    real_calls += [m for m in re.finditer(r"^[ \t]*generate_history\(", src, re.M)]
    assert not real_calls, (
        "eval.py 仍有真实调用 generate_history() 的语句（第 %d 行）—— "
        "它会清空正式库的经营经验" % (real_calls[0].start() if real_calls else 0))
