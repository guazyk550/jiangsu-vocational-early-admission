"""本地文件存取基础设施（用户数据目录、JSON 原子读写）。

为什么把用户数据放在用户目录
----------------------------
打包后的 exe 可能被放在 ``C:\\Program Files`` 等无写权限的位置，收藏/最近浏览
必须写到用户可写目录（Windows 为 ``%APPDATA%``），否则会静默失败。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

APP_DIR_NAME = "JSVocNav"


def app_data_dir() -> Path:
    """返回应用的用户数据目录（不存在则创建）。"""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Roaming"
    else:
        base = os.environ.get("XDG_DATA_HOME")
        root = Path(base) if base else Path.home() / ".local" / "share"
    directory = root / APP_DIR_NAME
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        # 极端情况下退回到临时目录，保证功能仍可用
        directory = Path(tempfile.gettempdir()) / APP_DIR_NAME
        directory.mkdir(parents=True, exist_ok=True)
    return directory


def read_json(path: Path, default: Any) -> Any:
    """读取 JSON；文件缺失/损坏时返回 default，并把损坏文件改名为 .bak。"""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        try:
            path.replace(path.with_suffix(path.suffix + ".bak"))
        except OSError:
            pass
        return default


def write_json_atomic(path: Path, payload: Any) -> bool:
    """原子写入 JSON（先写临时文件再替换），避免写入中断导致文件损坏。"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temp_name = handle.name
        Path(temp_name).replace(path)
        return True
    except OSError:
        return False
