"""需求中的 8 项验收测试（全部在 offscreen 模式下运行，可重复执行）。

1. 搜索「南京」→ 只显示南京院校
2. 筛选「民办」→ 只显示民办院校
3. 点击「打开提前招生官网」→ 用正确 URL 唤起浏览器
4. 点击「百度地图」→ 打开百度地图驾车路线（起点=参照点，终点=该校）
5. 距离能正常显示（直线距离）
6. 学校没有提前招生页面时 → 回退「打开招生网」，而不是报错
7. 断网启动 → 仍显示本地数据
8. 删除/改坏某校 URL → 程序不崩溃
"""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from src.data.school_repository import SchoolRepository  # noqa: E402
from src.models.school import School  # noqa: E402
from src.services.browser_service import BrowserService  # noqa: E402
from src.services.config_service import ConfigService  # noqa: E402
from src.services.favorites_service import FavoritesService, RecentService  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402
from src.ui.school_card import SchoolCard  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])  # type: ignore[return-value]


class Recorder:
    """记录被打开的 URL，并可模拟打开失败。"""

    def __init__(self, fail: bool = False) -> None:
        self.urls: list[str] = []
        self.fail = fail

    def __call__(self, url: str) -> bool:
        self.urls.append(url)
        return not self.fail


def build_window(
    qapp: QApplication,
    tmp_path: Path,
    *,
    data_file: Path | None = None,
    opener: Recorder | None = None,
) -> tuple[MainWindow, Recorder]:
    recorder = opener or Recorder()
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    if data_file is not None:
        (data_dir / "schools.json").write_text(
            json.dumps(data_file, ensure_ascii=False), encoding="utf-8"
        )
    repository = SchoolRepository(data_dir / "schools.json")
    config = ConfigService(tmp_path / "config.json")
    window = MainWindow(
        repository,
        config,
        favorites=FavoritesService(tmp_path / "favorites.json"),
        recent=RecentService(tmp_path / "recent.json"),
        browser_service=BrowserService(opener=recorder),
    )
    return window, recorder


def cards(window: MainWindow) -> list[SchoolCard]:
    return [c for c in window._cards if isinstance(c, SchoolCard)]  # noqa: SLF001


def real_dataset() -> dict:
    path = Path(__file__).resolve().parents[1] / "data" / "schools.json"
    return json.loads(path.read_text(encoding="utf-8"))


# =============================================================== 测试 1
def test_1_search_nanjing(qapp: QApplication, tmp_path: Path) -> None:
    window, _ = build_window(qapp, tmp_path, data_file=real_dataset())
    window.search_edit.setText("南京")
    window._refresh_cards()  # noqa: SLF001

    shown = cards(window)
    assert shown, "搜索南京不应为空"
    assert all(c.school.city == "南京" for c in shown)
    assert len(shown) == 15


# =============================================================== 测试 2
def test_2_filter_private_only(qapp: QApplication, tmp_path: Path) -> None:
    window, _ = build_window(qapp, tmp_path, data_file=real_dataset())
    window.ownership_combo.setCurrentText("民办")
    window._refresh_cards()  # noqa: SLF001

    shown = cards(window)
    assert shown
    assert all(c.school.ownership == "民办" for c in shown)
    assert len(shown) == 22


# =============================================================== 测试 3
def test_3_open_early_admission_page(qapp: QApplication, tmp_path: Path) -> None:
    window, recorder = build_window(qapp, tmp_path, data_file=real_dataset())
    school = next(
        c.school for c in cards(window) if c.school.has_official_early_admission_page
    )
    window._open_admission(school)  # noqa: SLF001

    assert recorder.urls == [school.early_admission_url]
    assert recorder.urls[0].startswith("http")


# =============================================================== 测试 4
def test_4_open_baidu_map_driving_route(qapp: QApplication, tmp_path: Path) -> None:
    window, recorder = build_window(qapp, tmp_path, data_file=real_dataset())
    # 选一所有坐标的院校，验证会生成精确的 latlng 参数
    school = next(c.school for c in cards(window) if c.school.has_coordinates)
    window._open_map(school)  # noqa: SLF001

    assert recorder.urls, "应调用浏览器打开地图"
    url = recorder.urls[0]
    assert url.startswith("https://api.map.baidu.com/direction?")
    from urllib.parse import unquote

    decoded = unquote(url)
    assert "origin=latlng:31.6467631,120.082389|name:常州武进洛阳高级中学" in decoded
    assert f"destination=latlng:{school.latitude},{school.longitude}" in decoded
    assert "mode=driving" in decoded


