"""配置读写（``data/config.json``）。

配置项
------
- ``origin``：距离/导航的**固定参照点**（默认常州武进洛阳高级中学），可修改；
- ``update_url``：数据更新地址；**留空则完全不发起网络请求**；
- ``last_update_check``：上次检查更新的时间（展示用）；
- ``sort`` / ``window``：界面偏好。

容错原则：配置文件损坏或字段缺失时使用默认值继续运行，并把坏文件备份为 ``.bak``，
不让用户因为一个配置错误就无法启动软件。
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from src.data.school_repository import project_root
from src.models.origin import OriginPoint
from src.services.storage import read_json, write_json_atomic

CONFIG_FILENAME = "config.json"
DEFAULT_SORT = "default"


@dataclass(slots=True)
class AppConfig:
    """应用配置。"""

    origin: OriginPoint = field(default_factory=OriginPoint)
    update_url: str = ""
    last_update_check: str = ""
    last_update_result: str = ""
    sort: str = DEFAULT_SORT
    window_geometry: str = ""
    data_year: int = 0

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> "AppConfig":
        if not isinstance(raw, Mapping):
            return cls()
        return cls(
            origin=OriginPoint.from_dict(raw.get("origin")),
            update_url=str(raw.get("update_url") or "").strip(),
            last_update_check=str(raw.get("last_update_check") or ""),
            last_update_result=str(raw.get("last_update_result") or ""),
            sort=str(raw.get("sort") or DEFAULT_SORT),
            window_geometry=str(raw.get("window_geometry") or ""),
            data_year=int(raw.get("data_year") or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "origin": self.origin.to_dict(),
            "update_url": self.update_url,
            "last_update_check": self.last_update_check,
            "last_update_result": self.last_update_result,
            "sort": self.sort,
            "window_geometry": self.window_geometry,
            "data_year": self.data_year,
        }


class ConfigService:
    """加载/保存配置。"""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (project_root() / "data" / CONFIG_FILENAME)
        self._config: AppConfig | None = None

    def load(self, *, force: bool = False) -> AppConfig:
        if self._config is not None and not force:
            return self._config
        raw = read_json(self.path, default=None)
        if raw is None:
            # 首次运行：生成带默认值的配置文件，方便用户修改参照点
            config = AppConfig()
            self.save(config)
        else:
            config = AppConfig.from_dict(raw)
        self._config = config
        return config

    def save(self, config: AppConfig | None = None) -> bool:
        target = config or self._config or AppConfig()
        self._config = target
        return write_json_atomic(self.path, target.to_dict())

    # -------------------------------------------------------------- 便捷更新
    def update_origin(self, origin: OriginPoint) -> bool:
        config = self.load()
        config.origin = origin
        return self.save(config)

    def mark_update_checked(self, result: str) -> bool:
        config = self.load()
        config.last_update_check = dt.datetime.now().astimezone().isoformat(
            timespec="seconds"
        )
        config.last_update_result = result
        return self.save(config)

    def set_sort(self, sort: str) -> bool:
        config = self.load()
        config.sort = sort
        return self.save(config)
