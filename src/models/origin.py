"""固定参照点（默认：常州武进洛阳高级中学）。

为什么单独建模
--------------
用户要看到「学校 → 洛阳高级中学」的**直线距离**，并据此排序。参照点需要：
1. 可配置（用户可改成自己关心的学校）；
2. 保存坐标以免每次都靠文字搜索（坐标缺失时距离功能自动降级为「暂无距离数据」）；
3. 记录坐标来源，明确它不是官方数据。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

DEFAULT_ORIGIN_NAME = "常州武进洛阳高级中学"
DEFAULT_ORIGIN_ADDRESS = "江苏省常州市武进区洛阳镇"
#: 来自 OpenStreetMap（Photon 反查，OSM way 863559198），**非官方数据**
DEFAULT_ORIGIN_LATITUDE = 31.6467631
DEFAULT_ORIGIN_LONGITUDE = 120.082389
DEFAULT_ORIGIN_SOURCE = (
    "OpenStreetMap（Photon 查询『武进区洛阳高级中学』命中 OSM way 863559198，非官方数据）"
)


def _as_float(value: Any) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number


@dataclass(frozen=True, slots=True)
class OriginPoint:
    """距离计算/地图导航的起点。"""

    name: str = DEFAULT_ORIGIN_NAME
    address: str = DEFAULT_ORIGIN_ADDRESS
    latitude: float | None = DEFAULT_ORIGIN_LATITUDE
    longitude: float | None = DEFAULT_ORIGIN_LONGITUDE
    source: str = DEFAULT_ORIGIN_SOURCE

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> "OriginPoint":
        """从配置字典构造；缺字段时回落到内置默认值。"""
        if not isinstance(raw, Mapping):
            return cls()
        latitude = _as_float(raw.get("latitude"))
        longitude = _as_float(raw.get("longitude"))
        if latitude is None or longitude is None:
            latitude, longitude = None, None
        return cls(
            name=str(raw.get("name") or DEFAULT_ORIGIN_NAME).strip(),
            address=str(raw.get("address") or "").strip(),
            latitude=latitude,
            longitude=longitude,
            source=str(raw.get("source") or "").strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "address": self.address,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "source": self.source,
        }

    @property
    def coord_text(self) -> str:
        """百度等地图 URI 需要的 ``经度,纬度`` 之外的 ``纬度,经度`` 文本。"""
        if not self.has_coordinates:
            return ""
        return f"{self.latitude},{self.longitude}"