def test_4b_open_baidu_map_without_coordinates_uses_text(
    qapp: QApplication, tmp_path: Path
) -> None:
    """缺坐标的院校：地图仍可用，只是终点退化为文字名称。"""
    window, recorder = build_window(qapp, tmp_path, data_file=real_dataset())
    school = next(c.school for c in cards(window) if not c.school.has_coordinates)
    window._open_map(school)  # noqa: SLF001

    from urllib.parse import unquote

    decoded = unquote(recorder.urls[0])
    assert f"destination={school.name}" in decoded
    assert "mode=driving" in decoded


# =============================================================== 测试 5
def test_5_distance_is_displayed(qapp: QApplication, tmp_path: Path) -> None:
    window, _ = build_window(qapp, tmp_path, data_file=real_dataset())
    window.sort_combo.setCurrentIndex(2)  # 距离最近
    window._refresh_cards()  # noqa: SLF001

    shown = cards(window)
    nearest = shown[0]
    assert nearest.school.has_coordinates

    text = window.distance_service.describe(nearest.school)
    assert "km" in text and "直线距离" in text

    # 卡片上确实渲染了距离文本
    from PySide6.QtWidgets import QLabel

    labels = [l.text() for l in nearest.findChildren(QLabel) if l.objectName() == "CardDistance"]
    assert labels and labels[0].endswith("km")


# =============================================================== 测试 6
def test_6_falls_back_to_admission_site_without_early_admission_page(
    qapp: QApplication, tmp_path: Path
) -> None:
    dataset = {
        "meta": {"data_year": 2026},
        "schools": [
            {
                "id": "no-early",
                "name": "测试无提前招生页学院",
                "city": "常州",
                "ownership": "公办",
                "official_website": "https://official.example.edu.cn/",
                "admission_website": "https://zs.example.edu.cn/",
                "early_admission_url": None,
                "latitude": 31.7,
                "longitude": 120.0,
                "data_year": 2026,
            }
        ],
    }
    window, recorder = build_window(qapp, tmp_path, data_file=dataset)
    school = cards(window)[0].school

    assert school.admission_entry == ("https://zs.example.edu.cn/", "打开学校招生官网")
    window._open_admission(school)  # noqa: SLF001
    assert recorder.urls == ["https://zs.example.edu.cn/"]


# =============================================================== 测试 7
def test_7_offline_startup_still_shows_local_data(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def deny(*args: object, **kwargs: object) -> None:
        raise OSError("网络已断开（测试模拟）")

    # 拦截所有 TCP 连接，模拟断网
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)

    window, _ = build_window(qapp, tmp_path, data_file=real_dataset())
    shown = cards(window)
    assert len(shown) == 84, "断网也必须能显示本地数据"
    # update_url 为空 → 启动时不应发起任何检查
    assert window.config_service.load().update_url == ""
    assert window._update_worker is None  # noqa: SLF001


# =============================================================== 测试 8
def test_8_broken_school_url_does_not_crash(qapp: QApplication, tmp_path: Path) -> None:
    dataset = {
        "meta": {"data_year": 2026},
        "schools": [
            {
                "id": "broken-url",
                "name": "URL乱码学院",
                "city": "苏州",
                "ownership": "民办",
                "official_website": "这不是一个网址",
                "admission_website": "javascript:alert(1)",
                "early_admission_url": "ht!tp://broken url",
                "latitude": "不是数字",
                "longitude": None,
            },
            {
                "id": "deleted-url",
                "name": "URL被删学院",
                "city": "无锡",
                "ownership": "公办",
                "official_website": "",
                "admission_website": None,
                "early_admission_url": None,
            },
        ],
    }
    window, recorder = build_window(qapp, tmp_path, data_file=dataset)

    shown = cards(window)
    assert len(shown) == 2, "坏 URL 不应导致记录被丢弃"

    for card in shown:
        school = card.school
        # 非法协议不会被交给系统浏览器
        outcome = window.browser_service.open(school.admission_entry[0])
        assert outcome.ok is False or recorder.urls == []

    # 无任何链接的院校：按钮应被禁用而不是崩溃
    broken_card = next(c for c in shown if c.school.id == "deleted-url")
    assert broken_card.school.admission_entry == ("", "暂无官网链接")

    # 距离计算也要能扛住非法坐标
    assert window.distance_service.describe(shown[0].school) in (
        "暂无距离数据（该校坐标缺失）",
        "暂无距离数据",
    )


# =============================================================== 附加
def test_dataset_loads_without_repository_error(tmp_path: Path) -> None:
    repo = SchoolRepository(
        Path(__file__).resolve().parents[1] / "data" / "schools.json"
    )
    loaded = repo.load()
    assert len(loaded.schools) == 84
    assert loaded.data_year == 2026
