"""逐校核验「提前招生」页面地址（early_admission_url）。

为什么必须逐校核验
------------------
各校网站结构完全不同：有的把提前招生放在「招生网 → 招生章程 → 提前招生」，有的
直接在招生网首页挂当年简章，有的用图片/JS 导航。**不存在可推导的统一规则**，因此
本脚本对每所院校：

1. 抓取其**招生网首页**与**官网首页**（官网只作后备）；
2. 提取页内全部链接，按「是否含『提前招生』『简章/章程』『当年年份』」等特征打分；
3. 对高分候选**实际发请求验证**（HTTP 200 且页面确含「提前招生」），避免写入死链；
4. 找不到就留空（``null``）——**绝不猜测或拼接 URL**。

未达 ``high`` 置信度的院校会进入待人工复核清单。

用法::

    py tools/verify_early_admission.py                     # 全量（默认 6 并发）
    py tools/verify_early_admission.py --limit 10          # 只跑前 10 所
    py tools/verify_early_admission.py --only 苏州卫生      # 只跑校名含该子串的院校
    py tools/verify_early_admission.py --workers 10        # 调整并发
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import functools
import json
import re
import sys
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import FetchError, http_get, http_probe  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_PATH = PROJECT_ROOT / "data" / "_base.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "_verify_raw.json"

CURRENT_YEAR = 2026
PAST_YEARS = (2025, 2024, 2023)

STRONG_KEYWORD = "提前招生"
WEAK_KEYWORDS = ("单独招生", "单招", "提前录取")
#: 越靠前越接近「用户真正想看的页面」——简章/章程/指南
DOC_STRONG = ("简章", "章程", "指南", "方案", "办法")
DOC_WEAK = ("通知", "公告", "计划", "资讯")
#: 这些是招生过程中的事务性页面（成绩查询/拟录取公示等），不应作为「提前招生官网」入口
DOC_NEGATIVE = (
    "成绩", "查询", "录取", "名单", "公示", "面试", "缴费", "准考证",
    "打印", "复核", "补录", "打印阶", "报名入口", "模拟",
)
SUBPAGE_HINTS = ("招生", "单招", "提前", "报考")
SUBPAGE_URL_HINTS = ("zhaosheng", "zsb", "zs.", "zsw", "enroll", "recruit")

YEAR_RE = re.compile(r"(20\d{2})")


class _LinkExtractor(HTMLParser):
    """提取 ``<a>`` 的 (文本, href) 对。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.title: str = ""
        self._in_title = False
        self._href: str | None = None
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
        elif tag == "a":
            self._href = dict(attrs).get("href")
            self._chunks = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "a" and self._href is not None:
            text = " ".join("".join(self._chunks).split())
            self.links.append((text, self._href))
            self._href = None
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._href is not None:
            self._chunks.append(data)


def parse_html(html: str) -> _LinkExtractor:
    parser = _LinkExtractor()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 - 畸形 HTML 不应中断核验
        pass
    return parser


def extract_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """返回去重后的绝对化链接列表。"""
    parser = parse_html(html)
    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for text, href in parser.links:
        if not href:
            continue
        url = urllib.parse.urljoin(base_url, href.strip())
        if not url.lower().startswith(("http://", "https://")):
            continue
        if url in seen:
            continue
        seen.add(url)
        result.append((text, url))
    return result


def page_title(html: str) -> str:
    return " ".join(parse_html(html).title.split())[:200]


def link_blob(text: str, url: str) -> str:
    """把链接文本与 URL 路径合起来判断（URL 需要解码后再看中文）。"""
    return f"{text} {urllib.parse.unquote(url)}"


def score_link(text: str, url: str, home_host: str) -> int:
    """给候选链接打分，分越高越可能是「提前招生简章/栏目」页面。

    设计意图（避免把「校测成绩查询通知」这类事务页当成入口）：
    简章/章程/指南 优先；当年 > 往年；成绩/查询/录取公示类重罚。
    """
    blob = link_blob(text, url)
    score = 0
    if STRONG_KEYWORD in blob:
        score += 100
    elif any(k in blob for k in WEAK_KEYWORDS):
        score += 40
    else:
        return 0  # 与提前招生/单招完全无关的链接直接淘汰

    if any(k in blob for k in DOC_STRONG):
        score += 35
    elif any(k in blob for k in DOC_WEAK):
        score += 5
    if any(k in blob for k in DOC_NEGATIVE):
        score -= 45
    if str(CURRENT_YEAR) in blob:
        score += 30
    elif any(str(y) in blob for y in PAST_YEARS):
        score += 12
    if urllib.parse.urlparse(url).netloc == home_host:
        score += 8
    if url.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx")):
        score += 2
    return score


