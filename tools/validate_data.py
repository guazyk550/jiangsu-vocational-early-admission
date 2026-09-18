"""数据集体检：``data/schools.json`` 的自动化校验。

校验项（对应需求中「Phase 5 数据检查」）
-----------------------------------------
- 校名/必填字段是否缺失；
- URL 是否为空或格式明显错误（非 http/https）；
- 坐标是否缺失、是否落在江苏省之外（经纬度写反等）；
- 校名/id 是否重复；
- 城市是否规范（江苏 13 个设区市）；
- 办学性质取值是否合法（公办/民办）；
- 是否混入非高职院校（校名含“大学/本科”等信号）。

退出码：``0`` 无 error，``1`` 存在 error —— 便于在打包前作为门禁使用。

用法::

    py tools/validate_data.py                     # 校验 data/schools.json
    py tools/validate_data.py --dataset path.json  # 校验指定文件
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = PROJECT_ROOT / "data" / "schools.json"

JIANGSU_CITIES = {
    "南京", "无锡", "徐州", "常州", "苏州", "南通", "连云港",
    "淮安", "盐城", "扬州", "镇江", "泰州", "宿迁",
}

#: 江苏省粗略经纬度范围（与 geocode.py 的围栏一致）
LAT_RANGE = (30.7, 35.2)
LON_RANGE = (116.1, 122.0)

VALID_OWNERSHIP = {"公办", "民办"}
URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
NON_VOCATIONAL_HINTS = ("大学", "本科")

#: 提前招生入口的「标题」里出现这些词，说明它很可能是过程性页面
#: （第二轮、校测、成绩、录取公示…）而不是简章/栏目页——
#: 正是用户反馈过的问题（“打开的是第二轮招生”），所以纳入体检。
PROCESS_TITLE_HINTS = (
    "第二轮", "二轮", "校测", "校考", "成绩", "录取", "公示", "准考证",
    "征集", "补录", "严正声明", "声明", "须知", "报名", "考试",
)

LEVEL_ERROR = "ERROR"
LEVEL_WARN = "WARN"


@dataclass(frozen=True, slots=True)
class Issue:
    level: str
    scope: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.scope}: {self.message}"


def check_school(raw: dict, index: int) -> list[Issue]:
    """校验单条记录。"""
    issues: list[Issue] = []
    name = str(raw.get("name") or "").strip()
    scope = name or f"第 {index + 1} 条"

    if not name:
        return [Issue(LEVEL_ERROR, scope, "缺少校名（name 为空）")]

    if any(hint in name for hint in NON_VOCATIONAL_HINTS):
        issues.append(
            Issue(LEVEL_WARN, scope, f"校名含「{'/'.join(NON_VOCATIONAL_HINTS)}」，请确认不是本科院校混入")
        )

    city = str(raw.get("city") or "").strip()
    if not city:
        issues.append(Issue(LEVEL_ERROR, scope, "缺少城市（city）"))
    elif city not in JIANGSU_CITIES:
        issues.append(
            Issue(LEVEL_ERROR, scope, f"城市「{city}」不在江苏 13 个设区市内，可能是脏数据")
        )

    ownership = str(raw.get("ownership") or "").strip()
    if ownership not in VALID_OWNERSHIP:
        issues.append(
            Issue(LEVEL_ERROR, scope, f"办学性质「{ownership}」非法（应为 公办/民办）")
        )

    # ---- URL 检查 ----
    # ---- 链接检查（全部招生相关入口）----
    for field, label, fatal in (
        ("official_website", "官网", False),
        ("admission_website", "招生网", False),
        ("early_admission_url", "提前招生页面", True),
        ("admission_brochure_url", "招生简章/章程", False),
        ("admission_plan_url", "招生计划", False),
    ):
        value = str(raw.get(field) or "").strip()
        if not value:
            issues.append(
                Issue(LEVEL_ERROR if fatal else LEVEL_WARN, scope, f"{label}（{field}）为空")
            )
        elif not URL_RE.match(value):
            issues.append(
                Issue(LEVEL_ERROR, scope, f"{label}（{field}）格式可疑：{value[:80]}")
            )

    # 入口标题的“过程性页面”体检（只对提前招生入口做，其他入口无标题字段）
    entry_title = str(raw.get("early_admission_title") or "")
    hits = [word for word in PROCESS_TITLE_HINTS if word in entry_title]
    if hits:
        issues.append(
            Issue(
                LEVEL_WARN,
                scope,
                f"提前招生入口标题疑似过程性页面（命中 {'、'.join(hits)}）：{entry_title[:40]}",
            )
        )

    if not str(raw.get("address") or "").strip():
        issues.append(Issue(LEVEL_WARN, scope, "地址为空"))
    if not str(raw.get("source_url") or "").strip():
        issues.append(Issue(LEVEL_WARN, scope, "缺少数据来源 source_url"))

    # ---- 坐标检查 ----
    latitude, longitude = raw.get("latitude"), raw.get("longitude")
    if latitude is None or longitude is None:
        issues.append(Issue(LEVEL_WARN, scope, "缺少坐标（不计算直线距离）"))
    else:
        try:
            lat, lon = float(latitude), float(longitude)
        except (TypeError, ValueError):
            issues.append(Issue(LEVEL_ERROR, scope, f"坐标不是数字：{latitude}, {longitude}"))
        else:
            if 20 <= lat <= 50 and 110 <= lon <= 130 and not (
                LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]
            ):
                issues.append(
                    Issue(LEVEL_ERROR, scope, f"坐标 {lat},{lon} 看起来不在江苏省内（可能经纬度写反）")
                )
            elif not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]):
                issues.append(
                    Issue(LEVEL_ERROR, scope, f"坐标 {lat},{lon} 明显越界（应在中国江苏附近）")
                )

    # ---- 年度检查 ----
    data_year = raw.get("data_year")
    if not data_year:
        issues.append(Issue(LEVEL_WARN, scope, "缺少 data_year（数据年度）"))
    if not str(raw.get("last_verified") or "").strip():
        issues.append(Issue(LEVEL_WARN, scope, "缺少 last_verified（核验日期）"))

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="校验院校数据集")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--strict-warnings", action="store_true", help="把 WARN 也视为失败")
    parser.add_argument("--quiet", action="store_true", help="只输出汇总")
    args = parser.parse_args()

    if not args.dataset.exists():
        print(f"[ERROR] 数据集不存在：{args.dataset}")
        return 1

    try:
        payload = json.loads(args.dataset.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[ERROR] 数据集不是合法 JSON：{exc}")
        return 1

    schools = payload.get("schools") if isinstance(payload, dict) else payload
    if not isinstance(schools, list) or not schools:
        print("[ERROR] 数据集中没有 schools 数组或为空")
        return 1

    issues: list[Issue] = []
    seen_names: dict[str, int] = {}
    seen_ids: dict[str, int] = {}

    for index, raw in enumerate(schools):
        if not isinstance(raw, dict):
            issues.append(Issue(LEVEL_ERROR, f"第 {index + 1} 条", "不是对象"))
            continue
        issues.extend(check_school(raw, index))

        name = str(raw.get("name") or "").strip()
        school_id = str(raw.get("id") or "").strip()
        if name:
            seen_names.setdefault(name, index)
        if school_id:
            seen_ids.setdefault(school_id, index)

    names_seen: set[str] = set()
    ids_seen: set[str] = set()
    for raw in schools:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        school_id = str(raw.get("id") or "").strip()
        if name:
            if name in names_seen:
                issues.append(Issue(LEVEL_ERROR, name, "校名重复"))
            names_seen.add(name)
        if school_id:
            if school_id in ids_seen:
                issues.append(Issue(LEVEL_ERROR, school_id, f"id 重复（{name}）"))
            ids_seen.add(school_id)

    errors = [i for i in issues if i.level == LEVEL_ERROR]
    warnings = [i for i in issues if i.level == LEVEL_WARN]

    if not args.quiet:
        for issue in errors + warnings:
            print(issue)

    print()
    print(f"数据集：{args.dataset}")
    print(f"院校总数：{len(schools)}　坐标缺失：{sum(1 for s in schools if isinstance(s, dict) and s.get('latitude') is None)}")
    print(f"ERROR {len(errors)} 项　WARN {len(warnings)} 项")

    if errors:
        print("\n结论：存在必须修复的问题。")
        return 1
    if warnings and args.strict_warnings:
        print("\n结论：严格模式下存在警告项。")
        return 1
    print("\n结论：通过（无 ERROR）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
