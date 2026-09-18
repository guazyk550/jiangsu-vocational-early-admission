"""浏览器唤起服务。

软件**不内置浏览器**：点击「提前招生官网」「百度地图」时用系统默认浏览器打开
（webbrowser.open）。原因：兼容性最好、学校网站可能依赖复杂 JS/Cookie、用户习惯
自己的浏览器。

本模块只做两件事：URL 合法性校验 + 失败时不抛异常而是返回结果对象，便于 UI
提示「该网站当前无法访问」并提供「复制网址」。
"""

from __future__ import annotations

import webbrowser
from dataclasses import dataclass
from typing import Callable, Iterable
from urllib.parse import urlparse

#: 只允许打开 http/https，杜绝 file:// 等本地协议带来的风险
ALLOWED_SCHEMES = ("http", "https")

#: 占位/无效 URL 的常见形态
INVALID_MARKERS = ("", "#", "javascript:", "about:blank", "null")


@dataclass(frozen=True, slots=True)
class OpenOutcome:
    """一次「打开网页」操作的结果。"""

    ok: bool
    url: str
    message: str = ""

    @property
    def failed(self) -> bool:
        return not self.ok


def is_openable_url(url: str | None) -> bool:
    """判断 URL 是否为可打开的外部链接。"""
    if not url:
        return False
    text = url.strip()
    if text.lower() in INVALID_MARKERS:
        return False
    parsed = urlparse(text)
    return parsed.scheme.lower() in ALLOWED_SCHEMES and bool(parsed.netloc)


class BrowserService:
    """统一的网页打开入口（可注入 opener 便于测试）。"""

    def __init__(self, opener: Callable[[str], bool] | None = None) -> None:
        self._opener = opener or webbrowser.open

    def open(self, url: str | None) -> OpenOutcome:
        """打开一个 URL。永不抛异常。"""
        if not url or not str(url).strip():
            return OpenOutcome(False, "", "没有可打开的链接")
        text = str(url).strip()
        if not is_openable_url(text):
            return OpenOutcome(
                False, text, "链接格式无法识别（仅支持 http/https），可复制后在浏览器中打开"
            )
        try:
            opened = bool(self._opener(text))
        except Exception as exc:  # noqa: BLE001 - 唤起失败不能影响程序
            return OpenOutcome(False, text, f"无法唤起浏览器：{exc}")
        if not opened:
            return OpenOutcome(
                False, text, "该网站当前无法访问，可复制网址稍后重试"
            )
        return OpenOutcome(True, text)

    def open_first(self, urls: Iterable[str | None]) -> OpenOutcome:
        """依次尝试多个候选链接，返回第一个成功的结果。

        用于「提前招生页面 → 招生网 → 官网」这类回退场景。
        """
        last = OpenOutcome(False, "", "没有可打开的链接")
        for url in urls:
            if not url:
                continue
            outcome = self.open(url)
            if outcome.ok:
                return outcome
            last = outcome
        return last
