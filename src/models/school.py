"""院校数据模型。

设计要点
--------
1. **完全容错**：``data/schools.json`` 是外部可编辑文件，可能缺字段、写错类型、
   填 null。``School.from_dict`` 对任何输入都返回一个可用的对象，绝不抛异常
   （用户要求：一个学校的数据错误不能让整个程序崩溃）。
2. **不可变**：``frozen`` + ``slots``，避免 UI 层意外修改数据。
3. **不猜数据**：缺失值保持 ``None`` / 空串，由 UI 决定如何展示「暂无数据」。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

#: 办学性质取值（UI 筛选只有公办/民办两类，中外合作办学归入民办组）
OWNERSHIP_PUBLIC = "公办"
OWNERSHIP_PRIVATE = "民办"
VALID_OWNERSHIPS = (OWNERSHIP_PUBLIC, OWNERSHIP_PRIVATE)

#: 提前招生入口的置信度等级
CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"
CONFIDENCE_NONE = "none"


def _as_str(value: Any) -> str:
    """任意值 → 去空白字符串；None / 容器 → 空串。"""
    if value is None or isinstance(value, (list, dict, tuple, set)):
        return ""
    return str(value).strip()


def _as_float(value: Any) -> float | None:
    """任意值 → float；无法转换或超出合理经纬度范围 → None。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _as_str(value).lower() in ("1", "true", "yes", "y", "是")


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [text for item in value if (text := _as_str(item))]
    return []


@dataclass(frozen=True, slots=True)
class School:
    """一所院校的全部展示信息。"""

    id: str = ""
    name: str = ""
    short_name: str = ""
    city: str = ""
    district: str = ""
    ownership: str = ""
    ownership_note: str = ""
    school_type: str = "高职专科"
    official_website: str = ""
    admission_website: str = ""
    early_admission_url: str = ""
    early_admission_title: str = ""
    early_admission_year: int | None = None
    early_admission_confidence: str = CONFIDENCE_NONE
    early_admission_third_party: bool = False
    early_admission_evidence: str = ""
    address: str = ""
    latitude: float | None = None
    longitude: float | None = None
    coord_confidence: str = CONFIDENCE_NONE
    coord_matched_name: str = ""
    data_year: int = 0
    last_verified: str = ""
    source_url: str = ""
    notes: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ 构造
    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> "School":
        """从字典构造，任何异常输入都能得到一个可用对象。"""
        if not isinstance(raw, Mapping):
            raw = {}

        latitude = _as_float(raw.get("latitude"))
        longitude = _as_float(raw.get("longitude"))
        # 经纬度必须成对且落在合理范围内，否则视为无坐标
        if (
            latitude is None
            or longitude is None
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
            or (latitude == 0 and longitude == 0)
        ):
            latitude = longitude = None

        name = _as_str(raw.get("name"))
        school_id = _as_str(raw.get("id")) or name

        return cls(
            id=school_id,
            name=name,
            short_name=_as_str(raw.get("short_name")) or name,
            city=_as_str(raw.get("city")),
            district=_as_str(raw.get("district")),
            ownership=_as_str(raw.get("ownership")),
            ownership_note=_as_str(raw.get("ownership_note")),
            school_type=_as_str(raw.get("school_type")) or "高职专科",
            official_website=_as_str(raw.get("official_website")),
            admission_website=_as_str(raw.get("admission_website")),
            early_admission_url=_as_str(raw.get("early_admission_url")),
            early_admission_title=_as_str(raw.get("early_admission_title")),
            early_admission_year=_as_int(raw.get("early_admission_year")),
            early_admission_confidence=_as_str(
                raw.get("early_admission_confidence")
            )
            or CONFIDENCE_NONE,
            early_admission_third_party=_as_bool(
                raw.get("early_admission_third_party")
            ),
            early_admission_evidence=_as_str(raw.get("early_admission_evidence")),
            address=_as_str(raw.get("address")),
            latitude=latitude,
            longitude=longitude,
            coord_confidence=_as_str(raw.get("coord_confidence")) or CONFIDENCE_NONE,
            coord_matched_name=_as_str(raw.get("coord_matched_name")),
            data_year=_as_int(raw.get("data_year")) or 0,
            last_verified=_as_str(raw.get("last_verified")),
            source_url=_as_str(raw.get("source_url")),
            notes=_as_str_list(raw.get("notes")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "short_name": self.short_name,
            "city": self.city,
            "district": self.district,
            "ownership": self.ownership,
            "ownership_note": self.ownership_note,
            "school_type": self.school_type,
            "official_website": self.official_website,
            "admission_website": self.admission_website,
            "early_admission_url": self.early_admission_url,
            "early_admission_title": self.early_admission_title,
            "early_admission_year": self.early_admission_year,
            "early_admission_confidence": self.early_admission_confidence,
            "early_admission_third_party": self.early_admission_third_party,
            "early_admission_evidence": self.early_admission_evidence,
            "address": self.address,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "coord_confidence": self.coord_confidence,
            "coord_matched_name": self.coord_matched_name,
            "data_year": self.data_year,
            "last_verified": self.last_verified,
            "source_url": self.source_url,
            "notes": list(self.notes),
        }

    # ------------------------------------------------------------- 派生属性
    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def has_official_early_admission_page(self) -> bool:
        """是否有**学校自有域名**的提前招生页面（第三方转载不算）。"""
        return bool(self.early_admission_url) and not self.early_admission_third_party

    @property
    def admission_entry(self) -> tuple[str, str]:
        """返回「提前招生/招生」按钮应打开的 (url, 按钮文案)。

        优先级：提前招生页面（自有域名）→ 招生网 → 官网；都没有则返回空。
        """
        if self.has_official_early_admission_page:
            return self.early_admission_url, "打开提前招生官网"
        if self.admission_website:
            return self.admission_website, "打开学校招生官网"
        if self.official_website:
            return self.official_website, "打开学校官网"
        return "", "暂无官网链接"

    @property
    def has_early_admission_reference(self) -> bool:
        """是否存在（第三方转载的）简章参考链接。"""
        return bool(self.early_admission_url) and self.early_admission_third_party

    def search_blob(self) -> str:
        """搜索用文本：校名 + 简称 + 城市 + 区县 + 办学性质 + 类型 + 地址。"""
        return " ".join(
            filter(
                None,
                [
                    self.name,
                    self.short_name,
                    self.city,
                    self.district,
                    self.ownership,
                    self.ownership_note,
                    self.school_type,
                    self.address,
                ],
            )
        )
