"""院校数据仓储：加载、校验、查询。

数据查找顺序（保证「只更新 JSON、不重新打包程序」可用）
------------------------------------------------------
1. 环境变量 ``JSVOC_DATA_DIR`` 指定的目录（便于测试与高级用户）
2. **exe / 项目根目录同级的 ``data/schools.json``**（用户可直接替换）
3. 打包进 exe 的内置资源 ``sys._MEIPASS/data/schools.json``（保底）

前一个位置的数据文件若缺失/损坏/为空，自动降级到下一个，并记录 warning，
**不会因为数据问题阻止程序启动**。
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.models.school import (
    CONFIDENCE_HIGH,
    OWNERSHIP_PRIVATE,
    OWNERSHIP_PUBLIC,
    School,
)

#: 排序方式（UI 下拉框）
SORT_DEFAULT = "default"
SORT_NAME = "name"
SORT_DISTANCE = "distance"
SORT_PUBLIC_FIRST = "public_first"
SORT_PRIVATE_FIRST = "private_first"

SORT_LABELS: tuple[tuple[str, str], ...] = (
    (SORT_DEFAULT, "默认（城市→校名）"),
    (SORT_NAME, "A-Z 校名"),
    (SORT_DISTANCE, "距离最近"),
    (SORT_PUBLIC_FIRST, "公办优先"),
    (SORT_PRIVATE_FIRST, "民办优先"),
)

#: 「全部」在筛选框中的占位值
FILTER_ALL = "全部"


class RepositoryError(RuntimeError):
    """数据完全不可用（所有候选数据源都失败）。"""


@dataclass(frozen=True, slots=True)
class LoadResult:
    """一次加载的结果（含诊断信息，供 UI 展示数据来源与警告）。"""

    schools: tuple[School, ...]
    meta: Mapping[str, Any]
    source_path: str
    warnings: tuple[str, ...]

    @property
    def data_year(self) -> int:
        try:
            return int(self.meta.get("data_year") or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def last_verified(self) -> str:
        return str(self.meta.get("last_verified") or self.meta.get("generated_at") or "")

    @property
    def cities(self) -> list[str]:
        """出现过的城市（按院校数量降序），用于城市筛选框。"""
        counter: dict[str, int] = {}
        for school in self.schools:
            if school.city:
                counter[school.city] = counter.get(school.city, 0) + 1
        return [city for city, _ in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))]


def project_root() -> Path:
    """项目根目录（源码运行时）或 exe 所在目录（打包后）。"""
    if getattr(sys, "frozen", False):  # PyInstaller 打包后
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def candidate_data_files(filename: str = "schools.json") -> list[Path]:
    """按优先级列出可能的数据文件位置。"""
    candidates: list[Path] = []

    env_dir = os.environ.get("JSVOC_DATA_DIR")
    if env_dir:
        candidates.append(Path(env_dir) / filename)

    candidates.append(project_root() / "data" / filename)

    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        candidates.append(Path(bundle_dir) / "data" / filename)

    # 去重但保持顺序
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        resolved = path.resolve() if path.exists() else path
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique


class SchoolRepository:
    """加载并查询院校数据。"""

    def __init__(self, data_file: Path | None = None) -> None:
        self._explicit_file = data_file
        self._result: LoadResult | None = None

    # ------------------------------------------------------------------ 加载
    def load(self, *, force: bool = False) -> LoadResult:
        """加载数据（带缓存）。任何情况下都不会抛异常，除非完全没有可用数据。"""
        if self._result is not None and not force:
            return self._result

        warnings: list[str] = []
        files = [self._explicit_file] if self._explicit_file else candidate_data_files()

        for path in files:
            if path is None or not path.exists():
                warnings.append(f"数据文件不存在：{path}")
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                warnings.append(f"数据文件无法解析（已跳过）：{path} — {exc}")
                continue

            schools, meta, parse_warnings = self._parse(payload)
            warnings.extend(parse_warnings)
            if not schools:
                warnings.append(f"数据文件没有有效院校（已跳过）：{path}")
                continue

            self._result = LoadResult(
                schools=tuple(schools),
                meta=meta,
                source_path=str(path),
                warnings=tuple(warnings),
            )
            return self._result

        raise RepositoryError(
            "未能加载任何院校数据。" + ("；".join(warnings) if warnings else "")
        )

    @staticmethod
    def _parse(payload: Any) -> tuple[list[School], dict[str, Any], list[str]]:
        """把 JSON 负载解析成 School 列表（跳过坏记录并记录 warning）。"""
        warnings: list[str] = []
        if isinstance(payload, list):  # 允许裸数组格式
            items, meta = payload, {}
        elif isinstance(payload, Mapping):
            items = payload.get("schools") or payload.get("data") or []
            meta = dict(payload.get("meta") or {})
        else:
            return [], {}, ["数据文件顶层结构无法识别（应为对象或数组）"]

        if not isinstance(items, list):
            return [], meta, ["schools 字段不是数组"]

        schools: list[School] = []
        seen_ids: set[str] = set()
        for index, item in enumerate(items):
            if not isinstance(item, Mapping):
                warnings.append(f"第 {index + 1} 条不是对象，已跳过")
                continue
            school = School.from_dict(item)
            if not school.name:
                warnings.append(f"第 {index + 1} 条缺少校名，已跳过")
                continue
            dedup_key = school.id or school.name
            if dedup_key in seen_ids:
                warnings.append(f"重复院校已跳过：{school.name}")
                continue
            seen_ids.add(dedup_key)
            schools.append(school)

        return schools, meta, warnings

    # ------------------------------------------------------------------ 查询
    def query(
        self,
        schools: Sequence[School] | None = None,
        *,
        keyword: str = "",
        city: str = FILTER_ALL,
        ownership: str = FILTER_ALL,
        sort: str = SORT_DEFAULT,
        distances: Mapping[str, float] | None = None,
    ) -> list[School]:
        """按关键词/城市/办学性质筛选并排序。

        :param distances: ``{school.id: 公里数}``，用于「距离最近」排序
        """
        if schools is None:
            schools = self.load().schools

        result = [s for s in schools if self._match(s, keyword, city, ownership)]
        return self.sort(result, sort=sort, distances=distances)

    @staticmethod
    def _match(school: School, keyword: str, city: str, ownership: str) -> bool:
        if city and city != FILTER_ALL and school.city != city:
            return False
        if ownership and ownership != FILTER_ALL and school.ownership != ownership:
            return False
        terms = keyword.split()
        if not terms:
            return True
        blob = school.search_blob().lower()
        return all(term.lower() in blob for term in terms)

    @staticmethod
    def sort(
        schools: Iterable[School],
        *,
        sort: str = SORT_DEFAULT,
        distances: Mapping[str, float] | None = None,
    ) -> list[School]:
        items = list(schools)

        def distance_of(school: School) -> float:
            if not distances:
                return float("inf")
            value = distances.get(school.id)
            return float(value) if value is not None else float("inf")

        if sort == SORT_NAME:
            items.sort(key=lambda s: (s.name,))
        elif sort == SORT_DISTANCE:
            items.sort(key=lambda s: (distance_of(s), s.city, s.name))
        elif sort == SORT_PUBLIC_FIRST:
            items.sort(key=lambda s: (s.ownership != OWNERSHIP_PUBLIC, s.city, s.name))
        elif sort == SORT_PRIVATE_FIRST:
            items.sort(key=lambda s: (s.ownership != OWNERSHIP_PRIVATE, s.city, s.name))
        else:  # SORT_DEFAULT
            items.sort(key=lambda s: (s.city, s.name))
        return items

    # ------------------------------------------------------------------ 统计
    def loading_summary(self) -> dict[str, int]:
        """用于「关于/数据」对话框展示的统计。"""
        result = self.load()
        return {
            "total": len(result.schools),
            "public": sum(1 for s in result.schools if s.ownership == OWNERSHIP_PUBLIC),
            "private": sum(1 for s in result.schools if s.ownership == OWNERSHIP_PRIVATE),
            "with_coordinates": sum(1 for s in result.schools if s.has_coordinates),
            "with_official_early_admission": sum(
                1
                for s in result.schools
                if s.early_admission_confidence == CONFIDENCE_HIGH
            ),
        }
