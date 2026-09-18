"""百度地图 URL 生成（不要求用户安装百度地图客户端）。

策略
----
1. **优先**用百度地图 URI 接口生成「驾车路线」页面：
   ``https://api.map.baidu.com/direction?origin=...&destination=...&mode=driving&region=...``
   起点为参照点（默认常州武进洛阳高级中学），终点为当前院校，出行方式为驾车。
   有经纬度时使用 ``latlng:纬度,经度|name:名称`` 形式（更精准），否则退回纯文字地址。
2. 若院校信息不足以生成路线，则退化为**地点搜索页**：
   ``https://map.baidu.com/search/<关键词>``，让用户至少能看到学校位置。

所有中文/特殊字符一律走 ``urllib.parse.quote`` / ``urlencode``，**不手工拼接 URL**。
"""

from __future__ import annotations

from typing import Iterable
from urllib.parse import quote, urlencode

from src.models.origin import OriginPoint
from src.models.school import School
from src.services.browser_service import BrowserService, OpenOutcome

#: 百度地图 URI 接口（唤醒网页版/客户端做路线规划）
BAIDU_DIRECTION_ENDPOINT = "https://api.map.baidu.com/direction"
#: 百度地图网页版地点搜索
BAIDU_SEARCH_ENDPOINT = "https://map.baidu.com/search/"
#: URI 接口要求的来源标识
BAIDU_SRC = "webapp.jsvoc-nav"

MODE_DRIVING = "driving"


def _text(value: str) -> str:
    return (value or "").strip()


def _place_parameter(name: str, latitude: float | None, longitude: float | None) -> str:
    """构造百度 URI 的 origin/destination 参数值。

    有坐标时用 ``latlng:纬度,经度|name:名称``（百度要求纬度在前）；否则只用名称，
    由 ``region`` 兜底消歧。

    ⚠️ 这里**不做**手工 quote：整个参数值交给 ``urlencode`` 统一编码，
    否则 ``|`` ``:`` 与中文会被 URL 编码两次（%25E4…），百度端无法还原。
    """
    clean = _text(name)
    if latitude is not None and longitude is not None:
        return f"latlng:{latitude},{longitude}|name:{clean}"
    return clean


class MapService:
    """生成并打开百度地图链接。"""

    def __init__(
        self,
        origin: OriginPoint | None = None,
        region: str = "江苏",
        browser: BrowserService | None = None,
    ) -> None:
        self.origin = origin
        self.region = region
        self.browser = browser or BrowserService()

    # -------------------------------------------------------------- URL 生成
    def direction_url(self, school: School) -> str:
        """生成「参照点 → 该校」的驾车路线 URL。"""
        origin_name = self.origin.name if self.origin else ""
        origin_lat = self.origin.latitude if self.origin else None
        origin_lon = self.origin.longitude if self.origin else None

        params = {
            "origin": _place_parameter(origin_name, origin_lat, origin_lon),
            "destination": _place_parameter(
                school.name, school.latitude, school.longitude
            ),
            "mode": MODE_DRIVING,
            "region": self.region,
            "output": "html",
            "src": BAIDU_SRC,
        }
        return f"{BAIDU_DIRECTION_ENDPOINT}?{urlencode(params, safe=':|')}"

    def search_url(self, school: School) -> str:
        """生成百度地图地点搜索 URL（关键词 = 校名 + 地址，便于消歧）。"""
        keyword = _text(school.name)
        if school.address:
            keyword = f"{keyword} {_text(school.address)}"
        params = {
            "querytype": "s",
            "wd": keyword,
            "region": self.region,
            "src": BAIDU_SRC,
        }
        return f"{BAIDU_SEARCH_ENDPOINT}{quote(keyword, safe='')}?{urlencode(params)}"

    def candidate_urls(self, school: School) -> list[str]:
        """按优先级返回可尝试的链接（路线 → 搜索）。"""
        return [self.direction_url(school), self.search_url(school)]

    # -------------------------------------------------------------- 打开动作
    def open_directions(self, school: School) -> OpenOutcome:
        """打开驾车路线；失败则退化到地点搜索页。"""
        urls: Iterable[str] = self.candidate_urls(school)
        return self.browser.open_first(urls)

    def open_search(self, school: School) -> OpenOutcome:
        """只打开地点搜索页。"""
        return self.browser.open(self.search_url(school))