def looks_like_subpage(text: str, url: str) -> bool:
    """判断是否值得再抓一层（招生类栏目页）。"""
    blob = link_blob(text, url)
    if any(k in blob for k in SUBPAGE_HINTS):
        return True
    low = url.lower()
    return any(k in low for k in SUBPAGE_URL_HINTS)


def year_in(text: str) -> int | None:
    """从文本中取一个合理的年份（优先当年，其次近年）。"""
    years = [int(y) for y in YEAR_RE.findall(text)]
    years = [y for y in years if 2018 <= y <= CURRENT_YEAR + 1]
    if not years:
        return None
    if CURRENT_YEAR in years:
        return CURRENT_YEAR
    return max(years)


def collect_candidates(
    school: dict[str, Any],
    max_subpages: int = 2,
    timeout: float = 18.0,
    retries: int = 1,
    insecure: bool = False,
) -> tuple[list[dict[str, Any]], list[str]]:
    """抓取招生网/官网首页（及少量招生栏目子页），收集候选链接。"""
    notes: list[str] = []
    seeds: list[str] = []
    for key in ("admission_website", "official_website"):
        url = (school.get(key) or "").strip()
        if url and url not in seeds:
            seeds.append(url)

    candidates: dict[str, dict[str, Any]] = {}
    subpages: list[dict[str, Any]] = []

    def register(source_page: str, text: str, url: str) -> None:
        score = score_link(text, url, urllib.parse.urlparse(source_page).netloc)
        if score <= 0:
            return
        record = {
            "text": text[:120],
            "url": url,
            "score": score,
            "source_page": source_page,
        }
        previous = candidates.get(url)
        if previous is None or previous["score"] < score:
            candidates[url] = record

    for seed in seeds:
        try:
            # 带 Referer 可绕过部分院校站点的防盗链（412/403）
            html = http_get(
                seed,
                headers={"Referer": seed},
                timeout=timeout,
                retries=retries,
                insecure=insecure,
            )
        except FetchError as exc:
            notes.append(f"首页抓取失败 {seed}: {exc}")
            continue
        for text, url in extract_links(html, seed):
            score = score_link(text, url, urllib.parse.urlparse(seed).netloc)
            if score <= 0:
                continue
            register(seed, text, url)
            if score < 60 and looks_like_subpage(text, url) and url != seed:
                subpages.append({"text": text, "url": url, "score": score})

    # 再抓一层招生栏目页（首页没直接挂提前招生链接时常见）
    for sub in sorted(subpages, key=lambda d: -d["score"])[:max_subpages]:
        try:
            html = http_get(
                sub["url"],
                headers={"Referer": sub["source_page"]},
                timeout=timeout,
                retries=retries,
                insecure=insecure,
            )
        except FetchError as exc:
            notes.append(f"子页抓取失败 {sub['url']}: {exc}")
            continue
        for text, url in extract_links(html, sub["url"]):
            register(sub["url"], text, url)

    return sorted(candidates.values(), key=lambda d: -d["score"]), notes


def verify_candidate(
    candidate: dict[str, Any], timeout: float = 15.0, insecure: bool = False
) -> dict[str, Any]:
    """实际请求候选链接，确认可达且页面确实与提前招生相关。"""
    url = candidate["url"]
    status, body = http_probe(url, timeout=timeout, insecure=insecure)
    title = page_title(body) if body else ""
    has_keyword = STRONG_KEYWORD in body or STRONG_KEYWORD in title
    evidence = {
        **candidate,
        "status": status,
        "page_title": title,
        "page_has_keyword": has_keyword,
        "reached": status == 200,
    }

    if status != 200:
        confidence = "none"
    elif has_keyword:
        confidence = "high"
    elif any(k in link_blob(candidate["text"], url) for k in WEAK_KEYWORDS):
        confidence = "medium"
    else:
        confidence = "low"

    evidence["confidence"] = confidence
    evidence["year"] = year_in(f"{candidate['text']} {title} {urllib.parse.unquote(url)}")
    return evidence


