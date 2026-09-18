"""生成数据报告 ``tools/report.md``：统计概览 + 需人工确认清单 + 未收录清单。

报告面向「数据维护者」，与 ``validate_data.py``（面向机器校验、返回退出码）互补。

用法::

    py tools/report.py
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUT_PATH = PROJECT_ROOT / "tools" / "report.md"

#: 事务性页面/负面词：这些不是「提前招生简章」，用户点开意义有限
NEGATIVE_WORDS = ("成绩", "查询", "录取", "名单", "公示", "准考证", "缴费", "复核", "补录")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    dataset = load(DATA_DIR / "schools.json")
    schools: list[dict[str, Any]] = dataset["schools"]
    excluded = load(DATA_DIR / "excluded.json")["excluded"]

    lines: list[str] = []
    add = lines.append

    add("# 江苏高职提前招生院校导航器 —— 数据报告")
    add("")
    add(f"- 生成时间：{dt.datetime.now().astimezone().isoformat(timespec='seconds')}")
    add(f"- 数据年度：**{dataset['meta']['data_year']}**")
    add(f"- 收录院校：**{len(schools)} 所**（公办 {dataset['meta']['ownership_summary']['公办']} 所 / 民办 {dataset['meta']['ownership_summary']['民办']} 所）")
    add(f"- 未收录：{len(excluded)} 所（见文末，原因可追溯）")
    add("")

    # ---- 分布统计 ----
    add("## 一、分布统计")
    add("")
    add("### 1.1 按城市")
    add("")
    add("| 城市 | 院校数 | 公办 | 民办 |")
    add("| --- | ---: | ---: | ---: |")
    by_city = collections.defaultdict(list)
    for school in schools:
        by_city[school["city"]].append(school)
    for city, items in sorted(by_city.items(), key=lambda kv: -len(kv[1])):
        public = sum(1 for x in items if x["ownership"] == "公办")
        private = len(items) - public
        add(f"| {city} | {len(items)} | {public} | {private} |")
    add("")

    add("### 1.2 提前招生页面核验置信度")
    add("")
    add("| 置信度 | 含义 | 数量 |")
    add("| --- | --- | ---: |")
    add("| high | 学校自有域名、页面确含“提前招生” | "
        f"{sum(1 for x in schools if x['early_admission_confidence'] == 'high')} |")
    add("| medium | 仅第三方转载页，或官方页无法直连核验 | "
        f"{sum(1 for x in schools if x['early_admission_confidence'] == 'medium')} |")
    add("| low | 页面可访问但无法确认内容 | "
        f"{sum(1 for x in schools if x['early_admission_confidence'] == 'low')} |")
    add("")

    add("### 1.3 坐标置信度")
    add("")
    coord_summary = dataset["meta"]["coord_confidence_summary"]
    add("| 置信度 | 数量 |")
    add("| --- | ---: |")
    for level in ("high", "medium", "low", "none"):
        add(f"| {level} | {coord_summary.get(level, 0)} |")
    add("")
    add(f"> 可用坐标（high + medium）：**{coord_summary.get('high', 0) + coord_summary.get('medium', 0)} 所**；其余显示“暂无距离数据”。")
    add("")

    # ---- 需人工确认 ----
    add("## 二、需人工确认清单")
    add("")

    add("### 2.1 提前招生页面为第三方转载（非学校自有域名）")
    add("")
    third_party = [x for x in schools if x["early_admission_third_party"]]
    if third_party:
        add("| 院校 | 参考链接 | 说明 |")
        add("| --- | --- | --- |")
        for school in third_party:
            add(f"| {school['name']} | {school['early_admission_url']} | {school['early_admission_evidence'][:60]} |")
    else:
        add("（无）")
    add("")

    add("### 2.2 页面指向事务性内容（非招生简章）")
    add("")
    transactional = []
    for school in schools:
        blob = f"{school['early_admission_title']} {school['early_admission_url']}"
        if any(word in blob for word in NEGATIVE_WORDS):
            transactional.append(school)
    if transactional:
        add("| 院校 | 当前链接标题 | 建议 |")
        add("| --- | --- | --- |")
        for school in transactional:
            add(f"| {school['name']} | {school['early_admission_title']} | 人工寻找当年《提前招生简章》栏目页替换 |")
    else:
        add("（无）")
    add("")

    add("### 2.3 缺少坐标（无法显示直线距离）")
    add("")
    missing_coord = [x for x in schools if x["latitude"] is None]
    add(f"共 {len(missing_coord)} 所：")
    add("")
    for school in missing_coord:
        note = school.get("notes") or []
        reason = next((n for n in note if "Photon" in n or "无匹配" in n), "")
        add(f"- {school['name']}（{school['city']}）{('— ' + reason[:60]) if reason else ''}")
    add("")

    add("### 2.4 坐标/地址匹配到“分校区或相关地点”")
    add("")
    suspect = [
        x
        for x in schools
        if x.get("coord_matched_name") and x["coord_matched_name"] != x["name"]
    ]
    if suspect:
        add("| 院校 | 命中的地点名 | 置信度 |")
        add("| --- | --- | --- |")
        for school in suspect:
            add(f"| {school['name']} | {school['coord_matched_name']} | {school['coord_confidence']} |")
    else:
        add("（无）")
    add("")

    # ---- 未收录 ----
    add("## 三、未收录院校（含原因）")
    add("")
    add("| 院校 | 城市 | 未收录原因 | 复核提示 |")
    add("| --- | --- | --- | --- |")
    for item in excluded:
        hint = item.get("joined_early_admission_hint") or ""
        reason = item.get("reason", "")
        note = (item.get("agent_note") or "").replace("\n", " ")[:110]
        add(f"| {item['name']} | {item.get('city', '')} | {reason} | {hint} {note} |")
    add("")

    # ---- 数据来源 ----
    add("## 四、数据来源")
    add("")
    for source in dataset["meta"]["sources"]:
        add(f"- {source}")
    add("")
    add("## 五、免责声明")
    add("")
    add(dataset["meta"]["disclaimer"])
    add("")

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[完成] 报告已写入 {OUT_PATH}（{len(lines)} 行）")
    print(f"  收录 {len(schools)} 所｜未收录 {len(excluded)} 所")
    print(f"  第三方转载页 {len(third_party)} 所｜事务性页面 {len(transactional)} 所｜缺坐标 {len(missing_coord)} 所")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
