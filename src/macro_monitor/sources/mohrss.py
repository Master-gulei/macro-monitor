from __future__ import annotations

import re
import urllib.parse
from typing import Any, Dict, Optional

from ..fetch import SafeFetcher
from . import SourceError
from .statsweb import parse_html

# 人力资源社会保障部：季度例行新闻发布会实录（城镇新增就业累计值）

# 季度词 -> 累计期截至月份
_QUARTER_END = {"一季度": 3, "二季度": 6, "三季度": 9, "四季度": 12,
                "上半年": 6, "前三季度": 9, "全年": 12}
_QUARTER_WORDS = re.compile(r"一季度|二季度|三季度|四季度|上半年|前三季度")


class MohrssSource:
    """人力资源社会保障部官网（www.mohrss.gov.cn）新闻发布会实录解析。"""

    def __init__(self, fetcher: SafeFetcher, config: Dict[str, Any]):
        self.fetcher = fetcher
        self.config = config
        self.base = str(config.get("mohrss", {}).get(
            "base_url", "https://www.mohrss.gov.cn")).rstrip("/")

    def _fetch_html(self, url: str) -> Optional[bytes]:
        return self.fetcher.fetch(url, mode="automatic", purpose="mohrss_page",
                                  accept="text/html,application/xhtml+xml")

    def _find_press_url(self, parser: Any) -> Any:
        """在页面链接中找第一个季度新闻发布会链接，返回 (绝对 URL, 链接文本)。

        相对链接基于配置的 base_url 拼装，镜像部署时同样生效。
        """
        for href, text in parser.links:
            if "新闻发布" in text and _QUARTER_WORDS.search(text):
                return urllib.parse.urljoin(self.base + "/", href), text
        return None, None

    @staticmethod
    def _parse_new_jobs(plain: str) -> Optional[float]:
        """从发布会实录正文解析全国城镇新增就业累计值（万人）。

        (?!以上) 排除「全年城镇新增就业 1200 万人以上」之类的目标表述。
        """
        for pattern in (re.compile(r"全国城镇新增就业\s*([\d,]+(?:\.\d+)?)\s*万人(?!以上)"),
                        re.compile(r"城镇新增就业\s*([\d,]+(?:\.\d+)?)\s*万人(?!以上)")):
            match = pattern.search(plain)
            if match:
                try:
                    return float(match.group(1).replace(",", ""))
                except ValueError:
                    return None
        return None

    @staticmethod
    def _press_period(title: str, plain: str) -> str:
        """数据期 = 标题年份 + 累计截至月（正文「1—X月」优先，其次标题季度词）。"""
        year_match = re.search(r"(20\d{2})年", title or "")
        year = int(year_match.group(1)) if year_match else 0
        span_match = re.search(r"1\s*—\s*(\d{1,2})\s*月[^。；;]{0,40}?新增就业", plain or "")
        if not span_match:
            span_match = re.search(r"1\s*—\s*(\d{1,2})\s*月", plain or "")
        month = int(span_match.group(1)) if span_match else 0
        if not month:
            quarter_match = _QUARTER_WORDS.search(title or "")
            month = _QUARTER_END.get(quarter_match.group(0), 0) if quarter_match else 0
        return "{}-{:0>2}".format(year, month) if year and month else ""

    def fetch_new_jobs(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """城镇新增就业（累计，万人）：季度例行新闻发布会实录。

        官网首页为动态渲染（JS 壳）或部署反爬时本方法抛 SourceError，
        由流水线按指标级容错处理，并在看板/解读中注明缺失。
        """
        body = self._fetch_html(self.base + "/")
        if not body:
            raise SourceError("人社部官网首页无法访问")
        parser = parse_html(body)
        url, title = self._find_press_url(parser)
        if not url:
            raise SourceError("人社部官网未找到季度新闻发布会链接")
        press = self._fetch_html(url)
        if not press:
            raise SourceError("新闻发布会实录页面为空")
        plain = parse_html(press).text()
        value = self._parse_new_jobs(plain)
        if value is None:
            raise SourceError("新闻发布会实录中未解析到城镇新增就业数据")
        period = self._press_period(title or "", plain)
        rows = [{"period": period, "kind": "accum", "city": "",
                 "value": value, "unit": "万人"}]
        return {"rows": rows,
                "source_label": "人力资源社会保障部官网·季度新闻发布会实录",
                "period": period}
