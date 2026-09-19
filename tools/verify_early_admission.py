"""逐校核验院校的三类入口链接。

核验目标
--------
1. ``early_admission``：**提前招生简章/章程/指南**，退而求其次才是「提前招生」栏目页；
2. ``admission_brochure``：学校**招生简章/招生章程**（普通高考口径）；
3. ``admission_plan``：**招生计划**页面。

为什么必须逐校核验、且要区分「简章」与「过程性通知」
------------------------------------------------------
各校网站结构完全不同，不存在可推导的统一规则。更麻烦的是：同一所学校的提前招生
栏目下会同时挂着《提前招生简章》和一堆过程性通知（第二轮报名、校测通知、计划表、
成绩/录取查询……）。早期版本只判断「页面可达且含『提前招生』」，于是把
「2026年提前招生第二轮计划表」这类页面选成了入口 —— 用户点进去看到的不是简章。

本版评分规则（对 ``early_admission``）：

- 「简章 / 章程 / 指南」→ 大幅加分；
- 栏目页（``list.htm``、标题就是「提前招生」）→ 加分（栏目会持续更新，比单篇通知更耐用）；
- 过程性词（第二轮、校测、成绩、查询、录取、公示、报名、考试、计划表…）→ 大幅减分；
- 当年年份 → 加分。

若某校**只有**过程性页面可选，仍会返回该链接，但把置信度降为 ``medium`` 并在
``notes`` 里写明原因，避免把「非简章页」伪装成「简章」。

用法::

    py tools/verify_early_admission.py                  # 全量
    py tools/verify_early_admission.py --only 江苏信息    # 只跑校名含该子串的院校
    py tools/verify_early_admission.py --retry-failed    # 只重跑未达标的院校
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
from dataclasses import dataclass, field
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

#: 过程性页面特征：出现即说明「这不是简章本身」
PROCESS_KEYWORDS = (
    "第二轮", "二轮", "补录", "征集", "征求", "调剂", "成绩", "查询", "录取", "名单", "公示",
    "准考证", "打印", "复核", "模拟", "报名", "考试", "校测", "面试", "缴费",
    "计划表", "专业计划", "严正声明", "声明", "温馨提醒", "倒计时",
)
#: 专业级/合作办学类简章不是「学校整体招生简章」，不应作为「招生简章」入口
MAJOR_LEVEL_KEYWORDS = ("中外合作", "合作办学", "（中外", "(中外", "订单班", "专业（", "专业(")

#: 项目/批次类修饰词：属于专项计划，不是「全校总览」
MODIFIER_KEYWORDS = (
    "3+2", "贯通培养", "现代职教", "中外合作", "合作办学", "订单班",
    "艺术类", "体育类", "职教高考", "对口单招", "中职", "征求",
)

#: 不同目标下的「过程性噪声」不一样：
#: ——对「提前招生简章」而言，“计划表/校测/录取查询”都是噪声；
#: ——对「招生计划」而言，“计划表”恰恰是正常内容，只有“征求/补录”才是噪声。
EARLY_PROCESS = PROCESS_KEYWORDS
BROCHURE_PROCESS = (
    "成绩", "查询", "录取", "公示", "准考证", "校测", "计划表", "专业计划",
    "征求", "补录", "调剂", "缴费",
)
PLAN_PROCESS = ("征求", "征集", "补录", "调剂", "录取", "查询", "成绩", "公示", "准考证")

#: 「录取结果 / 成绩查询」——这类页面本身就是过程性的，因此**不做过程词惩罚**，
#: 但它们只作为**参考入口**展示，不会占用「提前招生简章」的位置。
RESULT_PROCESS: tuple[str, ...] = ()
#: 「考试资料 / 试卷 / 大纲」——同理，不罚过程词
EXAM_PROCESS: tuple[str, ...] = ()
#: 弱负面：这些页面可能是简章，也可能不是（如「2026年提前招生通知」）
SOFT_NEGATIVE = ("通知", "公告", "须知", "新闻", "要闻", "简讯")

BROCHURE_STRONG = ("简章", "章程", "指南")
SECTION_URL_RE = re.compile(
    r"(list\d*\.(?:htm|html|php|jsp|aspx)$|/column/|/index\.(?:htm|html|php|asp|aspx|shtml)$"
    r"|/list\b|/tqzs|/gzdz|/ztzs)",
    re.IGNORECASE,
)
SECTION_TEXTS = (
    "提前招生", "单招", "单独招生", "高职提前招生", "提前自主招生",
    "招生简章", "招生章程", "招生计划", "招生信息", "报考指南",
)
SUBPAGE_HINTS = ("招生", "单招", "提前", "报考", "简章", "章程", "计划")
SUBPAGE_URL_HINTS = ("zhaosheng", "zsb", "zs.", "zsw", "enroll", "recruit", "zsw", "zsjy")

#: 栏目页 URL 里常见的中文拼音缩写。用于**识别候选**（不是猜 URL），保守只收语义明确的。
PINYIN_HINTS = {
    "tqzs": "提前招生",
    "gzdz": "高职单招",
    "dzs": "单招",
    "zsjz": "招生简章",
    "zsjh": "招生计划",
    "zsdt": "招生动态",
    "zsw": "招生网",
    "zsxx": "招生信息",
    "lqcx": "录取查询",
    "lqjg": "录取结果",
    "cjcx": "成绩查询",
}

#: 页面上的链接文字常被截断（“2026年…提前招...”），因此允许关键词尾部缺字
MIN_PARTIAL_LEN = 3


def loose_contains(blob: str, keyword: str) -> bool:
    """宽容包含判断：允许关键词尾部被截断（至少保留 3 个字）。

    这一条修的是一个真实数据 bug：江苏信息招生网首页的链接文字被截断成
    「2026年江苏信息职业技术学院高职院校提前招...」，严格匹配“提前招生”失败，
    于是选错了入口（选成了「提前招生第二轮计划表」）。
    """
    if not keyword:
        return False
    if keyword in blob:
        return True
    for cut in range(len(keyword) - 1, MIN_PARTIAL_LEN - 1, -1):
        if keyword[:cut] in blob:
            return True
    return False


def pinyin_expand(url: str) -> str:
    """把 URL 路径里的拼音缩写展开成中文，让「无文字链接」也能被正确分类。"""
    path = urllib.parse.urlparse(url).path.lower()
    return " ".join(text for key, text in PINYIN_HINTS.items() if key in path)

YEAR_RE = re.compile(r"(20\d{2})")

#: 置信度优先级：重跑结果只在“更好”时才覆盖旧结果，
#: 避免院校站点限流/超时导致已核验到的链接被误删（实测过“越跑越少”）。
CONFIDENCE_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}


@dataclass(frozen=True, slots=True)
class LinkTarget:
    """一类要核验的链接（含自己的评分策略）。"""

    key: str
    label: str
    any_keywords: tuple[str, ...]
    page_keywords: tuple[str, ...]
    #: 命中这些词说明「就是简章本身」
    doc_bonus: tuple[str, ...] = ()
    #: 已单独采集「提前招生」时，优先普通高考简章
    prefer_no_early_keyword: bool = False
    #: 该目标下的过程性噪声词
    process_keywords: tuple[str, ...] = ()
    #: 栏目页（列表页）加成——栏目会随官网持续更新，比单篇文章耐用
    section_bonus: int = 20
    #: 是否惩罚「项目/批次类」文档
    penalize_modifiers: bool = False


EARLY = LinkTarget(
    key="early_admission",
    label="提前招生简章/栏目",
    any_keywords=("提前招生", "单招", "单独招生", "提前录取"),
    page_keywords=("提前招生",),
    doc_bonus=BROCHURE_STRONG,
    process_keywords=EARLY_PROCESS,
    section_bonus=20,
)
BROCHURE = LinkTarget(
    key="admission_brochure",
    label="招生简章/章程",
    any_keywords=("招生简章", "招生章程", "简章", "章程"),
    page_keywords=("招生简章", "招生章程"),
    doc_bonus=("简章", "章程"),
    prefer_no_early_keyword=True,
    process_keywords=BROCHURE_PROCESS,
    section_bonus=70,
    penalize_modifiers=True,
)
PLAN = LinkTarget(
    key="admission_plan",
    label="招生计划",
    any_keywords=("招生计划", "招生专业", "计划表", "分专业招生计划"),
    page_keywords=("招生计划", "招生专业"),
    doc_bonus=("计划",),
    process_keywords=PLAN_PROCESS,
    section_bonus=70,
    penalize_modifiers=True,
)
RESULT = LinkTarget(
    key="admission_result",
    label="录取结果/成绩查询",
    any_keywords=(
        "录取查询", "录取结果", "拟录取", "预录取", "录取名单", "录取公示",
        "成绩查询", "查询系统", "录取信息",
    ),
    page_keywords=("录取", "成绩", "查询"),
    doc_bonus=("查询", "结果", "名单"),
    process_keywords=RESULT_PROCESS,
    section_bonus=30,
)
EXAM = LinkTarget(
    key="exam_material",
    label="考试资料/试卷",
    any_keywords=(
        "校测", "考试大纲", "试题", "试卷", "样题", "真题", "考试说明",
        "考核办法", "校测方案", "测试大纲", "题库", "模拟题", "考试内容",
        "职业适应性测试", "文化素质测试",
    ),
    page_keywords=("校测", "试题", "试卷", "大纲", "考核", "考试", "测试"),
    doc_bonus=("大纲", "试题", "试卷", "样题", "考核办法"),
    process_keywords=EXAM_PROCESS,
    section_bonus=30,
)

TARGETS = (EARLY, BROCHURE, PLAN, RESULT, EXAM)


class _LinkExtractor(HTMLParser):
    """提取 ``<a>`` 的 (文本, href) 对以及页面标题。"""

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


def page_title(html: str) -> str:
    return " ".join(parse_html(html).title.split())[:200]


def extract_links(html: str, base_url: str) -> list[tuple[str, str]]:
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


def link_blob(text: str, url: str) -> str:
    """把链接文本、URL 路径与拼音展开合起来判断。"""
    return f"{text} {urllib.parse.unquote(url)} {pinyin_expand(url)}"


def is_section_page(text: str, url: str) -> bool:
    """判断是否像「栏目页/列表页」而不是单篇文章。"""
    clean = text.strip()
    if clean in SECTION_TEXTS or (len(clean) <= 8 and any(k in clean for k in SECTION_TEXTS)):
        return True
    # URL 本身就是已知的拼音栏目名（zsjh.htm / zsjz.htm / tqzs.htm …）
    if pinyin_expand(url):
        return True
    return bool(SECTION_URL_RE.search(url))


def year_in(text: str) -> int | None:
    years = [int(y) for y in YEAR_RE.findall(text)]
    years = [y for y in years if 2018 <= y <= CURRENT_YEAR + 1]
    if not years:
        return None
    if CURRENT_YEAR in years:
        return CURRENT_YEAR
    return max(years)


def process_hits(blob: str) -> list[str]:
    return [word for word in PROCESS_KEYWORDS if word in blob]


def score_candidate(
    target: LinkTarget,
    text: str,
    url: str,
    home_host: str,
    context: str = "",
) -> tuple[int, list[str]]:
    """给某目标下的候选链接打分。

    :param context: 同栏目其他链接的语境（例如该栏目里其他文章含「招生章程」），
        用于弥补“链接文字被截断/为空、看不出是什么页面”的情况。
    :return: ``(分数, 命中的过程性关键词)``
    """
    own = link_blob(text, url)
    context = context or ""

    owned = any(loose_contains(own, keyword) for keyword in target.any_keywords)
    inherited = (
        not owned
        and bool(context)
        and any(loose_contains(context, keyword) for keyword in target.any_keywords)
    )
    if not (owned or inherited):
        return 0, []

    score = 0
    if target.key == EARLY.key:
        if loose_contains(own, "提前招生"):
            score += 100
        elif any(k in own for k in ("单独招生", "单招", "提前录取", "提前招")):
            score += 45
        elif inherited:
            # 只能靠同栏目语境推断（例如同栏目其他文章写了「提前招生」）
            score += 50
        else:
            return 0, []
    else:
        # 自身文字能判定 → 满分；只靠栏目语境 → 基础分更低（避免“沾亲带故”的误判）
        score += 80 if owned else 50
        if target.prefer_no_early_keyword and loose_contains(own, "提前招生"):
            # 已单独采集「提前招生」，这里优先普通高考简章/章程
            score -= 25

    if target.key == BROCHURE.key and any(k in own for k in MAJOR_LEVEL_KEYWORDS):
        # 「某某专业/中外合作办学招生简章」属于专业级文档，不是学校整体招生简章
        return 0, []

    if any(loose_contains(own, keyword) for keyword in target.doc_bonus):
        score += 45
    if is_section_page(text, url):
        score += target.section_bonus
    if target.penalize_modifiers and any(k in own for k in MODIFIER_KEYWORDS):
        score -= 40

    # 过程性判断只看链接自身文字，不看栏目语境（语境会让「成绩查询」也沾上「简章」）
    hits = [word for word in target.process_keywords if word in own]
    if hits:
        score -= 70
    score -= 20 * sum(1 for word in SOFT_NEGATIVE if word in own)

    if str(CURRENT_YEAR) in own:
        score += 25
    elif any(str(y) in own for y in PAST_YEARS):
        # 往年文档虽相关，但不是“最新信息”，明显降权
        score -= 70
    if urllib.parse.urlparse(url).netloc == home_host:
        score += 8
    if url.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx")):
        score += 2
    return score, hits


ARTICLE_ID_RE = re.compile(r"/info/(\d+)/\d+\.(?:htm|html)$", re.IGNORECASE)
CATEGORY_RE = re.compile(r"/info/(\d+)/", re.IGNORECASE)

#: 栏目语境词：同栏目里只要有一篇能看出栏目性质，就给整组补上语境
CONTEXT_WORDS = ("提前招生", "招生简章", "招生章程", "招生计划", "录取查询")


def build_context_map(links: list[dict[str, Any]]) -> dict[str, str]:
    """按文章 URL 的栏目 ID 分组，用同组链接的文字推断该栏目是什么。

    例：江苏信息招生网的 ``/info/1036/`` 分组里有一篇标题含「招生章程」的文章，
    于是同组那篇链接文字被截断成「江苏信息职业技术学院2026年全日制普通专科...」
    的文章也能被正确归到「招生章程」目标下。
    """
    groups: dict[str, list[str]] = {}
    for link in links:
        match = CATEGORY_RE.search(link["url"])
        if not match:
            continue
        groups.setdefault(match.group(1), []).append(link.get("text", ""))

    context: dict[str, str] = {}
    for category, texts in groups.items():
        joined = " ".join(texts)
        words = [word for word in CONTEXT_WORDS if loose_contains(joined, word)]
        if words:
            context[category] = " ".join(words)
    return context


def guess_section_urls(article_url: str) -> list[str]:
    """从文章页 URL 反推可能的「栏目列表页」（仅为候选，必须经请求验证后才采用）。"""
    match = ARTICLE_ID_RE.search(article_url)
    if not match:
        return []
    base = article_url[: match.start()]
    category = match.group(1)
    return [f"{base}/{category}/list.htm", f"{base}/{category}/list.html"]


def looks_like_subpage(text: str, url: str) -> bool:
    blob = link_blob(text, url)
    if any(k in blob for k in SUBPAGE_HINTS):
        return True
    low = url.lower()
    return any(k in low for k in SUBPAGE_URL_HINTS)


def gather_links(
    school: dict[str, Any],
    *,
    max_subpages: int = 3,
    timeout: float = 18.0,
    retries: int = 1,
    insecure: bool = False,
) -> tuple[list[dict[str, Any]], list[str]]:
    """抓取招生网/官网首页（及若干招生栏目子页），返回**全部**候选链接。"""
    notes: list[str] = []
    seeds: list[str] = []
    for key in ("admission_website", "official_website"):
        url = (school.get(key) or "").strip()
        if url and url not in seeds:
            seeds.append(url)

    # 只把「本校域名」的页面当作可抓子页，避免跑到 chsi.com.cn 之类外站
    home_hosts = {
        urllib.parse.urlparse(url).netloc
        for url in seeds
        if urllib.parse.urlparse(url).netloc
    }

    candidates: dict[str, dict[str, Any]] = {}
    subpages: dict[str, dict[str, Any]] = {}

    def register(source_page: str, text: str, url: str) -> None:
        if url in candidates:
            return
        candidates[url] = {"text": text[:140], "url": url, "source_page": source_page}

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
            if url == seed:
                continue
            blob = link_blob(text, url)
            relevant = any(
                any(loose_contains(blob, keyword) for keyword in target.any_keywords)
                for target in TARGETS
            ) or loose_contains(blob, "提前招生")
            if not relevant and not looks_like_subpage(text, url):
                continue
            register(seed, text, url)
            if (
                looks_like_subpage(text, url)
                and urllib.parse.urlparse(url).netloc in home_hosts
            ):
                subpages.setdefault(url, {"text": text, "url": url, "source_page": seed})

    # 再抓一层招生栏目页：简章往往在「招生简章」「提前招生」栏目里。
    # 优先挑语义明确的栏目（而不是随便一个含“招生”的页面），否则会白跑请求。
    SECTION_TEXT_PRIORITY = (
        "提前招生",
        "招生简章",
        "招生章程",
        "招生计划",
        "单招",
        "报考指南",
        "招生信息",
        "通知公告",
        "招生动态",
    )

    def subpage_rank(entry: dict[str, Any]) -> tuple[int, int]:
        text = entry.get("text", "")
        for index, keyword in enumerate(SECTION_TEXT_PRIORITY):
            if keyword in text:
                return index, len(entry["url"])
        # 文本看不出名堂的，退而看 URL 是否像栏目页
        fallback = len(SECTION_TEXT_PRIORITY)
        return fallback + (0 if is_section_page(text, entry["url"]) else 1), len(
            entry["url"]
        )

    ordered_subpages = [
        entry
        for entry in sorted(subpages.values(), key=subpage_rank)
        if entry["url"] not in seeds
    ][:max_subpages]
    for sub in ordered_subpages:
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

    result_links = list(candidates.values())
    context_map = build_context_map(result_links)
    for link in result_links:
        match = CATEGORY_RE.search(link["url"])
        link["context"] = context_map.get(match.group(1), "") if match else ""

    return result_links, notes


class ProbeCache:
    """URL → 探测结果缓存（同一 URL 可能被多个目标候选复用）。"""

    def __init__(self, timeout: float, insecure: bool) -> None:
        self.timeout = timeout
        self.insecure = insecure
        self._cache: dict[str, tuple[int, str]] = {}

    def probe(self, url: str) -> tuple[int, str]:
        if url not in self._cache:
            self._cache[url] = http_probe(
                url, timeout=self.timeout, insecure=self.insecure
            )
        return self._cache[url]

    def remember(self, url: str, status: int, body: str) -> None:
        self._cache[url] = (status, body)


def page_matches(target: LinkTarget, title: str, body: str) -> bool:
    return any(word in title or word in body for word in target.page_keywords)


def pick_for_target(
    target: LinkTarget,
    links: list[dict[str, Any]],
    home_hosts: set[str],
    probe_cache: ProbeCache,
    *,
    top_n: int = 4,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """为某个目标挑出最合适的链接并实际验证。"""
    scored: list[tuple[int, dict[str, Any], list[str]]] = []
    for link in links:
        score, hits = score_candidate(
            target,
            link["text"],
            link["url"],
            urllib.parse.urlparse(link["source_page"]).netloc,
            link.get("context", ""),
        )
        if score <= 0:
            continue
        scored.append((score, link, hits))
    scored.sort(key=lambda item: -item[0])

    # 若最优候选是「单篇文章页」而非栏目页，尝试从 URL 反推栏目列表页并验证。
    # 栏目页会随官网持续更新，比单篇通知更耐用——但**必须验证通过才采用**。
    if scored and not is_section_page(scored[0][1]["text"], scored[0][1]["url"]):
        for derived in guess_section_urls(scored[0][1]["url"]):
            if not any(link["url"] == derived for link in links):
                scored.insert(
                    0,
                    (
                        scored[0][0] + 5,
                        {
                            "text": target.label,
                            "url": derived,
                            "source_page": scored[0][1]["source_page"],
                            "derived_section": True,
                        },
                        [],
                    ),
                )

    evidence: list[dict[str, Any]] = []
    fallback: dict[str, Any] | None = None

    for score, link, hits in scored[: top_n + 2]:
        status, body = probe_cache.probe(link["url"])
        title = page_title(body) if body else ""
        matches = status == 200 and page_matches(target, title, body)
        record = {
            "url": link["url"],
            "text": link["text"],
            "score": score,
            "source_page": link["source_page"],
            "derived_section": bool(link.get("derived_section")),
            "status": status,
            "page_title": title,
            "page_matches": matches,
            "process_hits": hits,
            "is_section_page": is_section_page(link["text"], link["url"]),
            "year": year_in(f"{link['text']} {title} {urllib.parse.unquote(link['url'])}"),
        }
        record["stale_year"] = bool(record["year"] and record["year"] < CURRENT_YEAR)
        evidence.append(record)

        if not matches:
            if fallback is None and status == 200:
                fallback = record
            continue

        # 页面确认匹配：若带过程性关键词（第二轮/校测…）或为往年文档，则降级
        record["confidence"] = "medium" if (hits or record["stale_year"]) else "high"
        return record, evidence

    if fallback is not None:
        fallback["confidence"] = "low"
        return fallback, evidence
    return None, evidence


def verify_school(
    school: dict[str, Any],
    *,
    timeout: float = 18.0,
    retries: int = 1,
    insecure: bool = False,
) -> dict[str, Any]:
    """核验一所院校的五类链接。"""
    links, notes = gather_links(
        school, timeout=timeout, retries=retries, insecure=insecure
    )
    if insecure:
        notes.append("本次抓取已忽略 TLS 证书校验（部分院校证书链不完整）")

    home_hosts = set()
    for key in ("admission_website", "official_website"):
        url = (school.get(key) or "").strip()
        if url:
            home_hosts.add(urllib.parse.urlparse(url).netloc)

    probe_cache = ProbeCache(timeout * 0.8, insecure)
    result: dict[str, Any] = {
        "eol_id": school.get("eol_id"),
        "name": school.get("name", ""),
        "city": school.get("city"),
        "admission_website": school.get("admission_website", ""),
        "official_website": school.get("official_website", ""),
        "evidence": [],
        "notes": [],
    }

    for target in TARGETS:
        best, evidence = pick_for_target(target, links, home_hosts, probe_cache)
        result["evidence"].extend(evidence)
        if best is None:
            result[f"{target.key}_url"] = None
            result[f"{target.key}_title"] = ""
            result[f"{target.key}_confidence"] = "none"
            result[f"{target.key}_year"] = None
            if not links:
                notes.append("未在招生网/官网找到任何可用的栏目或文章链接")
            continue
        confidence = best.get("confidence", "none")
        result[f"{target.key}_url"] = best["url"] if confidence != "none" else None
        result[f"{target.key}_title"] = best.get("page_title") or best.get("text", "")
        result[f"{target.key}_confidence"] = confidence
        result[f"{target.key}_year"] = best.get("year")
        if best.get("process_hits"):
            notes.append(
                f"{target.label}：该校未找到「简章/栏目」页，采用过程性页面"
                f"（命中 {'、'.join(best['process_hits'])}）并已降级为 {confidence}"
            )
        if best.get("stale_year"):
            notes.append(
                f"{target.label}：仅找到 {best.get('year')} 年文档（非当年），已降级为 {confidence}"
            )
        if best.get("is_section_page"):
            notes.append(f"{target.label}：指向栏目页（会随官网更新，较稳定）")

    # 兼容旧字段名：早期版本与下游脚本使用 confidence / early_admission_*
    result["confidence"] = result["early_admission_confidence"]
    result["checked_at"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    result["notes"] = notes
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="逐校核验提前招生/简章/计划链接")
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
        help="只重跑上次「提前招生置信度非 high」或缺少简章/计划的院校，并与上次结果合并",
    )
    parser.add_argument("--out", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    data = json.loads(BASE_PATH.read_text(encoding="utf-8"))
    schools: list[dict[str, Any]] = data["schools"]
    if args.only:
        schools = [s for s in schools if args.only in s.get("name", "")]
    if args.limit:
        schools = schools[: args.limit]

    previous: dict[str, dict[str, Any]] = {}
    if args.out.exists():
        cached = json.loads(args.out.read_text(encoding="utf-8"))
        previous = {r["name"]: r for r in cached.get("results", [])}

    if args.retry_failed and previous:
        def needs_retry(school: dict[str, Any]) -> bool:
            old = previous.get(school.get("name", ""))
            if not old:
                return True
            if old.get("early_admission_confidence") != "high":
                return True
            return not old.get("admission_brochure_url") or not old.get("admission_plan_url") \
                or not old.get("admission_result_url") or not old.get("exam_material_url")

        schools = [s for s in schools if needs_retry(s)]
        print(f"[续跑] 待重跑 {len(schools)} 所")

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
                    "early_admission_confidence": "none",
                    "confidence": "none",
                    "evidence": [],
                    "notes": [f"核验过程异常: {exc!r}"],
                }
            results.append(result)
            print(
                f"[{index:>3}/{len(schools)}] {result['name']} → "
                f"{result.get('confidence')} {result.get('early_admission_url') or ''}"
                f"  | 简章:{'有' if result.get('admission_brochure_url') else '无'}"
                f" 计划:{'有' if result.get('admission_plan_url') else '无'}"
                f" 结果:{'有' if result.get('admission_result_url') else '无'}"
                f" 资料:{'有' if result.get('exam_material_url') else '无'}",
                flush=True,
            )

    if previous:
        merged = dict(previous)
        kept = 0
        for result in results:
            old = merged.get(result["name"])
            if old is not None:
                old_rank = max(
                    CONFIDENCE_RANK.get(old.get("early_admission_confidence") or "none", 0),
                    CONFIDENCE_RANK.get(old.get("confidence") or "none", 0),
                )
                new_rank = max(
                    CONFIDENCE_RANK.get(
                        result.get("early_admission_confidence") or "none", 0
                    ),
                    CONFIDENCE_RANK.get(result.get("confidence") or "none", 0),
                )
                if new_rank < old_rank:
                    kept += 1
                    # 保留旧的「提前招生」结果，但**采纳本轮采集到的其他入口**
                    # （招生简章/计划/录取结果/考试资料），避免新增字段被一起丢掉
                    merged_record = dict(result)
                    for field in (
                        "early_admission_url",
                        "early_admission_title",
                        "early_admission_confidence",
                        "early_admission_year",
                        "confidence",
                        "evidence",
                    ):
                        if field in old:
                            merged_record[field] = old[field]
                    merged_record["notes"] = list(old.get("notes") or []) + [
                        "本轮重跑未命中更优的提前招生页，沿用上一轮结果"
                    ]
                    merged[result["name"]] = merged_record
                    continue
            merged[result["name"]] = result
        if kept:
            print(f"[保护] 保留 {kept} 所上一轮更优的结果（本轮重跑降级，不覆盖）")
        results = list(merged.values())

    results.sort(key=lambda r: (r.get("city") or "", r.get("name") or ""))
    summary: dict[str, int] = {}
    for result in results:
        key = result.get("early_admission_confidence") or result.get("confidence", "none")
        summary[key] = summary.get(key, 0) + 1

    output = {
        "meta": {
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "target_year": CURRENT_YEAR,
            "method": (
                "抓取招生网+官网首页及其招生栏目子页；对『提前招生简章/章程/指南』加分、"
                "对栏目页加分、对『第二轮/校测/成绩/录取』等过程性页面重罚；"
                "同时采集招生简章/招生计划/录取结果/考试资料四类入口；"
                "候选链接均实际发请求验证（200 且页面关键词匹配）"
            ),
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
    print(f"[提前招生置信度] {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
