"""统计局官网国民经济运行情况稿就业部分解析（UnempMixin）。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from . import SourceError
from .html_parser import parse_html


class UnempMixin:
    """城镇调查失业率：国民经济运行情况稿（月度/季度）就业部分。"""

    # 就业部分句子 -> (kind, pattern, unit)；正文数字与单位间常有空格，用 \s* 容忍。
    # 分年龄组（16—24/25—29/30—59 岁）句子仅在数据发布库或历史稿出现，
    # 新闻稿缺失时按缺失处理，不视为解析失败
    _UNEMP_SENTENCES = (
        ("unemp_rate", re.compile(
            r"(\d{1,2})\s*月份，全国城镇调查失业率为\s*([\d\.]+)\s*%"), "%"),
        ("lab_avg", re.compile(
            r"全国城镇调查失业率平均值为\s*([\d\.]+)\s*%"), "%"),
        ("lab_local", re.compile(
            r"本地户籍劳动力调查失业率为\s*([\d\.]+)\s*%"), "%"),
        ("lab_migrant", re.compile(
            r"外来户籍劳动力调查失业率为\s*([\d\.]+)\s*%"), "%"),
        ("lab_agri", re.compile(
            r"外来农业户籍劳动力调查失业率为\s*([\d\.]+)\s*%"), "%"),
        ("lab_31cities", re.compile(
            r"31\s*个大城市城镇调查失业率为\s*([\d\.]+)\s*%"), "%"),
        ("lab_hours", re.compile(
            r"全国企业就业人员周平均工作时间为\s*([\d\.]+)\s*小时"), "小时"),
        ("lab_1624", re.compile(
            r"16\s*[—\-]\s*24\s*岁[^。；;]{0,60}?失业率[^。；;]{0,30}?([\d\.]+)\s*%"), "%"),
        ("lab_2529", re.compile(
            r"25\s*[—\-]\s*29\s*岁[^。；;]{0,60}?失业率[^。；;]{0,30}?([\d\.]+)\s*%"), "%"),
        ("lab_3059", re.compile(
            r"30\s*[—\-]\s*59\s*岁[^。；;]{0,60}?失业率[^。；;]{0,30}?([\d\.]+)\s*%"), "%"),
    )

    def fetch_unemp(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """城镇调查失业率：国民经济运行情况稿（月度/季度）就业部分。

        数据期由核心句月份 + 链接目录年份（如 /202610/）推断，
        发布月早于数据月时（如 12 月数据次年 1 月发布）年份减一。
        """
        url, text = self.find_unemp_release_url()
        if not url:
            raise SourceError("统计局官网未找到国民经济运行情况新闻稿链接")
        body = self._fetch_html(url)
        if not body:
            raise SourceError("国民经济运行情况新闻稿页面为空")
        plain = parse_html(body).text()
        rows: List[Dict[str, Any]] = []
        core_month: Optional[int] = None
        for kind, pattern, unit in self._UNEMP_SENTENCES:
            match = pattern.search(plain)
            if not match:
                continue
            group = 2 if kind == "unemp_rate" else 1
            try:
                value = float(match.group(group))
            except (ValueError, IndexError):
                continue
            if kind == "unemp_rate":
                core_month = int(match.group(1))
            rows.append({"period": "", "kind": kind, "city": "",
                         "value": value, "unit": unit})
        if core_month is None:
            raise SourceError("国民经济运行情况稿中未解析到城镇调查失业率")
        period = self._unemp_period(url, core_month)
        for row in rows:
            row["period"] = period
        return {"rows": rows,
                "source_label": "国家统计局官网·国民经济运行情况（就业部分）",
                "period": period}

    @staticmethod
    def _unemp_period(url: str, core_month: int) -> str:
        match = re.search(r"/(\d{4})(\d{2})/", url or "")
        year = int(match.group(1)) if match else 0
        publish_month = int(match.group(2)) if match else 0
        if year and publish_month and publish_month < core_month:
            year -= 1
        return "{}-{:0>2}".format(year, core_month) if year else ""
