"""统计局官网新闻稿分类细项解析（NewsDetailMixin）。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from . import SourceError
from .html_parser import parse_html
from .statsweb_patterns import NEWS_LINK_PATTERNS, normalize_row_name


class NewsDetailMixin:
    """新闻稿分类细项：按表格行名取数（CPI/PPI/工业增加值/社零）。"""

    def fetch_news_detail(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """新闻稿分类细项：按表格行名取数。

        spec 字段：
          news: 链接 pattern 键（cpi/ppi/indva/retail）
          rows: [{"kind", "name", "col"}]，col 为 "yoy"（同比列，默认）或 "value"（绝对量列）
          sentences: [{"kind", "pattern"}] 可选，从正文正则取数
        兼容两种表格结构：CPI/PPI 的「环比/同比涨跌幅」表，
        与工业增加值/社零的「指标 | 9月 | 1—9月」表。
        """
        pattern = NEWS_LINK_PATTERNS.get(spec.get("news") or "")
        if pattern is None:
            raise SourceError("未知的新闻稿类型: {}".format(spec.get("news")))
        url, text = self.find_release_url(pattern)
        if not url:
            raise SourceError("统计局官网未找到新闻稿链接: {}".format(spec.get("news")))
        body = self._fetch_html(url)
        if not body:
            raise SourceError("新闻稿页面为空: {}".format(spec.get("news")))
        parser = parse_html(body)
        name_to_row: Dict[str, List[str]] = {}
        value_col: Optional[int] = None
        yoy_col: Optional[int] = None
        for table in parser.tables:
            if len(table) < 2 or not table[0]:
                continue
            header = [cell for cell in table[0] if cell]
            if any("涨跌幅" in cell for cell in header):
                name_col, yoy_col, value_col = 0, 2, None
            elif header and header[0] == "指标":
                name_col, yoy_col, value_col = 0, 2, 1
            else:
                continue
            for row in table[1:]:
                if len(row) <= yoy_col or not row[name_col]:
                    continue
                name_to_row[normalize_row_name(row[name_col])] = row
        if not name_to_row:
            raise SourceError("新闻稿中未解析到数据表格: {}".format(spec.get("news")))
        rows: List[Dict[str, Any]] = []
        for item in spec.get("rows") or []:
            row = name_to_row.get(normalize_row_name(str(item["name"])))
            if row is None:
                continue
            if item.get("col") == "value":
                col = value_col
            else:
                col = yoy_col
            if col is None or len(row) <= col:
                continue
            try:
                value = float(row[col])
            except ValueError:
                continue
            rows.append({"period": "", "kind": str(item["kind"]), "city": "",
                         "value": value, "unit": str(item.get("unit") or "")})
        if spec.get("sentences"):
            plain = parser.text()
            for item in spec["sentences"]:
                match = re.search(item["pattern"], plain)
                if not match:
                    continue
                try:
                    value = float(match.group(1))
                except (ValueError, IndexError):
                    continue
                rows.append({"period": "", "kind": str(item["kind"]), "city": "",
                             "value": value, "unit": str(item.get("unit") or "")})
        if not rows:
            raise SourceError("新闻稿细项解析为空: {}".format(spec.get("news")))
        period_match = pattern.search(text or "")
        period = "{}-{:0>2}".format(period_match.group(1), int(period_match.group(2))) \
            if period_match else ""
        return {"rows": rows, "source_label": str(spec.get("source_label") or ""),
                "period": period}
