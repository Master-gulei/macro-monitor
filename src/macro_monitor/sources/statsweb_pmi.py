"""统计局官网 PMI 报告分项细项解析（PmiMixin）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from . import SourceError
from .html_parser import parse_html
from .statsweb_patterns import NEWS_LINK_PATTERNS, _MONTH_CELL


class PmiMixin:
    """PMI 报告分项细项：时间序列表按列名取最新值。"""

    # PMI 时间序列表组特征单元格 -> spec 中的 table 序号
    _PMI_TABLE_FEATURES = {"生产": 0, "采购量": 1, "商务活动": 2, "存货": 3}

    @staticmethod
    def _pmi_time_series(tables: List[List[List[str]]]) -> Dict[int, List[
            Tuple[List[str], List[str], str]]]:
        """PMI 报告为时间序列表：行为月份（如「2025年9月」），列为指标。

        每张表取「首个数据行前最后一行」作表头、最后一个数据行作最新值；
        页面尾部会重复渲染同一组表，按「表头 + 数据行」签名去重；
        表组序号由表头特征单元格映射（生产/采购量/商务活动/存货）。
        返回 {表组序号: [(表头, 最新数据行, 期间)]}。
        """
        found: Dict[int, List[Tuple[List[str], List[str], str]]] = {}
        seen = set()
        for table in tables:
            if len(table) < 2:
                continue
            header_row: Optional[List[str]] = None
            data_row: Optional[List[str]] = None
            period = ""
            for row in table:
                if not row:
                    continue
                first = row[0].strip()
                match = _MONTH_CELL.match(first)
                if match:
                    data_row = row
                    period = "{}-{:0>2}".format(match.group(1), int(match.group(2)))
                    continue
                if first == "单位：%" or not any(cell.strip() for cell in row):
                    continue
                if data_row is None:
                    header_row = row
            if header_row is None or data_row is None:
                continue
            group = None
            for cell in header_row:
                if cell in PmiMixin._PMI_TABLE_FEATURES:
                    group = PmiMixin._PMI_TABLE_FEATURES[cell]
                    break
            if group is None:
                continue
            key = "|".join(header_row) + "||" + "|".join(data_row)
            if key in seen:
                continue
            seen.add(key)
            found.setdefault(group, []).append((header_row, data_row, period))
        return found

    def fetch_pmi_detail(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """PMI 报告分项细项：时间序列表按列名取最新值。

        spec 字段：
          news: 链接 pattern 键（pmi）
          rows: [{"kind", "name", "table"}]，table 为表组序号：
                0=制造业构成、1=制造业其他、2=非制造业构成、3=非制造业其他
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
        series_by_group = self._pmi_time_series(parse_html(body).tables)
        rows: List[Dict[str, Any]] = []
        for item in spec.get("rows") or []:
            series = series_by_group.get(int(item.get("table", 0))) or []
            if not series:
                continue
            header_row, data_row, period = series[0]
            name = str(item["name"])
            if name not in header_row:
                continue
            col = header_row.index(name) + (len(data_row) - len(header_row))
            if col >= len(data_row):
                continue
            try:
                value = float(data_row[col])
            except ValueError:
                continue
            rows.append({"period": period, "kind": str(item["kind"]), "city": "",
                         "value": value, "unit": str(item.get("unit") or "")})
        if not rows:
            raise SourceError("PMI 分项细项解析为空: {}".format(spec.get("news")))
        return {"rows": rows, "source_label": str(spec.get("source_label") or ""),
                "period": rows[0]["period"]}
