"""统计局官网工业企业利润月度报告解析（ProfitMixin）。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from . import SourceError
from .html_parser import parse_html
from .statsweb_patterns import PROFIT_LINK_PATTERN, normalize_row_name

# 表格行名 -> 细项 kind（行名已归一化：去「其中：」前缀）
_PROFIT_INDUSTRY_KINDS = {
    "采矿业": "profit_mining_yoy",
    "制造业": "profit_manufacturing_yoy",
    "电力、热力、燃气及水生产和供应业": "profit_utilities_yoy",
}
_PROFIT_TYPE_KINDS = {
    "国有控股企业": ("profit_state_accum", "profit_state_yoy"),
    "股份制企业": ("profit_share_accum", "profit_share_yoy"),
    "外商及港澳台投资企业": ("profit_foreign_accum", "profit_foreign_yoy"),
    "私营企业": ("profit_private_accum", "profit_private_yoy"),
}


class ProfitMixin:
    """工业企业利润：正文正则 + 表格兑底，含分企业类型与分行业细项。"""

    def fetch_profit(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        url, text = self.find_release_url(PROFIT_LINK_PATTERN)
        if not url:
            raise SourceError("统计局官网未找到工业企业利润月度报告链接")
        body = self._fetch_html(url)
        if not body:
            raise SourceError("工业企业利润月度报告页面为空")
        parser = parse_html(body)
        plain = parser.text()
        # 正文里数字与单位之间常有空格（如「利润总额 52719.8 亿元」），用 \s* 容忍
        total_match = re.search(
            r"规模以上工业企业实现利润总额\s*([\d,]+(?:\.\d+)?)\s*亿元", plain)
        yoy_match = re.search(
            r"利润总额\s*[\d,\.]*\s*亿元，同比增长\s*(-?[\d\.]+)\s*%", plain)
        month_match = re.search(
            r"(\d{1,2})月份，规模以上工业企业利润同比增长\s*(-?[\d\.]+)\s*%", plain)
        total_value = float(total_match.group(1).replace(",", "")) if total_match else None
        yoy_value = float(yoy_match.group(1)) if yoy_match else None
        month_value = float(month_match.group(2)) if month_match else None
        table_rows = self._profit_rows_from_tables(parser.tables)
        if total_value is None or yoy_value is None:
            total_row = table_rows.get("总计") or table_rows.get("合计")
            if total_row is not None:
                total_value, yoy_value = total_row
        period_match = PROFIT_LINK_PATTERN.search(text or "")
        period = "{}-{:0>2}".format(period_match.group(1), int(period_match.group(2))) \
            if period_match else ""
        rows: List[Dict[str, Any]] = []
        if total_value is not None:
            rows.append({"period": period, "kind": "accum", "city": "",
                         "value": total_value, "unit": "亿元"})
        if yoy_value is not None:
            rows.append({"period": period, "kind": "accum_yoy", "city": "",
                         "value": yoy_value, "unit": "%"})
        if month_value is not None:
            rows.append({"period": period, "kind": "month_yoy", "city": "",
                         "value": month_value, "unit": "%"})
        # 细项：分企业类型（金额+同比）与分行业（同比）
        for name, (amount, yoy) in table_rows.items():
            norm = normalize_row_name(name)
            industry_kind = _PROFIT_INDUSTRY_KINDS.get(norm)
            if industry_kind:
                rows.append({"period": period, "kind": industry_kind, "city": "",
                             "value": yoy, "unit": "%"})
                continue
            type_kinds = _PROFIT_TYPE_KINDS.get(norm)
            if type_kinds:
                rows.append({"period": period, "kind": type_kinds[0], "city": "",
                             "value": amount, "unit": "亿元"})
                rows.append({"period": period, "kind": type_kinds[1], "city": "",
                             "value": yoy, "unit": "%"})
        if not rows:
            raise SourceError("工业企业利润报告正文中没有解析到数据")
        return {"rows": rows,
                "source_label": "国家统计局官网·工业企业利润月度报告",
                "period": period}

    @staticmethod
    def _profit_rows_from_tables(tables: List[List[List[str]]]) -> Dict[
            str, Tuple[float, float]]:
        """表格解析：返回 {行名: (利润总额金额, 同比)}，含总计与分行业/分类型行。"""
        for table in tables:
            if len(table) < 2:
                continue
            header = [cell for cell in table[0] if cell]
            if "利润总额" not in header:
                continue
            # 列布局：分组占 1 列，其后每个指标组占 2 列（金额 + 同比）
            column = 1 + (header.index("利润总额") - 1) * 2
            found: Dict[str, Tuple[float, float]] = {}
            for row in table[1:]:
                cells = [cell for cell in row if cell]
                if not cells or not cells[0]:
                    continue
                try:
                    total = float(cells[column].replace(",", ""))
                    yoy = float(cells[column + 1].replace(",", ""))
                except (ValueError, IndexError):
                    continue
                found[cells[0]] = (total, yoy)
            if found:
                return found
        return {}
