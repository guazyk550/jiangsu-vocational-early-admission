"""``School`` 数据模型与 ``SchoolRepository`` 的测试。

核心诉求：**任何畸形数据都不能让程序崩溃**，并且坏记录要被跳过而不是拖垮整体。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.data.school_repository import (
    FILTER_ALL,
    SORT_DISTANCE,
    SORT_NAME,
    SORT_PRIVATE_FIRST,
    SORT_PUBLIC_FIRST,
    RepositoryError,
    SchoolRepository,
)
from src.models.origin import OriginPoint
from src.models.school import School

# ------------------------------------------------------------------ 模型容错
BAD_INPUTS = [
    None,
    {},
    {"name": None},
    {"name": "X", "latitude": "abc", "longitude": "118.9"},
    {"name": "X", "latitude": None, "longitude": 118.0},
    {"name": "X", "latitude": 0, "longitude": 0},
    {"name": "X", "latitude": 999, "longitude": 999},
    {"name": "X", "notes": "单个字符串"},
    {"name": "X", "notes": None, "data_year": "not-a-number"},
    {"name": "X", "early_admission_third_party": "yes"},
]


@pytest.mark.parametrize("payload", BAD_INPUTS)
def test_from_dict_never_raises(payload: object) -> None:
    school = School.from_dict(payload)  # type: ignore[arg-type]
    assert isinstance(school, School)


def test_from_dict_normalizes_values() -> None:
    school = School.from_dict(
        {
            "id": "abc",
            "name": " 测试学院 ",
            "latitude": "32.1",
            "longitude": "118.9",
            "data_year": "2026",
            "notes": ["a", "", None],
        }
    )
    assert school.name == "测试学院"
    assert school.latitude == pytest.approx(32.1)
    assert school.data_year == 2026
    assert school.notes == ["a"]
    assert school.has_coordinates


def test_from_dict_rejects_half_coordinates() -> None:
    school = School.from_dict({"name": "X", "latitude": 32.0, "longitude": None})
    assert not school.has_coordinates


def test_admission_entry_fallback_order() -> None:
    official_only = School.from_dict({"name": "X", "official_website": "https://a.cn"})
    assert official_only.admission_entry == ("https://a.cn", "打开学校官网")

    with_admission = School.from_dict(
        {"name": "X", "admission_website": "https://b.cn", "official_website": "https://a.cn"}
    )
    assert with_admission.admission_entry == ("https://b.cn", "打开招生网")

    with_early = School.from_dict(
        {
            "name": "X",
            "early_admission_url": "https://c.cn",
            "admission_website": "https://b.cn",
        }
    )
    assert with_early.admission_entry == ("https://c.cn", "提前招生简章")

    assert School.from_dict({"name": "X"}).admission_entry == ("", "暂无官网链接")


def test_third_party_url_is_not_treated_as_official() -> None:
    school = School.from_dict(
        {
            "name": "X",
            "early_admission_url": "https://third-party.example.com/a.html",
            "early_admission_third_party": True,
            "admission_website": "https://official.example.edu.cn/",
        }
    )
    assert school.has_early_admission_reference
    assert not school.has_official_early_admission_page
    # 第三方链接不能冒充官方入口，按钮应回退到招生网
    assert school.admission_entry == ("https://official.example.edu.cn/", "打开招生网")


def test_search_blob_contains_key_fields() -> None:
    school = School.from_dict(
        {"name": "南京铁道职业技术学院", "short_name": "南京铁道学院", "city": "南京", "ownership": "公办"}
    )
    blob = school.search_blob()
    for token in ("南京铁道职业技术学院", "南京铁道学院", "南京", "公办"):
        assert token in blob


# ------------------------------------------------------------------ 仓储
def make_repo(tmp_path: Path, schools: list[dict], meta: dict | None = None) -> SchoolRepository:
    path = tmp_path / "schools.json"
    path.write_text(
        json.dumps({"meta": meta or {"data_year": 2026}, "schools": schools}, ensure_ascii=False),
        encoding="utf-8",
    )
    return SchoolRepository(path)


SAMPLE = [
    {"id": "a", "name": "南京甲学院", "city": "南京", "ownership": "公办", "latitude": 32.0, "longitude": 118.8},
    {"id": "b", "name": "苏州乙学院", "city": "苏州", "ownership": "民办", "latitude": 31.3, "longitude": 120.6},
    {"id": "c", "name": "南京丙学院", "city": "南京", "ownership": "民办"},
]


def test_repository_keeps_file_order_until_sorted(tmp_path: Path) -> None:
    """load() 尊重数据文件顺序；query() 才负责默认排序（城市→校名）。"""
    repo = make_repo(tmp_path, SAMPLE)
    loaded = repo.load()
    assert [s.name for s in loaded.schools] == ["南京甲学院", "苏州乙学院", "南京丙学院"]
    assert loaded.data_year == 2026
    assert loaded.cities == ["南京", "苏州"]
    assert [s.name for s in repo.query(loaded.schools)] == [
        "南京丙学院",
        "南京甲学院",
        "苏州乙学院",
    ]


def test_repository_skips_bad_records(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path,
        [*SAMPLE, "not-an-object", {"city": "常州"}, {"id": "a", "name": "重复项"}],
    )
    loaded = repo.load()
    assert len(loaded.schools) == 3  # 非对象、缺校名、重复 id 都被跳过
    assert any("已跳过" in w for w in loaded.warnings)


def test_repository_raises_when_nothing_usable(tmp_path: Path) -> None:
    path = tmp_path / "schools.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(RepositoryError):
        SchoolRepository(path).load()


def test_repository_accepts_bare_array(tmp_path: Path) -> None:
    path = tmp_path / "schools.json"
    path.write_text(json.dumps(SAMPLE, ensure_ascii=False), encoding="utf-8")
    assert len(SchoolRepository(path).load().schools) == 3


def test_query_keyword_matches_name_city_and_ownership(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, SAMPLE)
    schools = repo.load().schools
    assert {s.name for s in repo.query(schools, keyword="南京")} == {"南京甲学院", "南京丙学院"}
    assert {s.name for s in repo.query(schools, keyword="民办")} == {"苏州乙学院", "南京丙学院"}
    assert [s.name for s in repo.query(schools, keyword="乙")] == ["苏州乙学院"]
    assert repo.query(schools, keyword="不存在") == []


def test_query_filters_and_multiple_keywords(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, SAMPLE)
    schools = repo.load().schools
    assert len(repo.query(schools, city="南京")) == 2
    assert [s.name for s in repo.query(schools, city="南京", ownership="民办")] == ["南京丙学院"]
    # 多个关键词按 AND 匹配
    assert [s.name for s in repo.query(schools, keyword="南京 民办")] == ["南京丙学院"]
    assert len(repo.query(schools, city=FILTER_ALL, ownership=FILTER_ALL)) == 3


def test_sort_modes(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, SAMPLE)
    schools = repo.load().schools

    assert [s.name for s in repo.query(schools, sort=SORT_NAME)] == [
        "南京丙学院",
        "南京甲学院",
        "苏州乙学院",
    ]
    # 有距离的排前面，缺距离的排最后
    distances = {"b": 10.0, "a": 200.0}
    assert [s.name for s in repo.query(schools, sort=SORT_DISTANCE, distances=distances)] == [
        "苏州乙学院",
        "南京甲学院",
        "南京丙学院",
    ]
    assert repo.query(schools, sort=SORT_PUBLIC_FIRST)[0].ownership == "公办"
    assert repo.query(schools, sort=SORT_PRIVATE_FIRST)[0].ownership == "民办"


def test_sort_distance_without_distances_does_not_crash(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, SAMPLE)
    result = repo.query(repo.load().schools, sort=SORT_DISTANCE)
    assert len(result) == 3


def test_origin_point_defaults_and_overrides() -> None:
    default = OriginPoint()
    assert default.has_coordinates
    assert default.name == "常州武进洛阳高级中学"

    custom = OriginPoint.from_dict({"name": "自定中学", "latitude": "31.1", "longitude": "120.2"})
    assert custom.name == "自定中学"
    assert custom.has_coordinates

    broken = OriginPoint.from_dict({"name": "无坐标", "latitude": "x", "longitude": None})
    assert not broken.has_coordinates
    assert OriginPoint.from_dict(None).has_coordinates  # 非 dict 输入回落默认值
