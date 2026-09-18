"""把采集/核验/地理编码三路中间数据合成最终数据集 ``data/schools.json``。

输入
----
- ``data/_base.json``        —— 院校基础信息（名称/城市/官网/招生网/地址）
- ``data/_verify_raw.json``  —— 2026 提前招生页面核验结果（含置信度与证据）
- ``data/_geocode_raw.json`` —— Photon(OSM) 坐标与置信度
- ``data/_agent3/*.json``    —— 办学性质交叉核验结果（可选）

输出
----
- ``data/schools.json``      —— 程序实际读取的数据集（仅收录**已核验到提前招生页面**的院校）
- ``data/excluded.json``     —— 未收录院校及原因（不删除、可追溯）

字段设计原则
------------
1. 每个字段尽量可追溯：来源 URL、置信度、核验日期都保留；
2. 拿不到就 ``null``，**绝不编造** URL/坐标/地址；
3. ``data_year`` 表示整个数据集的年度；单个院校的 ``early_admission_year``
   表示其页面上明确标注的年度（栏目页可能为 null，属正常）。

用法::

    py tools/build_dataset.py
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

BASE_PATH = DATA_DIR / "_base.json"
VERIFY_PATH = DATA_DIR / "_verify_raw.json"
GEOCODE_PATH = DATA_DIR / "_geocode_raw.json"
OWNERSHIP_DIR = DATA_DIR / "_agent3"
OUT_PATH = DATA_DIR / "schools.json"
EXCLUDED_PATH = DATA_DIR / "excluded.json"

DATA_YEAR = 2026
#: 数据核验基准日（本次人工/自动核验日期）
VERIFY_DATE = "2026-09-18"

#: 精确发布时间在核验脚本里不便解析，这里用「核验日」再补一个粗粒度年度
SHORT_NAME_RULES: tuple[tuple[str, str], ...] = (
    ("职业技术学院", "学院"),
    ("职业学院", "学院"),
    ("高等专科学校", ""),
    ("高等职业学校", ""),
    ("师范学校", ""),
    ("职业学院", ""),
)


def auto_short_name(name: str) -> str:
    """规则化生成简称（仅用于搜索匹配，标注 short_name_source=auto）。"""
    for suffix, replacement in SHORT_NAME_RULES:
        if name.endswith(suffix):
            return name[: -len(suffix)] + replacement
    return name


def _chinese_only(value: Any) -> str:
    """只保留含中文的字段值。

    Photon 返回的 district 是拼音（如 "Maqun"），对中文用户没有意义，
    宁可为空也不展示拼音。
    """
    text = str(value or "").strip()
    return text if re.search(r"[\u4e00-\u9fff]", text) else ""


def make_id(eol_id: Any, name: str) -> str:
    """稳定 ID：优先复用数据源 id，保证跨版本可追踪。"""
    if eol_id:
        return f"jsvoc-{eol_id}"
    slug = re.sub(r"[^0-9a-z]+", "-", name.lower()).strip("-")
    return slug or "unknown"


def load_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_ownership_reviews() -> dict[str, dict[str, Any]]:
    """读取办学性质交叉核验结果（可能不存在，返回空 dict）。"""
    reviews: dict[str, dict[str, Any]] = {}
    if not OWNERSHIP_DIR.exists():
        return reviews
    for path in sorted(OWNERSHIP_DIR.glob("*.json")):
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for item in items:
            if item.get("name"):
                reviews[item["name"]] = item
    return reviews


def main() -> int:
    base = json.loads(BASE_PATH.read_text(encoding="utf-8"))
    verify = json.loads(VERIFY_PATH.read_text(encoding="utf-8"))
    geocode = load_optional(GEOCODE_PATH)
    ownership_reviews = load_ownership_reviews()

    verify_by_name = {r["name"]: r for r in verify["results"]}
    geo_by_name = {r["name"]: r for r in geocode.get("results", [])}

    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for school in base["schools"]:
        name = school["name"]
        verification = verify_by_name.get(name, {})
        geo = geo_by_name.get(name, {})
        confidence = verification.get("confidence", "none")
        ownership_review = ownership_reviews.get(name, {})

        # ---- 收录口径：只收录「已核验到 2026 提前招生相关页面」的院校 ----
        if confidence == "none" or not verification.get("early_admission_url"):
            excluded.append(
                {
                    "name": name,
                    "city": school.get("city"),
                    "official_website": school.get("official_website"),
                    "admission_website": school.get("admission_website"),
                    "reason": "未核验到明确的提前招生页面（未收录）",
                    "verification_notes": verification.get("notes", []),
                    "agent_note": verification.get("agent_note", ""),
                    "joined_early_admission_hint": verification.get(
                        "joined_early_admission_agent", ""
                    ),
                    "checked_at": VERIFY_DATE,
                }
            )
            continue

        ownership = school.get("ownership") or ""
        ownership_note = ""
        ownership_source = (
            "掌上高考 api.eol.cn（派生自教育部高校名单）"
        )
        if ownership == "中外合作办学":
            # 中外合作办学在筛选上归入「民办」组，但保留原始说明
            ownership_note = "中外合作办学"
            ownership = "民办"

        if ownership_review.get("ownership_verified") not in (None, "", "unknown"):
            verified_ownership = ownership_review["ownership_verified"]
            if verified_ownership == "中外合作办学":
                # 同样归入「民办」筛选组，避免出现第三种筛选值
                if "中外合作办学" not in ownership_note:
                    ownership_note = (
                        f"{ownership_note}；中外合作办学".strip("；")
                    )
                verified_ownership = "民办"
            if verified_ownership != ownership:
                ownership_note = (
                    f"{ownership_note}；经官网核验为{ownership_review['ownership_verified']}".strip(
                        "；"
                    )
                )
            ownership = verified_ownership
            ownership_source = (
                f"官网/官方来源核验：{ownership_review.get('source', '')}".strip("：")
            )

        address = school.get("address") or ""
        latitude = geo.get("latitude")
        longitude = geo.get("longitude")
        # 坐标缺失或低置信时，仍写入数值但用 confidence 标出，UI 可据此提示
        record: dict[str, Any] = {
            "id": make_id(school.get("eol_id"), name),
            "source_id": school.get("eol_id"),
            "name": name,
            "short_name": auto_short_name(name),
            "short_name_source": "auto",
            "city": school.get("city"),
            "district": _chinese_only(
                school.get("district") or geo.get("osm_district")
            ),
            "ownership": ownership,
            "ownership_note": ownership_note,
            "ownership_source": ownership_source,
            "school_type": "高职专科",
            "school_type_raw": school.get("school_type", ""),
            "official_website": school.get("official_website") or "",
            "admission_website": school.get("admission_website") or "",
            "early_admission_url": verification.get("early_admission_url") or "",
            "early_admission_title": verification.get("early_admission_title") or "",
            "early_admission_year": verification.get("early_admission_year"),
            "early_admission_confidence": confidence,
            "early_admission_third_party": bool(verification.get("third_party")),
            "early_admission_reference_url": (
                verification.get("early_admission_url")
                if verification.get("third_party")
                else ""
            ),
            "early_admission_evidence": verification.get("agent_evidence", "")
            or " ".join(
                str(e.get("text", ""))
                for e in (verification.get("evidence") or [])
                if e.get("text")
            )[:160],
            "address": address,
            "latitude": latitude,
            "longitude": longitude,
            "coord_source": geo.get("coord_source", ""),
            "coord_source_url": geo.get("coord_source_url", ""),
            "coord_confidence": geo.get("coord_confidence", "none"),
            "coord_matched_name": geo.get("matched_name", ""),
            "baidu_address": address,
            "map_query": name,
            "source_url": verification.get("early_admission_url")
            or school.get("admission_website")
            or school.get("official_website")
            or "",
            "source_list_url": base["meta"]["list_source_url"],
            "data_year": DATA_YEAR,
            "last_verified": VERIFY_DATE,
            "notes": verification.get("notes", []),
        }
        included.append(record)

    included.sort(key=lambda r: (r["city"] or "", r["name"]))

    output = {
        "meta": {
            "data_year": DATA_YEAR,
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "last_verified": VERIFY_DATE,
            "count": len(included),
            "ownership_summary": {
                "公办": sum(1 for r in included if r["ownership"] == "公办"),
                "民办": sum(1 for r in included if r["ownership"] == "民办"),
            },
            "early_admission_confidence_summary": {
                level: sum(
                    1 for r in included if r["early_admission_confidence"] == level
                )
                for level in ("high", "medium", "low")
            },
            "coord_confidence_summary": {
                level: sum(1 for r in included if r["coord_confidence"] == level)
                for level in ("high", "medium", "low", "none")
            },
            "scope": "江苏省内已核验到 2026 年提前招生相关页面的高职（专科）院校",
            "disclaimer": (
                "本数据集为公开信息整理，非官方招生平台发布。招生政策、计划、报考条件"
                "以江苏省教育考试院及各院校官方发布为准。坐标来自 OpenStreetMap，"
                "非官方数据。"
            ),
            "sources": [
                "江苏省教育考试院 www.jseea.cn（政策口径与时间节点）",
                "各院校官网/招生网（提前招生页面逐校核验）",
                "掌上高考 api.eol.cn 与 static-data.gaokao.cn（基础名单/官网/地址，第三方）",
                "OpenStreetMap via Photon（经纬度，非官方）",
            ],
        },
        "schools": included,
    }

    OUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    EXCLUDED_PATH.write_text(
        json.dumps(
            {
                "meta": {
                    "generated_at": output["meta"]["generated_at"],
                    "reason": "未核验到明确的 2026 提前招生页面，按用户口径暂不收录",
                    "count": len(excluded),
                },
                "excluded": excluded,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"[完成] schools.json 收录 {len(included)} 所")
    print(f"[完成] excluded.json 未收录 {len(excluded)} 所")
    print(f"[公办/民办] {output['meta']['ownership_summary']}")
    print(f"[提前招生置信度] {output['meta']['early_admission_confidence_summary']}")
    print(f"[坐标置信度] {output['meta']['coord_confidence_summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
