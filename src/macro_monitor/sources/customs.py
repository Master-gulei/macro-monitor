from __future__ import annotations

import re
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

from ..fetch import SafeFetcher
from . import SourceError
from .statsweb import parse_html

# 海关总署官网：统计快讯（进出口总值表）与外贸指数（出口价格指数）
# 注意：部分网络环境无法访问海关官网（超时/风控），此时该源失败并由流水线降级。

KUIXUN_LINK_PATTERN = re.compile(r"(\d{4})年(\d{1,2})月全国进出口总值表（人民币值）")
TRADE_INDEX_LINK_PATTERN = re.compile(r"(\d{4})年(\d{1,2})月中国外贸指数")


class CustomsSource:
    """海关总署官网页面解析（进出口总值快讯 + 外贸指数）。"""

    def __init__(self, fetcher: SafeFetcher, config: Dict[str, Any]):
        self.fetcher = fetcher
        self.config = config
        cfg = config.get("customs") or {}
        self.kuaixun_index = str(cfg.get("kuaixun_index", ""))
        self.trade_index_page = str(cfg.get("trade_index_page", ""))

    def _fetch_html(self, url: str) -> Optional[bytes]:
        return self.fetcher.fetch(url, mode="automatic", purpose="customs_page",
                                  accept="text/html,application/xhtml+xml")

    def _first_link(self, index_url: str, pattern: re.Pattern, referer: str) -> Tuple[
            Optional[str], Optional[str]]:
        body = self._fetch_html(index_url)
        if not body:
            raise SourceError("海关官网列表页为空")
        parser = parse_html(body)
        for href, text in parser.links:
            if pattern.search(text):
                return urllib.parse.urljoin(index_url, href), text
        raise SourceError("海关官网列表页中未找到目标链接")

    # ---------- 进出口总值 ----------

    def fetch_trade(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        url, text = self._first_link(
            self.kuaixun_index, KUIXUN_LINK_PATTERN, "https://www.customs.gov.cn/")
        body = self._fetch_html(url)
        if not body:
            raise SourceError("进出口总值快讯页面为空")
        parser = parse_html(body)
        rows: List[Dict[str, Any]] = []
        row_names = {"进出口总值": "value", "出口总值": "export", "进口总值": "import"}
        for table in parser.tables:
            for row in table:
                cells = [cell for cell in row if cell]
                if len(cells) < 3:
                    continue
                name = cells[0]
                if name not in row_names:
                    continue
                try:
                    value = float(cells[1].replace(",", ""))
                except (ValueError, IndexError):
                    continue
                kind = row_names[name]
                rows.append({"period": "", "kind": kind, "city": "",
                             "value": value, "unit": "亿元"})
                if kind == "value" and len(cells) >= 3:
                    try:
                        yoy = float(cells[2].replace(",", "").replace("%", ""))
                        rows.append({"period": "", "kind": "yoy", "city": "",
                                     "value": yoy, "unit": "%"})
                    except ValueError:
                        pass
        if not rows:
            raise SourceError("进出口总值快讯表格中没有解析到数据")
        match = KUIXUN_LINK_PATTERN.search(text or "")
        period = "{}-{:0>2}".format(match.group(1), int(match.group(2))) if match else ""
        return {"rows": rows,
                "source_label": "海关总署官网·统计快讯（人民币值）",
                "period": period}

    # ---------- 外贸指数（出口价格指数） ----------

    def fetch_trade_index(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        url, text = self._first_link(
            self.trade_index_page, TRADE_INDEX_LINK_PATTERN, "https://tjs.customs.gov.cn/")
        body = self._fetch_html(url)
        if not body:
            raise SourceError("外贸指数页面为空")
        parser = parse_html(body)
        # 总指数表：行首为"出口价格指数"（或含"价格指数"的合计行），取第一个数值单元格
        for table in parser.tables:
            for row in table:
                cells = [cell for cell in row if cell]
                if len(cells) < 2:
                    continue
                if "价格指数" not in cells[0] or "出口" not in cells[0]:
                    continue
                for cell in cells[1:]:
                    match = re.match(r"^(\d+(?:\.\d+)?)$", cell.strip())
                    if match:
                        rows = [{"period": "", "kind": "value", "city": "",
                                 "value": float(match.group(1)),
                                 "unit": "上年同月=100"}]
                        period_match = TRADE_INDEX_LINK_PATTERN.search(text or "")
                        period = "{}-{:0>2}".format(period_match.group(1),
                                                    int(period_match.group(2))) \
                            if period_match else ""
                        return {"rows": rows,
                                "source_label": "海关总署官网·中国外贸指数",
                                "period": period}
        raise SourceError("外贸指数页面中没有解析到出口价格指数")
