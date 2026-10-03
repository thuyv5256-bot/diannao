# -*- coding: utf-8 -*-
"""pytest 公共配置：确保 core 可导入，并提供隔离的临时记忆库 fixture。"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import memory  # noqa: E402


@pytest.fixture
def db(tmp_path, monkeypatch):
    """指向临时 SQLite 的隔离记忆库，并灌入一组精简商品档案。"""
    monkeypatch.setattr(memory, "DB_PATH", str(tmp_path / "test.db"))
    memory.init_db()
    memory.upsert_products([
        dict(sku="L1", name="大米", category="粮油", unit="袋",
             cost_price=24.0, sell_price=26.5, is_livelihood=1,
             shelf_life_days=180, pack_size=4, traffic_pull=1.8),
        dict(sku="N1", name="薯片", category="零食", unit="包",
             cost_price=4.2, sell_price=6.5, is_livelihood=0,
             shelf_life_days=180, pack_size=12, traffic_pull=1.0),
    ])
    memory.set_policy("L1", 5.0, 0.15)
    memory.set_policy("N1", 3.0, 0.15)
    return memory
