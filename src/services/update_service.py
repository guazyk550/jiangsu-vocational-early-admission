"""数据更新（可选功能；``update_url`` 留空则完全不联网）。

安全约束（来自需求）
--------------------
1. 网络失败**不影响程序启动与使用**，继续用本地数据；
2. 更新失败/超时/格式非法 → **绝不覆盖**本地数据；
3. 远程数据为空或结构不合法 → 拒绝写入；
4. 成功写入前先备份原文件（``schools.json.bak``），并原子替换；
5. 记录「数据更新时间」供界面展示。

本模块只提供**同步** ``check()``：GUI 层放在 QThread 里调用，避免界面卡顿。
"""

from __future__ import annotations

import shutil
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src.data.school_repository import SchoolRepository, project_root
from src.models.school import School
from src.services.config_service import ConfigService
from src.services.storage import write_json_atomic

STATUS_SKIPPED = "skipped"
STATUS_UP_TO_DATE = "up_to_date"
STATUS_UPDATED = "updated"
STATUS_FAILED = "failed"

USER_AGENT = "jsvoc-nav/1.0 (+data update check)"


@dataclass(frozen=True, slots=True)
class UpdateResult:
    """一次更新检查的结果。"""

    status: str
    message: str
    remote_count: int = 0
    local_count: int = 0
    url: str = ""
    remote_generated_at: str = ""

    @property
    def ok(self) -> bool:
        return self.status in (STATUS_UPDATED, STATUS_UP_TO_DATE, STATUS_SKIPPED)


def validate_remote_payload(payload: Any) -> tuple[bool, str, int, str]:
    """校验远程数据是否可接受。

    :return: ``(是否可接受, 说明, 有效院校数, 远程生成时间)``
    """
    if isinstance(payload, list):
        items, meta = payload, {}
    elif isinstance(payload, Mapping):
        items = payload.get("schools")
        meta = payload.get("meta") or {}
    else:
        return False, "远程数据顶层结构无法识别", 0, ""

    if not isinstance(items, list) or not items:
        return False, "远程数据为空或缺少 schools 列表（拒绝覆盖本地数据）", 0, ""

    valid = 0
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            continue
        school = School.from_dict(item)
        if not school.name:
            continue
        key = school.id or school.name
        if key in seen:
            continue
        seen.add(key)
        valid += 1

    if valid == 0:
        return False, "远程数据没有可用的院校记录（拒绝覆盖本地数据）", 0, ""
    return True, f"远程数据有效，共 {valid} 所", valid, str(meta.get("generated_at") or "")


class UpdateService:
    """检查并应用远程数据更新。"""

    def __init__(
        self,
        config_service: ConfigService,
        repository: SchoolRepository,
        *,
        timeout: float = 10.0,
    ) -> None:
        self.config_service = config_service
        self.repository = repository
        self.timeout = timeout

    # ---------------------------------------------------------------- 路径
    def write_target(self) -> Path:
        """确定可写的本地数据文件路径。

        若当前数据来自打包内置资源（只读），则写到 exe 同级 ``data/schools.json``。
        """
        try:
            loaded = self.repository.load()
            source = Path(loaded.source_path)
        except Exception:  # noqa: BLE001
            source = project_root() / "data" / "schools.json"

        bundle_dir = getattr(__import__("sys"), "_MEIPASS", None)
        if bundle_dir and str(source).startswith(str(bundle_dir)):
            return project_root() / "data" / "schools.json"
        return source

    # ---------------------------------------------------------------- 检查
    def check(self) -> UpdateResult:
        """执行一次更新检查（同步，可能阻塞网络；请在后台线程调用）。"""
        config = self.config_service.load()
        url = (config.update_url or "").strip()
        if not url:
            return UpdateResult(
                STATUS_SKIPPED,
                "未配置数据更新地址（update_url 为空），已跳过检查",
            )

        if not url.lower().startswith(("http://", "https://")):
            result = UpdateResult(STATUS_FAILED, f"更新地址格式不正确：{url}", url=url)
            self.config_service.mark_update_checked(result.message)
            return result

        local_count = len(self.repository.load().schools)

        # ---- 下载 ----
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                    "Cache-Control": "no-cache",
                },
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(8 * 1024 * 1024)  # 上限 8MB，防止异常大文件
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            result = UpdateResult(
                STATUS_FAILED,
                f"网络请求失败，已继续使用本地数据：{exc}",
                local_count=local_count,
                url=url,
            )
            self.config_service.mark_update_checked(result.message)
            return result

        # ---- 解析与校验 ----
        import json

        try:
            payload = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            result = UpdateResult(
                STATUS_FAILED,
                f"远程数据不是合法 JSON，已继续使用本地数据：{exc}",
                local_count=local_count,
                url=url,
            )
            self.config_service.mark_update_checked(result.message)
            return result

        acceptable, message, remote_count, remote_generated = validate_remote_payload(
            payload
        )
        if not acceptable:
            result = UpdateResult(
                STATUS_FAILED,
                message,
                remote_count=remote_count,
                local_count=local_count,
                url=url,
            )
            self.config_service.mark_update_checked(result.message)
            return result

        # ---- 是否需要写入 ----
        local_meta = self.repository.load().meta
        local_generated = str(local_meta.get("generated_at") or "")
        if remote_generated and local_generated and remote_generated <= local_generated:
            result = UpdateResult(
                STATUS_UP_TO_DATE,
                f"本地数据已是最新（本地 {local_count} 所，远程 {remote_count} 所）",
                remote_count=remote_count,
                local_count=local_count,
                url=url,
                remote_generated_at=remote_generated,
            )
            self.config_service.mark_update_checked(result.message)
            return result

        # ---- 备份 + 原子写入 ----
        target = self.write_target()
        backup = target.with_suffix(target.suffix + ".bak")
        try:
            if target.exists():
                shutil.copy2(target, backup)
        except OSError as exc:
            result = UpdateResult(
                STATUS_FAILED,
                f"备份本地数据失败，未执行更新：{exc}",
                local_count=local_count,
                url=url,
            )
            self.config_service.mark_update_checked(result.message)
            return result

        if not write_json_atomic(target, payload):
            result = UpdateResult(
                STATUS_FAILED,
                f"写入数据文件失败（目录可能不可写）：{target}",
                local_count=local_count,
                url=url,
            )
            self.config_service.mark_update_checked(result.message)
            return result

        self.repository.load(force=True)
        result = UpdateResult(
            STATUS_UPDATED,
            f"数据已更新：{local_count} 所 → {remote_count} 所（原文件已备份为 {backup.name}）",
            remote_count=remote_count,
            local_count=local_count,
            url=url,
            remote_generated_at=remote_generated,
        )
        self.config_service.mark_update_checked(result.message)
        return result
