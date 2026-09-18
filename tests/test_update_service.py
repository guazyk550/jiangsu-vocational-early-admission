"""``UpdateService`` 的行为测试。

重点验证需求中的硬约束：
- ``update_url`` 为空 → 完全不联网；
- 网络失败 / 远程数据为空 / 非法 JSON → **本地数据保持不变**；
- 更新成功 → 覆盖前先备份，且可立即被仓储读到新数据；
- 远程数据不新 → 保持本地不变。
"""

from __future__ import annotations

import http.server
import json
import threading
from pathlib import Path

import pytest

from src.data.school_repository import SchoolRepository
from src.services.config_service import ConfigService
from src.services.update_service import (
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_UPDATED,
    STATUS_UP_TO_DATE,
    UpdateService,
    validate_remote_payload,
)

LOCAL_DATA = {
    "meta": {"data_year": 2026, "generated_at": "2026-09-18T10:00:00+08:00", "count": 2},
    "schools": [
        {"id": "local-1", "name": "本地院校一", "city": "南京"},
        {"id": "local-2", "name": "本地院校二", "city": "苏州"},
    ],
}

RESPONSES = {
    "/empty.json": json.dumps({"meta": {}, "schools": []}, ensure_ascii=False),
    "/bad.json": "{ this is not json",
    "/valid.json": json.dumps(
        {
            "meta": {"data_year": 2027, "generated_at": "2099-01-01T00:00:00+08:00"},
            "schools": [
                {"id": "new-1", "name": "新院校一", "city": "常州"},
                {"id": "new-2", "name": "新院校二", "city": "无锡"},
                {"id": "new-3", "name": "新院校三", "city": "无锡"},
            ],
        },
        ensure_ascii=False,
    ),
    "/stale.json": json.dumps(
        {
            "meta": {"generated_at": "2000-01-01T00:00:00+08:00"},
            "schools": [{"id": "old-1", "name": "陈旧数据", "city": "徐州"}],
        },
        ensure_ascii=False,
    ),
    "/missing-name.json": json.dumps(
        {"meta": {}, "schools": [{"id": "x"}, {"name": ""}]}, ensure_ascii=False
    ),
}


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - 基类命名
        body = RESPONSES.get(self.path)
        if body is None:
            self.send_error(404)
            return
        payload = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args: object) -> None:  # 静音
        return


@pytest.fixture()
def server_url() -> str:
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture()
def repo(tmp_path: Path) -> SchoolRepository:
    data_file = tmp_path / "schools.json"
    data_file.write_text(json.dumps(LOCAL_DATA, ensure_ascii=False), encoding="utf-8")
    return SchoolRepository(data_file)


def make_service(tmp_path: Path, repo: SchoolRepository, url: str) -> UpdateService:
    config_path = tmp_path / "config.json"
    config = ConfigService(config_path)
    config.load()
    loaded = config.load()
    loaded.update_url = url
    config.save(loaded)
    return UpdateService(config, repo, timeout=5.0)


def local_names(repo: SchoolRepository) -> list[str]:
    return [s.name for s in repo.load(force=True).schools]


# --------------------------------------------------------------------- 用例
def test_skips_without_url(tmp_path: Path, repo: SchoolRepository) -> None:
    service = make_service(tmp_path, repo, "")
    result = service.check()
    assert result.status == STATUS_SKIPPED
    assert local_names(repo) == ["本地院校一", "本地院校二"]


def test_rejects_malformed_url(tmp_path: Path, repo: SchoolRepository) -> None:
    service = make_service(tmp_path, repo, "ftp://example.com/data.json")
    result = service.check()
    assert result.status == STATUS_FAILED
    assert local_names(repo) == ["本地院校一", "本地院校二"]


def test_network_failure_keeps_local_data(
    tmp_path: Path, repo: SchoolRepository
) -> None:
    # 端口 1 上不会有服务：必然连接失败
    service = make_service(tmp_path, repo, "http://127.0.0.1:1/schools.json")
    result = service.check()
    assert result.status == STATUS_FAILED
    assert local_names(repo) == ["本地院校一", "本地院校二"]


def test_empty_remote_data_never_overwrites(
    tmp_path: Path, repo: SchoolRepository, server_url: str
) -> None:
    service = make_service(tmp_path, repo, f"{server_url}/empty.json")
    result = service.check()
    assert result.status == STATUS_FAILED
    assert "为空" in result.message or "拒绝" in result.message
    assert local_names(repo) == ["本地院校一", "本地院校二"]


def test_bad_json_never_overwrites(
    tmp_path: Path, repo: SchoolRepository, server_url: str
) -> None:
    service = make_service(tmp_path, repo, f"{server_url}/bad.json")
    result = service.check()
    assert result.status == STATUS_FAILED
    assert local_names(repo) == ["本地院校一", "本地院校二"]


def test_records_without_name_rejected() -> None:
    payload = json.loads(RESPONSES["/missing-name.json"])
    acceptable, message, count, _ = validate_remote_payload(payload)
    assert not acceptable
    assert count == 0
    assert "拒绝" in message


def test_successful_update_replaces_and_backs_up(
    tmp_path: Path, repo: SchoolRepository, server_url: str
) -> None:
    service = make_service(tmp_path, repo, f"{server_url}/valid.json")
    result = service.check()
    assert result.status == STATUS_UPDATED
    assert result.local_count == 2 and result.remote_count == 3
    assert local_names(repo) == ["新院校一", "新院校二", "新院校三"]
    backup = Path(repo.load().source_path).with_suffix(".json.bak")
    assert backup.exists()
    assert "本地院校一" in backup.read_text(encoding="utf-8")


def test_stale_remote_data_keeps_local(
    tmp_path: Path, repo: SchoolRepository, server_url: str
) -> None:
    service = make_service(tmp_path, repo, f"{server_url}/stale.json")
    result = service.check()
    assert result.status == STATUS_UP_TO_DATE
    assert local_names(repo) == ["本地院校一", "本地院校二"]


def test_404_keeps_local(tmp_path: Path, repo: SchoolRepository, server_url: str) -> None:
    service = make_service(tmp_path, repo, f"{server_url}/nope.json")
    result = service.check()
    assert result.status == STATUS_FAILED
    assert local_names(repo) == ["本地院校一", "本地院校二"]
