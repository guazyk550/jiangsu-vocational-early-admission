"""tools 公共工具：零依赖的 HTTP GET / JSON 抓取（带重试与限速）。

只依赖标准库，避免为数据采集脚本额外引入第三方依赖。
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping

#: 使用真实浏览器 UA —— 部分站点会拒绝 Python-urllib 默认 UA
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class FetchError(RuntimeError):
    """抓取失败（网络错误 / HTTP 非 2xx / 重试耗尽）。"""


def smart_decode(raw: bytes, declared_charset: str | None = None) -> str:
    """解码网页字节流。

    很多国内院校网站是 GBK/GB2312 且头部声明不规范，无法用 UTF-8 解码；
    这里按 UTF-8 → GBK → GB18030 → 忽略错误的顺序兜底。
    """
    if declared_charset:
        try:
            return raw.decode(declared_charset, errors="strict")
        except (LookupError, UnicodeDecodeError):
            pass

    for charset in ("utf-8", "gbk", "gb18030"):
        try:
            return raw.decode(charset, errors="strict")
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")



def _build_ssl_context(insecure: bool) -> ssl.SSLContext | None:
    """部分院校网站的 HTTPS 证书链不完整（本校自签/缺中间证书）。

    ``insecure=True`` 时放弃证书校验——**仅用于读取公开招生页面（只读、无凭据传输）**，
    调用方必须把这一事实记入采集笔记。
    """
    if not insecure:
        return None
    return ssl._create_unverified_context()


def http_get(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = 20.0,
    retries: int = 3,
    backoff: float = 1.5,
    insecure: bool = False,
) -> str:
    """GET 一个 URL 并返回文本。

    :param params: 查询参数（会自动做 URL 编码）
    :param retries: 失败重试次数（指数退避）
    :raises FetchError: 全部重试仍失败
    """
    if params:
        query = urllib.parse.urlencode({k: v for k, v in params.items()}, doseq=True)
        url = f"{url}?{query}" if "?" not in url else f"{url}&{query}"

    req_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, text/html, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if headers:
        req_headers.update(headers)

    last_error: Exception | None = None
    context = _build_ssl_context(insecure)
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(url, headers=req_headers, method="GET")
            with urllib.request.urlopen(
                request, timeout=timeout, context=context
            ) as response:
                raw: bytes = response.read()
                return smart_decode(raw, response.headers.get_content_charset())
        except urllib.error.HTTPError as exc:  # 4xx/5xx
            last_error = exc
            # 4xx 多为不可恢复（403/404/412），但仍重试一次以躲过偶发风控
            if exc.code in (400, 404, 410):
                break
        except Exception as exc:  # noqa: BLE001 - 网络层任何异常都统一重试
            last_error = exc

        if attempt < retries:
            time.sleep(backoff ** (attempt + 1))

    raise FetchError(f"GET {url} 失败: {last_error!r}")


def http_get_json(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = 20.0,
    retries: int = 3,
) -> Any:
    """GET 一个返回 JSON 的 URL 并解析。"""
    text = http_get(
        url, params=params, headers=headers, timeout=timeout, retries=retries
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise FetchError(f"GET {url} 返回的不是合法 JSON: {exc}") from exc


def http_probe(
    url: str, *, timeout: float = 12.0, max_bytes: int = 300_000, insecure: bool = False
) -> tuple[int, str]:
    """探测 URL 可达性，返回 ``(HTTP 状态码, 正文前段)``；连接层失败时状态码为 0。

    用于「这个候选链接到底能不能打开」的判定，不重试、不抛异常。
    """
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"}
    )
    try:
        with urllib.request.urlopen(
            request, timeout=timeout, context=_build_ssl_context(insecure)
        ) as response:
            raw: bytes = response.read(max_bytes)
            return response.status, smart_decode(
                raw, response.headers.get_content_charset()
            )
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception:  # noqa: BLE001 - 任何连接层异常都视为不可达
        return 0, ""


def pick(source: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    """从字典中按顺序取第一个「有内容」的值（跳过 None / 空串 / 空列表）。"""
    for key in keys:
        value = source.get(key)
        if value not in (None, "", [], {}):
            return value
    return default


def unwrap(payload: Any) -> Mapping[str, Any]:
    """兼容 ``{"data": {...}}`` 包裹与扁平两种返回结构。"""
    if isinstance(payload, Mapping):
        inner = payload.get("data")
        if isinstance(inner, Mapping) and inner:
            return inner
    return payload if isinstance(payload, Mapping) else {}
