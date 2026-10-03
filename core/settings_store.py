# -*- coding: utf-8 -*-
"""小满 · 界面设置持久化（`data/ui_settings.json`）

只存**界面偏好**，不碰业务数据（业务数据一律在 SQLite 记忆库，见 core/memory.py）：
  · theme        当前主题 id（见 core/themes.py）
  · updated_at   最后修改时间

设计要点（容错优先：界面设置坏掉不该让应用起不来）
  · 文件不存在 / JSON 损坏 / 读写异常 → 一律回退默认值，不抛错
  · 写入走"临时文件 + os.replace"，避免留下半截文件
  · 路径可用 `settings_store.PATH` 覆写（测试 monkeypatch，与 memory.DB_PATH 同思路）
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from . import themes
from .config import DATA_DIR

PATH = DATA_DIR / "ui_settings.json"

DEFAULTS: dict = {"theme": themes.DEFAULT_ID}


def _resolve(path=None) -> Path:
    return Path(path) if path else Path(PATH)


def load(path=None) -> dict:
    """读设置；任何异常都回退默认值（并把 theme 收敛成合法 id）。"""
    data = dict(DEFAULTS)
    p = _resolve(path)
    try:
        if p.exists():
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data.update(raw)
    except Exception:
        data = dict(DEFAULTS)
    data["theme"] = themes.normalize(data.get("theme"))
    return data


def get_value(key: str, default=None, path=None):
    return load(path).get(key, default)


def set_value(key: str, value, path=None) -> dict:
    """写一个设置项，返回写入后的完整设置（失败时静默返回当前值）。"""
    data = load(path)
    data[key] = themes.normalize(value) if key == "theme" else value
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _write(data, path)
    return data


def set_theme(theme_id, path=None) -> dict:
    return set_value("theme", theme_id, path=path)


def current_theme(path=None) -> str:
    return load(path)["theme"]


def reset(path=None) -> dict:
    data = dict(DEFAULTS)
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _write(data, path)
    return data


def _write(data: dict, path=None) -> None:
    p = _resolve(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=p.name + ".", dir=str(p.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, p)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
    except Exception:
        pass  # 界面偏好写不进去也不该影响使用
