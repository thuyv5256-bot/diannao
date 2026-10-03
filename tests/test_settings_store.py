# -*- coding: utf-8 -*-
"""界面设置持久化测试：默认值 / 往返 / 容错 / 原子写。"""

import json

from core import settings_store, themes


def test_defaults_when_file_missing(tmp_path):
    p = tmp_path / "ui.json"
    assert settings_store.load(p)["theme"] == themes.DEFAULT_ID
    assert settings_store.current_theme(p) == themes.DEFAULT_ID


def test_set_theme_round_trip(tmp_path):
    p = tmp_path / "ui.json"
    settings_store.set_theme("animal", path=p)
    assert settings_store.current_theme(p) == "animal"
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert raw["theme"] == "animal"
    assert "updated_at" in raw


def test_invalid_theme_is_normalized(tmp_path):
    p = tmp_path / "ui.json"
    settings_store.set_theme("nope-not-a-theme", path=p)
    assert settings_store.current_theme(p) == themes.DEFAULT_ID
    # 文件里被写成非法值时，读取也要收敛
    p.write_text(json.dumps({"theme": "??"}), encoding="utf-8")
    assert settings_store.current_theme(p) == themes.DEFAULT_ID


def test_corrupt_file_falls_back_without_raising(tmp_path):
    p = tmp_path / "ui.json"
    p.write_text("{ this is not json", encoding="utf-8")
    assert settings_store.load(p)["theme"] == themes.DEFAULT_ID


def test_reset_restores_default(tmp_path):
    p = tmp_path / "ui.json"
    settings_store.set_theme("dark", path=p)
    settings_store.reset(p)
    assert settings_store.current_theme(p) == themes.DEFAULT_ID


def test_write_is_atomic_and_leaves_no_temp_files(tmp_path):
    p = tmp_path / "ui.json"
    settings_store.set_theme("wenyang", path=p)
    leftovers = [f.name for f in tmp_path.iterdir() if f.name != "ui.json"]
    assert leftovers == []
    assert json.loads(p.read_text(encoding="utf-8"))["theme"] == "wenyang"


def test_unwritable_path_does_not_raise(tmp_path):
    """目录不存在 + 无法创建时也不能抛（界面设置不该让应用起不来）。"""
    bad = tmp_path / "a-file" / "ui.json"
    (tmp_path / "a-file").write_text("not a dir", encoding="utf-8")
    settings_store.set_theme("animal", path=bad)   # 不抛即通过
    assert settings_store.current_theme(bad) == themes.DEFAULT_ID
