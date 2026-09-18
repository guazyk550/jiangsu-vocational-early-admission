"""用 Photon（OpenStreetMap 数据，免 key）批量采集院校经纬度。

⚠️ 坐标来源说明
----------------
江苏省教育考试院、各院校官网均**不提供**机读坐标，因此坐标只能来自地理编码服务。
本项目使用 `Photon <https://photon.komoot.io/>`_（数据源为 OpenStreetMap 社区数据），
**不是官方数据**：可能命中分校区、同名地点或存在数十米~数百米偏差。因此每条记录都
带 ``coord_source_url`` 与 ``coord_confidence``，低置信项会被列出来供人工复核。

经验（实测）
------------
- 查询词用**学校官方全名**命中率最高；带「省市区」前缀反而会掉命中。
- ``osm_value`` 为 college/university/school 才是学校类地点。
- 命中名含「分部/校区/继续教育」时降级标记。

用法::

    py tools/geocode.py                 # 全量采集（默认 1 req/s 限速）
    py tools/geocode.py --limit 5       # 调试
    py tools/geocode.py --refresh       # 忽略已有结果，全部重采
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import FetchError, http_get_json, pick  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_PATH = PROJECT_ROOT / "data" / "_base.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "_geocode_raw.json"

PHOTON_URL = "https://photon.komoot.io/api/"
USER_AGENT = "jsvoc-nav/0.1 (data collection; contact: project maintainer)"

SCHOOL_OSM_VALUES = {"college", "university", "school"}
SUSPECT_HINTS = ("分部", "分校区", "继续教育", "附属", "合作办学", "校区")
#: 命中名里出现这些词说明**不是同一所学校**（技师学院/中小学/公司/园区等），
#: 即使校名主干词命中也必须拒绝——“南京交通技师学院”绝不是“南京交通职业技术学院”。
NEGATIVE_NAME_HINTS = (
    "技师",
    "中学",
    "小学",
    "幼儿园",
    "公司",
    "工厂",
    "仓库",
    "创业园",
    "产业园",
    "科技园",
    "工业园",
    "研究院",
    "培训",
    "驾校",
    "医院",
    "卫生院",
    "酒店",
    "矿业",
    "公寓",
    "小区",
    "地铁站",
    "公交站",
    "汽车站",
)


def photon_query(name: str, limit: int = 5, timeout: float = 20.0) -> list[dict[str, Any]]:
    """查询 Photon，返回 GeoJSON features 列表。"""
    payload = http_get_json(
        PHOTON_URL,
        params={"q": name, "limit": limit},
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
        retries=2,
    )
    return pick(payload, "features", default=[]) or []


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


#: 未尾泛化后缀：去掉后剩下的才是学校“主干词”
GENERIC_SUFFIXES = (
    "职业技术学院",
    "职业学院",
    "高等专科学校",
    "高等职业学校",
    "技术学院",
    "师范学校",
    "大学",
    "学院",
    "学校",
)


def _normalize(text: str) -> str:
    """归一化校名：去省市字、括号、空白，便于包含关系判定。"""
    for token in ("江苏省", "省", "市", " ", "　"):
        text = text.replace(token, "")
    return text


def _stem(name: str) -> str:
    """提取校名主干词（去掉泛化后缀）。"""
    for suffix in GENERIC_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix) + 1:
            return name[: -len(suffix)]
    return name


def _in_jiangsu(latitude: float | None, longitude: float | None) -> bool:
    """粗略的江苏省地理围栏（约 lat 30.7~35.2、lon 116.1~122.0）。

    用坐标范围而非城市名判定：Photon 返回的城市名是拼音（Suzhou/Nanjing），
    与中文城市名比对会全部落空。
    """
    if latitude is None or longitude is None:
        return False
    return 30.7 <= latitude <= 35.2 and 116.1 <= longitude <= 122.0


def score_feature(school: dict[str, Any], feature: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    """给一个候选地点打分，并抽取标准化字段。

    关键判据是**校名主干词是否出现在命中名里**，而不是纯字符串相似度：
    “无锡职业技术学院”与“江阴职业技术学院”相似度高达 0.75、又都在无锡，
    纯相似度会把它们误判为同一所学校。
    """
    props = feature.get("properties") or {}
    geometry = feature.get("geometry") or {}
    coords = geometry.get("coordinates") or []

    matched_name = str(props.get("name") or "")
    matched_norm = _normalize(matched_name)
    stem_norm = _normalize(_stem(school["name"]))
    full_norm = _normalize(school["name"])

    # 只接受「学校主干词出现在命中名中」——反向包含会把「常州道」当「常州铁道」
    name_hit = bool(stem_norm) and (
        len(stem_norm) >= 2
        and (stem_norm in matched_norm or full_norm in matched_norm)
    )
    ratio = similarity(school["name"], matched_name)

    latitude = float(coords[1]) if len(coords) >= 2 else None
    longitude = float(coords[0]) if len(coords) >= 2 else None

    target_city = school.get("city") or ""
    haystack = " ".join(
        str(props.get(k) or "") for k in ("city", "county", "state", "district")
    )
    # 城市名可能命中（中文回退），但主判据是坐标是否落在江苏省内
    city_ok = _in_jiangsu(latitude, longitude) or (
        bool(target_city) and target_city in haystack
    )
    is_school_osm = props.get("osm_value") in SCHOOL_OSM_VALUES

    score = 0.0
    if name_hit:
        score += 100.0
    score += ratio * 30.0
    if city_ok:
        score += 25.0
    if is_school_osm:
        score += 15.0
    if any(hint in matched_name for hint in SUSPECT_HINTS) and not any(
        hint in school["name"] for hint in SUSPECT_HINTS
    ):
        score -= 35.0

    # 命中名里含「技师/中小学/公司/园区/公寓…」→ 判定为异名地点，直接拒绝
    negative_hit = any(h in matched_name for h in NEGATIVE_NAME_HINTS) and not any(
        h in school["name"] for h in NEGATIVE_NAME_HINTS
    )

    # 分级：既要「校名主干词命中」，又要「坐标确实在江苏」且不是异名地点；
    # ratio 防止「南京铁道车辆技师学院」这类同前缀异校被误采
    if name_hit and city_ok and not negative_hit and ratio >= 0.95:
        confidence = "high"
    elif name_hit and city_ok and not negative_hit and ratio >= 0.75:
        confidence = "medium"
    else:
        confidence = "low"

    record = {
        "matched_name": matched_name,
        "latitude": latitude,
        "longitude": longitude,
        "osm_value": props.get("osm_value"),
        "osm_id": props.get("osm_id"),
        "osm_city": props.get("city"),
        "osm_district": props.get("district") or props.get("county"),
        "osm_street": " ".join(
            filter(None, [props.get("street"), props.get("housenumber")])
        ),
        "name_hit": name_hit,
        "city_ok": city_ok,
        "negative_hit": negative_hit,
        "name_ratio": round(ratio, 3),
        "candidate_confidence": confidence,
    }
    return score, record


def query_variants(school: dict[str, Any]) -> list[str]:
    """构造多个查询词。

    Photon 对中文分词的敏感度很高：全名命中率最好，但新设院校/名称含「大学」
    的学校常常落空或误配，因此再试「去后缀」「城市+校名」「校名+城市」等变体，
    最后在所有变体的返回结果里统一评分取最优。
    """
    name = school["name"]
    city = school.get("city") or ""
    variants = [name]
    for suffix in (
        "高等专科学校",
        "职业技术学院",
        "职业学院",
        "技术学院",
        "高等职业学校",
    ):
        if name.endswith(suffix) and len(name) > len(suffix) + 2:
            variants.append(name[: -len(suffix)])
            break
    if city and not name.startswith(city):
        variants.append(f"{city}{name}")
        variants.append(f"{name} {city}")

    seen: set[str] = set()
    ordered: list[str] = []
    for variant in variants:
        if variant and variant not in seen:
            seen.add(variant)
            ordered.append(variant)
    return ordered


def geocode_school(
    school: dict[str, Any], sleep: float = 1.1, simple: bool = False
) -> dict[str, Any]:
    """采集一所院校的坐标（多查询变体，取评分最高的候选）。"""
    name = school["name"]
    variants = [name] if simple else query_variants(school)
    result: dict[str, Any] = {
        "name": name,
        "city": school.get("city"),
        "query": variants[0],
        "queries_tried": variants,
        "coord_source_url": f"{PHOTON_URL}?q={urllib.parse.quote(variants[0])}",
        "coord_source": "OpenStreetMap via Photon (非官方数据)",
    }

    scored: list[tuple[float, dict[str, Any]]] = []
    errors: list[str] = []
    for index, variant in enumerate(variants):
        try:
            features = photon_query(variant)
        except FetchError as exc:
            errors.append(f"{variant}: {exc}")
            continue
        for feature in features:
            scored.append(score_feature(school, feature))
        if index < len(variants) - 1:
            time.sleep(sleep)

    if not scored:
        result.update(
            {
                "latitude": None,
                "longitude": None,
                "coord_confidence": "none",
                "note": "；".join(errors) if errors else "Photon 无匹配结果",
            }
        )
        return result

    scored.sort(key=lambda pair: -pair[0])
    best_score, best = scored[0]
    confidence = best.pop("candidate_confidence", "none")

    # 低置信坐标一律不写入：错误的距离比没有距离更糟（用户要求：宁可空也不编造）
    if confidence in ("low", "none"):
        note = (
            f"Photon 仅有低置信候选（{best.get('matched_name')}），坐标不予采用"
        )
        result.update(
            {
                "latitude": None,
                "longitude": None,
                "coord_confidence": confidence,
                "match_score": round(best_score, 1),
                "rejected_candidate": best,
                "note": note,
            }
        )
        return result

    result.update(best)
    result.update(
        {
            "coord_confidence": confidence,
            "match_score": round(best_score, 1),
            "alternatives": [
                {"score": round(s, 1), **r} for s, r in scored[1:3]
            ],
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="用 Photon 采集院校坐标")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--only", type=str, default=None)
    parser.add_argument("--refresh", action="store_true", help="忽略已有结果重采")
    parser.add_argument(
        "--simple",
        action="store_true",
        help="只用学校全名查询（不加变体），用于补采未命中项",
    )
    parser.add_argument("--sleep", type=float, default=1.1, help="请求间隔秒数（限速）")
    parser.add_argument("--out", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    data = json.loads(BASE_PATH.read_text(encoding="utf-8"))
    schools: list[dict[str, Any]] = data["schools"]
    if args.only:
        schools = [s for s in schools if args.only in s["name"]]
    if args.limit:
        schools = schools[: args.limit]

    previous: dict[str, dict[str, Any]] = {}
    if args.out.exists() and not args.refresh:
        cached = json.loads(args.out.read_text(encoding="utf-8"))
        previous = {r["name"]: r for r in cached.get("results", [])}

    results: list[dict[str, Any]] = []
    for index, school in enumerate(schools, start=1):
        cached = previous.get(school["name"])
        if cached and cached.get("coord_confidence") in ("high", "medium"):
            results.append(cached)
            print(f"[{index:>3}/{len(schools)}] {school['name']} → 沿用缓存({cached['coord_confidence']})")
            continue
        record = geocode_school(school, sleep=args.sleep, simple=args.simple)
        results.append(record)
        lat, lon = record.get("latitude"), record.get("longitude")
        print(
            f"[{index:>3}/{len(schools)}] {school['name']} → {record['coord_confidence']} "
            f"{lat},{lon} ({record.get('matched_name')})",
            flush=True,
        )
        time.sleep(args.sleep)

    summary: dict[str, int] = {}
    for record in results:
        summary[record["coord_confidence"]] = summary.get(record["coord_confidence"], 0) + 1

    output = {
        "meta": {
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "source": "Photon / OpenStreetMap（免 key，非官方数据）",
            "source_url": PHOTON_URL,
            "count": len(results),
            "confidence_summary": summary,
        },
        "results": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n[完成] 写入 {args.out}")
    print(f"[坐标置信度] {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
