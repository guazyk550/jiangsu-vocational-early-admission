"""距离 / 地图 / 浏览器三个服务的测试。

重点：Haversine 精度、URL 编码正确性（中文/空格/括号）、以及各种失败情形
（无坐标、非法 URL、opener 抛异常）都必须安全降级。
"""

from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlparse

import pytest

from src.models.origin import OriginPoint
from src.models.school import School
from src.services.browser_service import BrowserService, is_openable_url
from src.services.distance_service import (
    EARTH_RADIUS_KM,
    DistanceService,
    format_km,
    haversine_distance,
)
from src.services.map_service import MapService

LUOYANG = OriginPoint()
NANJING = (32.0640583, 118.9149113)


# ------------------------------------------------------------------ Haversine
def test_haversine_known_distances() -> None:
    # 北京 → 上海 约 1067 km
    assert haversine_distance(39.9042, 116.4074, 31.2304, 121.4737) == pytest.approx(1067, abs=5)
    # 同一点为 0
    assert haversine_distance(32.0, 118.0, 32.0, 118.0) == pytest.approx(0, abs=1e-9)
    # 沿经线每 1 度纬度 ≈ 111.19 km
    assert haversine_distance(32.0, 118.0, 33.0, 118.0) == pytest.approx(
        EARTH_RADIUS_KM * 3.141592653589793 / 180, rel=1e-6
    )


def test_haversine_is_symmetric() -> None:
    a = haversine_distance(31.0, 120.0, 34.0, 118.0)
    b = haversine_distance(34.0, 118.0, 31.0, 120.0)
    assert a == pytest.approx(b)


def test_format_km_keeps_one_decimal() -> None:
    assert format_km(42.66) == "42.7"
    assert format_km(5) == "5.0"


# -------------------------------------------------------------- DistanceService
def test_distance_service_with_coordinates() -> None:
    service = DistanceService(LUOYANG)
    school = School.from_dict(
        {"name": "南京某学院", "latitude": NANJING[0], "longitude": NANJING[1]}
    )
    distance = service.distance_km(school)
    assert distance is not None and distance > 0
    assert "直线距离" in service.describe(school)
    assert LUOYANG.name in service.describe(school)


def test_distance_service_without_coordinates() -> None:
    service = DistanceService(LUOYANG)
    school = School.from_dict({"name": "无坐标学院"})
    assert service.distance_km(school) is None
    assert service.describe(school) == "暂无距离数据（该校坐标缺失）"
    assert service.distance_map([school]) == {}


def test_distance_service_without_origin_coordinates() -> None:
    service = DistanceService(OriginPoint.from_dict({"name": "无坐标点"}))
    school = School.from_dict({"name": "X", "latitude": 32.0, "longitude": 118.0})
    assert service.distance_km(school) is None
    assert "参照点坐标缺失" in service.describe(school)


def test_distance_map_and_format_map() -> None:
    service = DistanceService(LUOYANG)
    with_coords = School.from_dict({"id": "a", "name": "A", "latitude": 31.6, "longitude": 120.0})
    without = School.from_dict({"id": "b", "name": "B"})
    distance_map = service.distance_map([with_coords, without])
    assert set(distance_map) == {"a"}
    assert service.format_map([with_coords]) == {"a": f"{format_km(distance_map['a'])} km"}


# ------------------------------------------------------------------ 地图 URL
def test_direction_url_uses_coordinates_and_encodes_text() -> None:
    service = MapService(LUOYANG)
    school = School.from_dict(
        {
            "name": "江苏经贸职业技术学院",
            "latitude": 31.9338603,
            "longitude": 118.8794686,
            "address": "南京市江宁区（龙眠大道）629号",
        }
    )
    url = service.direction_url(school)
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "api.map.baidu.com"

    query = parse_qs(parsed.query)
    assert query["mode"] == ["driving"]
    assert query["output"] == ["html"]
    # 中文名称必须以百分号编码出现，且解码后名称完整
    assert "%" in url
    assert "江苏经贸职业技术学院" in unquote(url)
    assert query["origin"][0].startswith("latlng:31.6467631,120.082389")
    assert query["destination"][0].startswith("latlng:31.9338603,118.8794686")
    # 原始 URL 中不能出现未编码的中文或空格
    assert " " not in url
    for char in ("（", "）", "江", "苏"):
        assert char not in url


def test_direction_url_falls_back_to_text_when_no_coordinates() -> None:
    service = MapService(LUOYANG)
    school = School.from_dict({"name": "无名学院"})
    url = service.direction_url(school)
    query = parse_qs(urlparse(url).query)
    assert query["destination"][0] == "%E6%97%A0%E5%90%8D%E5%AD%A6%E9%99%A2" or unquote(
        query["destination"][0]
    ) == "无名学院"
    assert "latlng:" not in query["destination"][0]


def test_search_url_contains_encoded_keyword() -> None:
    service = MapService(LUOYANG)
    school = School.from_dict({"name": "苏州某学院", "address": "苏州市（吴中区）1 号"})
    url = service.search_url(school)
    assert url.startswith("https://map.baidu.com/search/")
    assert "苏州某学院" in unquote(url)
    assert " " not in url


def test_direction_falls_back_to_search_when_opening_fails() -> None:
    opened: list[str] = []

    def opener(url: str) -> bool:
        opened.append(url)
        return "map.baidu.com/search" in url  # 路线接口失败，搜索页成功

    browser = BrowserService(opener=opener)
    service = MapService(LUOYANG, browser=browser)
    school = School.from_dict({"name": "X", "latitude": 31.0, "longitude": 120.0})
    outcome = service.open_directions(school)
    assert outcome.ok
    assert len(opened) == 2
    assert "api.map.baidu.com/direction" in opened[0]


# ---------------------------------------------------------------- 浏览器服务
def test_is_openable_url_rules() -> None:
    assert is_openable_url("https://www.jseea.cn/")
    assert is_openable_url("http://example.com/a?b=1")
    assert not is_openable_url("")
    assert not is_openable_url(None)
    assert not is_openable_url("javascript:void(0)")
    assert not is_openable_url("file:///C:/Windows/system32/calc.exe")
    assert not is_openable_url("https://")
    assert not is_openable_url("关于我们")


def test_browser_service_rejects_unsafe_scheme() -> None:
    calls: list[str] = []
    service = BrowserService(opener=lambda url: calls.append(url) or True)
    outcome = service.open("file:///C:/secret.txt")
    assert outcome.failed
    assert calls == []  # 危险协议根本不会被交给系统浏览器


def test_browser_service_handles_opener_failure_and_exception() -> None:
    service = BrowserService(opener=lambda url: False)
    outcome = service.open("https://down.example.com/")
    assert outcome.failed and "无法访问" in outcome.message

    def boom(url: str) -> bool:
        raise RuntimeError("boom")

    outcome = BrowserService(opener=boom).open("https://boom.example.com/")
    assert outcome.failed and "boom" in outcome.message


def test_browser_service_open_first_skips_empty_and_unsafe() -> None:
    opened: list[str] = []
    service = BrowserService(opener=lambda url: opened.append(url) or True)
    outcome = service.open_first(["", "javascript:void(0)", "https://ok.example.com/"])
    assert outcome.ok
    assert opened == ["https://ok.example.com/"]
