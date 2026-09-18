"""收藏与最近浏览（本地 ``favorites.json`` / ``recent.json``）。

两者都写进用户数据目录（见 :mod:`src.services.storage`），存的是院校 ``id``，
与数据集解耦：数据更新后只要 id 稳定，收藏就不会丢。
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from src.services.storage import app_data_dir, read_json, write_json_atomic

FAVORITES_FILENAME = "favorites.json"
RECENT_FILENAME = "recent.json"
RECENT_LIMIT = 20


class FavoritesService:
    """收藏管理。"""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (app_data_dir() / FAVORITES_FILENAME)
        self._ids: list[str] = []

    def load(self) -> list[str]:
        raw = read_json(self.path, default={"ids": []})
        ids: Any
        if isinstance(raw, dict):
            ids = raw.get("ids")
        else:
            ids = raw  # 兼容裸数组格式
        self._ids = [str(item) for item in ids] if isinstance(ids, list) else []
        return self._ids

    @property
    def ids(self) -> list[str]:
        return list(self._ids) if self._ids else self.load()

    def is_favorite(self, school_id: str) -> bool:
        return school_id in self.ids

    def toggle(self, school_id: str) -> bool:
        """切换收藏状态，返回切换后是否已收藏。"""
        current = self.ids
        if school_id in current:
            current.remove(school_id)
            favorite = False
        else:
            current.insert(0, school_id)
            favorite = True
        self._ids = current
        self._save()
        return favorite

    def clear(self) -> None:
        self._ids = []
        self._save()

    def _save(self) -> bool:
        return write_json_atomic(
            self.path,
            {
                "updated_at": dt.datetime.now().astimezone().isoformat(
                    timespec="seconds"
                ),
                "ids": self._ids,
            },
        )


class RecentService:
    """最近浏览记录（最多 :data:`RECENT_LIMIT` 条，最新在前）。"""

    def __init__(self, path: Path | None = None, limit: int = RECENT_LIMIT) -> None:
        self.path = path or (app_data_dir() / RECENT_FILENAME)
        self.limit = limit
        self._ids: list[str] = []

    def load(self) -> list[str]:
        raw = read_json(self.path, default={"ids": []})
        ids = raw.get("ids") if isinstance(raw, dict) else raw
        self._ids = [str(item) for item in ids][: self.limit] if isinstance(ids, list) else []
        return self._ids

    @property
    def ids(self) -> list[str]:
        return list(self._ids) if self._ids else self.load()

    def record(self, school_id: str) -> list[str]:
        current = [item for item in self.ids if item != school_id]
        current.insert(0, school_id)
        self._ids = current[: self.limit]
        self._save()
        return self._ids

    def clear(self) -> None:
        self._ids = []
        self._save()

    def _save(self) -> bool:
        return write_json_atomic(
            self.path,
            {
                "updated_at": dt.datetime.now().astimezone().isoformat(
                    timespec="seconds"
                ),
                "ids": self._ids,
            },
        )