def verify_school(
    school: dict[str, Any],
    *,
    timeout: float = 18.0,
    retries: int = 1,
    insecure: bool = False,
) -> dict[str, Any]:
    """核验一所院校，返回结构化结果。"""
    name = school.get("name", "")
    candidates, notes = collect_candidates(
        school, timeout=timeout, retries=retries, insecure=insecure
    )
    if insecure:
        notes.append("本次抓取已忽略 TLS 证书校验（部分院校证书链不完整）")
    checked: list[dict[str, Any]] = []

    best: dict[str, Any] | None = None
    for candidate in candidates[:6]:
        evidence = verify_candidate(
            candidate, timeout=timeout * 0.8, insecure=insecure
        )
        checked.append(evidence)
        if evidence["reached"] and evidence["page_has_keyword"]:
            best = evidence
            break
        if best is None and evidence["reached"]:
            best = evidence  # 可达但未确认关键词，作为降级候选

    if best is None:
        result = {
            "early_admission_url": None,
            "early_admission_title": "",
            "early_admission_year": None,
            "confidence": "none",
        }
        if not candidates:
            notes.append("未在招生网/官网找到任何含『提前招生/单招』的链接")
    else:
        result = {
            "early_admission_url": best["url"] if best["confidence"] != "none" else None,
            "early_admission_title": best.get("page_title") or best.get("text", ""),
            "early_admission_year": best.get("year"),
            "confidence": best["confidence"],
        }

    return {
        "eol_id": school.get("eol_id"),
        "name": name,
        "city": school.get("city"),
        "admission_website": school.get("admission_website", ""),
        "official_website": school.get("official_website", ""),
        **result,
        "evidence": checked,
        "notes": notes,
        "checked_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="逐校核验提前招生页面")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--only", type=str, default=None, help="只跑校名含该子串的院校")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timeout", type=float, default=18.0, help="单个请求超时秒数")
    parser.add_argument("--retries", type=int, default=1, help="单请求重试次数")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="忽略 TLS 证书校验（仅用于部分院校证书链不完整的公开招生页面，只读）",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="只重跑上次结果中 confidence != high 的院校，并与上次结果合并",
    )
    parser.add_argument("--out", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    data = json.loads(BASE_PATH.read_text(encoding="utf-8"))
    schools: list[dict[str, Any]] = data["schools"]
    if args.only:
        schools = [s for s in schools if args.only in s.get("name", "")]
    if args.limit:
        schools = schools[: args.limit]

    # 已有结果：既用于 --retry-failed 的筛选，也用于「保留未重跑院校」的合并
    previous: dict[str, dict[str, Any]] = {}
    if args.out.exists():
        cached = json.loads(args.out.read_text(encoding="utf-8"))
        previous = {r["name"]: r for r in cached.get("results", [])}

    if args.retry_failed and previous:
        schools = [
            s
            for s in schools
            if previous.get(s.get("name", ""), {}).get("confidence") != "high"
        ]
        print(f"[续跑] 上次已 high 的 {len(previous)} 所中，需重跑 {len(schools)} 所")

    print(f"[核验] 待核验院校 {len(schools)} 所，并发 {args.workers}")
    results: list[dict[str, Any]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        verify_one = functools.partial(
            verify_school,
            timeout=args.timeout,
            retries=args.retries,
            insecure=args.insecure,
        )
        futures = {pool.submit(verify_one, s): s for s in schools}
        for index, future in enumerate(
            concurrent.futures.as_completed(futures), start=1
        ):
            school = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 - 单校失败不影响整体
                result = {
                    "eol_id": school.get("eol_id"),
                    "name": school.get("name"),
                    "early_admission_url": None,
                    "confidence": "none",
                    "evidence": [],
                    "notes": [f"核验过程异常: {exc!r}"],
                }
            results.append(result)
            print(
                f"[{index:>3}/{len(schools)}] {result['name']} → "
                f"{result['confidence']} {result.get('early_admission_url') or ''}",
                flush=True,
            )

    # 合并上次结果（续跑时未重跑的院校沿用旧结果）
    if previous:
        merged = {name: r for name, r in previous.items()}
        for result in results:
            merged[result["name"]] = result
        results = list(merged.values())

    results.sort(key=lambda r: (r.get("city") or "", r.get("name") or ""))
    summary: dict[str, int] = {}
    for result in results:
        summary[result["confidence"]] = summary.get(result["confidence"], 0) + 1

    output = {
        "meta": {
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "target_year": CURRENT_YEAR,
            "method": "抓取招生网+官网首页及其招生栏目子页，按关键词打分并实际请求验证",
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
    print(f"[置信度] {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
