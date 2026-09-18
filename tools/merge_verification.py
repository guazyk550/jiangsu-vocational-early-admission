"""把子代理人工核验结果合并进 ``data/_verify_raw.json``。

工作流
------
``verify_early_admission.py`` 负责**自动**核验（能覆盖大部分院校）；
对它的失败项与旧年度项，由人工/子代理复核，结果以固定 JSON 格式落到
``data/_agent*/`` 目录。本脚本把这些复核结果合并回主结果文件，规则：

1. 复核 ``found=true`` 且为**学校自有域名** → ``high``
2. 复核 ``found=true`` 但为**第三方转载页** → ``medium``（并在数据中标注）
3. 复核 ``found=false`` → 保持 ``none``，把复核结论写进 notes

合并是**幂等**的：重复运行不会叠加，只会用最新一次的复核结果覆盖。

用法::

    py tools/merge_verification.py
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = PROJECT_ROOT / "data" / "_verify_raw.json"
AGENT_DIRS = [
    PROJECT_ROOT / "data" / "_agent",
    PROJECT_ROOT / "data" / "_agent2",
]

#: 需要人工下调置信度的特例：URL 来自搜索索引线索、子代理未能真正打开页面
#: 或页面打开但正文为空。键为校名，值为 (目标置信度, 原因)。
MANUAL_OVERRIDES: dict[str, tuple[str, str]] = {
    "江苏经贸职业技术学院": (
        "medium",
        "子代理未能实际打开（站点对抓取一律返回 412），URL 由搜索引擎索引确认存在",
    ),
    "盐城农业科技职业学院": (
        "low",
        "栏目页可访问但返回空正文（疑似防爬/JS 渲染），未能验证页内含『提前招生』",
    ),
}


def load_agent_results() -> dict[str, dict[str, Any]]:
    """收集全部子代理复核结果，按校名索引。"""
    merged: dict[str, dict[str, Any]] = {}
    for directory in AGENT_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                items = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                print(f"  ! 跳过非法 JSON {path}: {exc}")
                continue
            for item in items:
                name = item.get("name")
                if name:
                    item["_source"] = path.name
                    merged[name] = item
    return merged


def main() -> int:
    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    agent_results = load_agent_results()
    print(f"[合并] 子代理复核结果 {len(agent_results)} 条")

    updated = 0
    for result in raw["results"]:
        name = result["name"]
        agent = agent_results.get(name)
        if agent is None:
            continue

        note = str(agent.get("note") or "").strip()
        evidence = str(agent.get("evidence") or "").strip()
        is_third_party = bool(agent.get("is_third_party"))

        result["agent_note"] = note
        result["agent_evidence"] = evidence

        if agent.get("found") and agent.get("url"):
            confidence = "medium" if is_third_party else "high"
            result["early_admission_url"] = agent["url"]
            result["early_admission_title"] = str(agent.get("title") or "")
            result["early_admission_year"] = agent.get("year")
            result["confidence"] = confidence
            result["third_party"] = is_third_party
            # 复核结论优先于自动核验的 evidence 列表
            result["evidence"] = [
                {
                    "text": evidence[:120],
                    "url": agent["url"],
                    "score": None,
                    "source_page": "subagent_verification",
                    "status": 200,
                    "page_has_keyword": not is_third_party,
                    "reached": True,
                    "confidence": confidence,
                    "year": agent.get("year"),
                }
            ]
        else:
            result["confidence"] = "none"
            result["early_admission_url"] = None
            result["early_admission_title"] = ""
            result["early_admission_year"] = None
            result.setdefault("notes", []).append(f"子代理复核：{note or '未找到'}")
            candidates = agent.get("unverified_candidate_urls") or []
            if candidates:
                result.setdefault("notes", []).append(
                    "仅来自搜索索引、未能实际验证的候选：" + "；".join(map(str, candidates))
                )
        if agent.get("joined_early_admission"):
            result["joined_early_admission_agent"] = agent["joined_early_admission"]
        updated += 1

    # 人工下调的特例
    for result in raw["results"]:
        override = MANUAL_OVERRIDES.get(result["name"])
        if override and result.get("early_admission_url"):
            target, reason = override
            result["confidence"] = target
            result.setdefault("notes", []).append(f"人工下调置信度：{reason}")

    summary: dict[str, int] = {}
    for result in raw["results"]:
        summary[result["confidence"]] = summary.get(result["confidence"], 0) + 1

    raw["meta"]["merged_at"] = dt.datetime.now().astimezone().isoformat(
        timespec="seconds"
    )
    raw["meta"]["agent_review_count"] = len(agent_results)
    raw["meta"]["confidence_summary"] = summary
    RAW_PATH.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"[合并] 更新 {updated} 所院校")
    print(f"[置信度] {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
