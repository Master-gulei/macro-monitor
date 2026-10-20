from __future__ import annotations

import re
import urllib.parse
from typing import Any, Dict, Optional, Tuple

from ..fetch import SafeFetcher
from . import HtmlSource
from .html_parser import parse_html
from .statsweb_house import HouseMixin
from .statsweb_news import NewsDetailMixin
from .statsweb_patterns import (
    HOUSE_LINK_PATTERN,
    NEWS_LINK_PATTERNS,
    PROFIT_LINK_PATTERN,
    UNEMP_ANNUAL_PATTERN,
    UNEMP_LINK_PATTERN,
    UNEMP_QUARTER_PATTERN,
    is_commentary_title,
)
from .statsweb_pmi import PmiMixin
from .statsweb_profit import ProfitMixin
from .statsweb_unemp import UnempMixin

# 统计局官网：数据发布列表与月度报告正文（70 城房价、工业企业利润、
# 新闻稿分类细项、国民经济运行情况就业部分及 PMI 分项指数）。
# 各指标解析逻辑拆分至 statsweb_*.py（Mixin，R1 拆分），本文件只保留
# 列表页定位等核心能力；patterns/parse_html 转发导出以兼容既有引用。

__all__ = ["StatsWebSource", "parse_html", "HOUSE_LINK_PATTERN", "PROFIT_LINK_PATTERN",
           "NEWS_LINK_PATTERNS", "UNEMP_LINK_PATTERN", "UNEMP_QUARTER_PATTERN",
           "UNEMP_ANNUAL_PATTERN"]


class StatsWebSource(HtmlSource, HouseMixin, ProfitMixin, NewsDetailMixin,
                     UnempMixin, PmiMixin):
    """国家统计局官网（www.stats.gov.cn）新闻稿解析。"""

    html_purpose = "stats_page"

    def __init__(self, fetcher: SafeFetcher, config: Dict[str, Any]):
        self.fetcher = fetcher
        self.config = config
        cfg = config.get("statsweb") or {}
        self.base = str(cfg.get("base_url", "https://www.stats.gov.cn")).rstrip("/")
        self.list_path = str(cfg.get("list_path", "/sj/zxfb/"))
        self.hjd_list_path = str(cfg.get("hjd_list_path", "/sj/zxfbhjd/"))
        self.max_list_pages = int(cfg.get("max_list_pages", 3))

    def _list_page(self, page: int) -> str:
        if page <= 0:
            return self.base + self.list_path
        base, _ = self.list_path.rsplit("/", 1) if "/" in self.list_path else (self.list_path, "")
        return self.base + base + "/index_{}.html".format(page)

    def _hjd_list_page(self, page: int) -> str:
        if page <= 0:
            return self.base + self.hjd_list_path
        base, _ = self.hjd_list_path.rsplit("/", 1) if "/" in self.hjd_list_path \
            else (self.hjd_list_path, "")
        return self.base + base + "/index_{}.html".format(page)

    def find_release_url(self, pattern: re.Pattern) -> Tuple[Optional[str], Optional[str]]:
        """在数据发布列表中找第一个匹配标题的链接，返回 (绝对 URL, 链接文本)。

        解读/署名文章与答记者问不含完整数据表，直接跳过。
        """
        for page in range(self.max_list_pages):
            url = self._list_page(page)
            body = self._fetch_html(url, optional_404=True)
            if not body:
                continue
            parser = parse_html(body)
            for href, text in parser.links:
                if is_commentary_title(text):
                    continue
                match = pattern.search(text)
                if match:
                    return urllib.parse.urljoin(url, href), text
        return None, None

    def find_unemp_release_url(self) -> Tuple[Optional[str], Optional[str]]:
        """在国民经济运行情况列表（/sj/zxfbhjd/）中找月度/季度/年度运行情况稿，

        跳过解读/署名文章与答记者问（不含完整就业数据）。
        """
        for page in range(self.max_list_pages):
            url = self._hjd_list_page(page)
            body = self._fetch_html(url, optional_404=True)
            if not body:
                continue
            parser = parse_html(body)
            for href, text in parser.links:
                if is_commentary_title(text):
                    continue
                if (UNEMP_LINK_PATTERN.search(text) or UNEMP_QUARTER_PATTERN.search(text)
                        or UNEMP_ANNUAL_PATTERN.search(text)):
                    return urllib.parse.urljoin(url, href), text
        return None, None
