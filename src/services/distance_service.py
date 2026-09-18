"""直线距离计算（Haversine）。

⚠️ 只计算**直线距离**（大圆距离）。道路距离（驾车距离）不能用直线距离代替，
必须交给地图服务，UI 上两者要区分显示。
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Iterable, Mapping

from src.models.origin import OriginPoint
from src.models.school import School

#: WGS84 平均地球半径（公里）
EARTH_RADIUS_KM = 6371.0088


def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """返回两点间大圆距离，单位公里（不做四舍五入，由调用方决定精度）。"""
    phi1, lambda1, phi2, lambda2 = (
        radians(lat1),
        radians(lon1),
        radians(lat2),
        radians(lon2),
    )
    delta_phi = phi2 - phi1
    delta_lambda = lambda2 - lambda1
    a = (
        sin(delta_phi / 2) ** 2
        + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * asin(sqrt(min(1.0, a)))


def format_km(kilometers: float) -> str:
    """格式化为一位小数，如 ``42.7``。"""
    return f"{kilometers:.1f}"


class DistanceService:
    """以某个固定参照点计算各院校的直线距离。"""

    def __init__(self, origin: OriginPoint | None = None) -> None:
        self.origin = origin

    # ------------------------------------------------------------------ 单点
    def distance_km(self, school: School) -> float | None:
        """院校到参照点的直线距离（公里）；任一端缺坐标则返回 None。"""
        if self.origin is None or not self.origin.has_coordinates:
            return None
        if not school.has_coordinates:
            return None
        assert school.latitude is not None and school.longitude is not None
        assert self.origin.latitude is not None and self.origin.longitude is not None
        return haversine_distance(
            school.latitude,
            school.longitude,
            self.origin.latitude,
            self.origin.longitude,
        )

    def describe(self, school: School) -> str:
        """给 UI 用的整句描述。"""
        if self.origin is None:
            return "暂无距离数据"
        if not self.origin.has_coordinates:
            return "暂无距离数据（参照点坐标缺失）"
        if not school.has_coordinates:
            return "暂无距离数据（该校坐标缺失）"
        distance = self.distance_km(school)
        if distance is None:
            return "暂无距离数据"
        return f"距离{self.origin.name}约 {format_km(distance)} km（直线距离）"

    # ------------------------------------------------------------------ 批量
    def distance_map(self, schools: Iterable[School]) -> dict[str, float]:
        """``{school.id: 公里数}``，供「距离最近」排序使用（缺坐标的不计入）。"""
        result: dict[str, float] = {}
        for school in schools:
            distance = self.distance_km(school)
            if distance is not None:
                result[school.id] = distance
        return result

    def format_map(self, schools: Iterable[School]) -> Mapping[str, str]:
        """``{school.id: "38.6 km"}``，供列表卡片直接展示。"""
        return {
            school.id: f"{format_km(distance)} km"
            for school in schools
            if (distance := self.distance_km(school)) is not None
        }
