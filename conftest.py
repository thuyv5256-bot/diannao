# -*- coding: utf-8 -*-
"""pytest 公共配置：确保 core 可导入，并提供隔离的临时记忆库 fixture。"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import memory  # noqa: E402


def require_app():
    """导入 app.py（Gradio 装配层）；缺 gradio / plotly 时让用例 **skip** 而不是失败（T-QA-04）。

    app.py 是网页装配层，依赖 gradio 与 plotly。这两个包没装时，UI 层测试没有意义，
    但它们**不应该**把测试套件染红 —— 其余 170+ 个用例在无 UI 依赖的环境里照样该全绿。
    """
    pytest.importorskip("gradio", exc_type=ImportError,
                        reason="app.py 依赖 gradio（未安装则跳过 UI 层用例）")
    pytest.importorskip("plotly", exc_type=ImportError,
                        reason="app.py 依赖 plotly（未安装则跳过 UI 层用例）")
    import app  # noqa: E402
    return app


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
