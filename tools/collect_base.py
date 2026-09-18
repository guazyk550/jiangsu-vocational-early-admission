"""采集江苏省专科（高职）院校基础数据。

数据口径
--------
江苏省内**全部高职（专科）院校**（含公办、民办）。依据江苏省 2026 年高职院校
提前招生官方口径「省内高职（专科）院校以及教育部批准的省外高职（专科）院校均
可申请参加」，省内全部高职专科院校都是潜在招生院校；「是否实际参加并公布当年
招生简章」由后续 ``verify_early_admission.py`` 逐校核验。

数据来源（均为公开可访问接口，实测无需鉴权 header）
----------------------------------------------------
1. 院校列表： ``https://api.eol.cn/gkcx/api/`` （掌上高考，uri=apidata/api/gk/school/lists）
   → 学校名称 / 所在城市 / 办学层次 / 办学性质（公办·民办）
2. 院校详情： ``https://static-data.gaokao.cn/www/2.0/school/{school_id}/info.json``
   → 官网地址 / 招生网地址 / 详细地址

⚠️ 上述来源是**第三方公开教育信息平台**（非省考试院官方数据），仅作为「基础名单 +
线索」。公办/民办、城市将在后续步骤与教育部《全国高等学校名单》交叉核验，官网/招生
网/提前招生页面将以各校官网实际抓取结果为准。

用法::

    py tools/collect_base.py                 # 采集全部并写入 data/_base.json
    py tools/collect_base.py --limit 5       # 只采前 5 所（调试用）
    py tools/collect_base.py --no-detail     # 只要列表，不逐校取详情
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

# 允许以 `py tools/collect_base.py` 直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import FetchError, http_get_json, pick, unwrap  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "data" / "_base.json"

LIST_URL = "https://api.eol.cn/gkcx/api/"
DETAIL_URL_TEMPLATE = "https://static-data.gaokao.cn/www/2.0/school/{school_id}/info.json"

PROVINCE_ID_JIANGSU = 32
LEVEL_ZHUANKE = 2002  # 专科（高职）
PAGE_SIZE = 30
DATA_YEAR = 2026

#: 江苏 13 个设区市（用于城市字段归一化与校验）
JIANGSU_CITIES = [
    "南京", "无锡", "徐州", "常州", "苏州", "南通", "连云港",
    "淮安", "盐城", "扬州", "镇江", "泰州", "宿迁",
]


def list_params(page: int) -> dict[str, Any]:
    """构造列表接口的查询参数（该接口要求把这些空参数也带上）。"""
    return {
        "access_token": "",
        "admissions": "",
        "central": "",
        "department": "",
        "dual_class": "",
        "f211": "",
        "f985": "",
        "is_dual_class": "",
        "keyword": "",
        "level": LEVEL_ZHUANKE,
        "page": page,
        "province_id": PROVINCE_ID_JIANGSU,
        "ranktype": "",
        "request_type": 1,
        "school_type": "",
        "signsafe": "",
        "size": PAGE_SIZE,
        "sort": "view_total",
        "type": "",
        "uri": "apidata/api/gk/school/lists",
    }


def normalize_city(raw: Any) -> tuple[str, str]:
    """把 ``南京市`` 归一化为 ``南京``；无法识别时原样返回。

    :return: (归一化城市, 原始城市)
    """
    raw_text = str(raw or "").strip()
    for city in JIANGSU_CITIES:
        if raw_text.startswith(city):
            return city, raw_text
    return raw_text.rstrip("市"), raw_text


def fetch_school_list(limit: int | None = None) -> list[dict[str, Any]]:
    """分页抓取江苏省专科院校列表，返回原始条目列表。"""
    items: list[dict[str, Any]] = []
    page = 1
    total: int | None = None

    while True:
        payload = http_get_json(LIST_URL, params=list_params(page), retries=3)
        data = unwrap(payload)
        if total is None:
            total = int(pick(data, "numFound", default=0) or 0)
            print(f"[列表] 接口报告江苏专科院校总数：{total}")

        batch = pick(data, "item", "items", default=[]) or []
        if not batch:
            break
        items.extend(batch)
        print(f"[列表] 第 {page} 页 +{len(batch)} 条（累计 {len(items)}）")

        if limit is not None and len(items) >= limit:
            items = items[:limit]
            break
        if total and len(items) >= total:
            break
        page += 1
        if page > 30:  # 安全阀，避免接口异常导致死循环
            break

    return items


def fetch_school_detail(school_id: int) -> dict[str, Any]:
    """抓取单所院校详情 JSON（失败返回空字典，不抛异常）。"""
    url = DETAIL_URL_TEMPLATE.format(school_id=school_id)
    try:
        payload = http_get_json(url, retries=2, timeout=15.0)
    except FetchError as exc:
        print(f"  ! 详情抓取失败 school_id={school_id}: {exc}")
        return {}
    detail = unwrap(payload)
    detail["_fetched"] = True
    return detail


def build_record(list_item: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    """把列表条目 + 详情合并为一条中间记录。"""
    school_id = pick(list_item, "school_id")
    city, city_raw = normalize_city(pick(list_item, "city_name", "city"))
    nature = str(pick(list_item, "nature_name", "school_nature_name", default="") or "")

    return {
        "eol_id": school_id,
        "name": str(pick(list_item, "name", default="") or "").strip(),
        "city": city,
        "city_raw": city_raw,
        "district": "",  # 列表接口不提供，后续按需补
        "ownership": nature,  # 公办 / 民办（待与教育部名单交叉核验）
        "ownership_raw": nature,
        "school_type": str(pick(list_item, "type_name", default="") or ""),
        "level_name": str(pick(list_item, "level_name", default="") or ""),
        "province_name": str(pick(list_item, "province_name", default="") or ""),
        "official_website": str(
            pick(detail, "school_site", "school_site_url", "website", default="") or ""
        ),
        "admission_website": str(
            pick(detail, "site", "admission_site", "zs_site", default="") or ""
        ),
        "address": str(pick(detail, "address", default="") or ""),
        "detail_fetched": bool(detail.get("_fetched")),
        "list_source_url": f"{LIST_URL}?uri=apidata/api/gk/school/lists&province_id={PROVINCE_ID_JIANGSU}&level={LEVEL_ZHUANKE}",
        "detail_source_url": DETAIL_URL_TEMPLATE.format(school_id=school_id),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="采集江苏高职专科院校基础数据")
    parser.add_argument("--limit", type=int, default=None, help="只采前 N 所（调试）")
    parser.add_argument("--no-detail", action="store_true", help="跳过逐校详情抓取")
    parser.add_argument("--out", type=Path, default=OUTPUT_PATH, help="输出路径")
    args = parser.parse_args()

    raw_items = fetch_school_list(limit=args.limit)
    print(f"[列表] 共取得 {len(raw_items)} 条原始记录")

    schools: list[dict[str, Any]] = []
    for index, item in enumerate(raw_items, start=1):
        school_id = pick(item, "school_id")
        name = pick(item, "name", default="?")
        detail: dict[str, Any] = {}
        if not args.no_detail and school_id is not None:
            detail = fetch_school_detail(int(school_id))
        record = build_record(item, detail)
        schools.append(record)
        flag = "OK " if record["official_website"] else "无官网"
        print(f"[{index:>3}/{len(raw_items)}] {record['name']} ({record['city']}) {flag}")

    output = {
        "meta": {
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "data_year": DATA_YEAR,
            "scope": "江苏省内高职（专科）院校（全量候选池，非『已确认参加提前招生』名单）",
            "province": "江苏省",
            "level": "专科（高职）",
            "list_source_url": f"{LIST_URL}?uri=apidata/api/gk/school/lists&province_id={PROVINCE_ID_JIANGSU}&level={LEVEL_ZHUANKE}",
            "detail_source_url_template": DETAIL_URL_TEMPLATE,
            "source_kind": "第三方公开教育信息平台（掌上高考/eol.cn、static-data.gaokao.cn），非官方数据，需交叉核验",
            "count": len(schools),
        },
        "schools": schools,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n[完成] 写入 {args.out}（{len(schools)} 所）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
