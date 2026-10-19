from __future__ import annotations

import re
import urllib.parse
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple

from ..fetch import SafeFetcher
from . import SourceError

# 统计局官网：数据发布列表与月度报告正文（70 城房价、工业企业利润、
# 新闻稿分类细项、国民经济运行情况就业部分及 PMI 分项指数）

HOUSE_LINK_PATTERN = re.compile(
    r"(\d{4})年(\d{1,2})月份70个大中城市商品住宅销售价格变动情况")
PROFIT_LINK_PATTERN = re.compile(
    r"(\d{4})年1—(\d{1,2})月份全国规模以上工业企业利润")
# 城镇调查失业率：2026 年起不再单独发布，内嵌在「国民经济运行情况」新闻稿
# （/sj/zxfbhjd/）就业段落；月度稿如「8月份国民经济运行平稳」、
# 季度稿如「前三季度经济运行总体平稳」，需跳过「答记者问」链接
UNEMP_LINK_PATTERN = re.compile(r"(\d{1,2})月份国民经济")
UNEMP_QUARTER_PATTERN = re.compile(r"(一季度|上半年|前三季度)经济")
# 新闻稿分类细项：链接标题 pattern（retail 为累计期标题，如「1—9月份」）
NEWS_LINK_PATTERNS: Dict[str, re.Pattern] = {
    "cpi": re.compile(r"(\d{4})年(\d{1,2})月份居民消费价格"),
    "ppi": re.compile(r"(\d{4})年(\d{1,2})月份工业生产者出厂价格"),
    "indva": re.compile(r"(\d{4})年(\d{1,2})月份规模以上工业增加值增长"),
    "retail": re.compile(r"(\d{4})年1—(\d{1,2})月份社会消费品零售总额增长"),
    "pmi": re.compile(r"(\d{4})年(\d{1,2})月中国采购经理指数运行情况"),
}
WHITESPACE = re.compile(r"[\s\u3000\u00a0]+")
NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")
_SECTION_NO = re.compile(r"^[一二三四五六七八九十]+、")
_MONTH_CELL = re.compile(r"^(\d{4})年(\d{1,2})月$")


class _ContentParser(HTMLParser):
    """提取页面里的链接、表格与纯文本（供新闻稿解析使用）。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: List[Tuple[str, str]] = []   # (href, text)
        self.tables: List[List[List[str]]] = []  # 每个表格: 行 -> 单元格文本
        self.text_parts: List[str] = []
        self._current_link: Optional[Tuple[Optional[str], List[str]]] = None
        self._table: Optional[List[List[str]]] = None
        self._row: Optional[List[str]] = None
        self._cell: Optional[List[str]] = None
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attributes = dict(attrs)
        if tag in ("script", "style"):
            self._skip_depth += 1
            return
        if tag == "a" and attributes.get("href"):
            self._current_link = (attributes.get("href"), [])
        elif tag == "table" and self._table is None:
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "a" and self._current_link is not None:
            href, parts = self._current_link
            text = WHITESPACE.sub("", "".join(parts))
            if text:
                self.links.append((href or "", text))
            self._current_link = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None
        elif tag == "tr" and self._row is not None:
            if self._table is not None:
                self._table.append(self._row)
            self._row = None
        elif tag in ("td", "th") and self._cell is not None:
            if self._row is not None:
                self._row.append(WHITESPACE.sub("", "".join(self._cell)))
            self._cell = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._current_link is not None:
            self._current_link[1].append(data)
        if self._cell is not None:
            self._cell.append(data)
        if self._table is None and self._row is None:
            self.text_parts.append(data)

    def text(self) -> str:
        return WHITESPACE.sub(" ", " ".join(self.text_parts))


def parse_html(body: bytes) -> _ContentParser:
    parser = _ContentParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    return parser


class StatsWebSource:
    """国家统计局官网（www.stats.gov.cn）新闻稿解析。"""

    def __init__(self, fetcher: SafeFetcher, config: Dict[str, Any]):
        self.fetcher = fetcher
        self.config = config
        cfg = config.get("statsweb") or {}
        self.base = str(cfg.get("base_url", "https://www.stats.gov.cn")).rstrip("/")
        self.list_path = str(cfg.get("list_path", "/sj/zxfb/"))
        self.hjd_list_path = str(cfg.get("hjd_list_path", "/sj/zxfbhjd/"))
        self.max_list_pages = int(cfg.get("max_list_pages", 3))

    def _fetch_html(self, url: str, optional_404: bool = False) -> Optional[bytes]:
        return self.fetcher.fetch(url, mode="automatic", purpose="stats_page",
                                  accept="text/html,application/xhtml+xml",
                                  optional_404=optional_404)

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
        """在数据发布列表中找第一个匹配标题的链接，返回 (绝对 URL, 链接文本)。"""
        for page in range(self.max_list_pages):
            url = self._list_page(page)
            body = self._fetch_html(url, optional_404=True)
            if not body:
                continue
            parser = parse_html(body)
            for href, text in parser.links:
                match = pattern.search(text)
                if match:
                    return urllib.parse.urljoin(url, href), text
        return None, None

    def find_unemp_release_url(self) -> Tuple[Optional[str], Optional[str]]:
        """在国民经济运行情况列表（/sj/zxfbhjd/）中找月度/季度运行情况稿，跳过答记者问。"""
        for page in range(self.max_list_pages):
            url = self._hjd_list_page(page)
            body = self._fetch_html(url, optional_404=True)
            if not body:
                continue
            parser = parse_html(body)
            for href, text in parser.links:
                if "答记者问" in text:
                    continue
                if UNEMP_LINK_PATTERN.search(text) or UNEMP_QUARTER_PATTERN.search(text):
                    return urllib.parse.urljoin(url, href), text
        return None, None

    # ---------- 70 城房价 ----------

    def fetch_house(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        url, text = self.find_release_url(HOUSE_LINK_PATTERN)
        if not url:
            raise SourceError("统计局官网未找到 70 城房价月度报告链接")
        body = self._fetch_html(url)
        if not body:
            raise SourceError("70 城房价月度报告页面为空")
        parser = parse_html(body)
        new_rows, second_rows = self._parse_house_tables(parser.tables)
        if not new_rows:
            raise SourceError("70 城房价月度报告中没有解析到城市数据")
        rows: List[Dict[str, Any]] = []
        for city, mom, yoy in new_rows:
            rows.append({"period": "", "kind": "city_mom", "city": city, "value": mom,
                         "unit": ""})
            rows.append({"period": "", "kind": "city_yoy", "city": city, "value": yoy,
                         "unit": ""})
        for city, mom, yoy in second_rows:
            rows.append({"period": "", "kind": "city_mom_2nd", "city": city, "value": mom,
                         "unit": ""})
            rows.append({"period": "", "kind": "city_yoy_2nd", "city": city, "value": yoy,
                         "unit": ""})
        rows.extend(self._parse_area_tables(parser.tables))
        return {"rows": rows,
                "source_label": "国家统计局官网·70城房价月度报告",
                "period": self._period_from_link(text or "")}

    @staticmethod
    def _parse_house_tables(tables: List[List[List[str]]]) -> Tuple[
            List[Tuple[str, float, float]], List[Tuple[str, float, float]]]:
        """解析 70 城表格，返回 (新建住宅, 二手住宅)。

        真实页面结构：表1=新建、表2=二手，每张表左右两栏各 35 城
        （表头出现两次「城市」，即两个列组）；页面尾部可能重复渲染同一组表，
        只取文档顺序前两张逻辑表；若前两张内容完全相同则视为重复，二手置空。
        兼容单栏表：无分隔时相邻单栏表累积为同一张逻辑表。
        """
        header_names = ("城市", "环比", "同比", "上月=100", "上年同月=100", "上年同期=100")
        logical: List[List[List[List[str]]]] = []  # 每个逻辑表 = 若干物理表
        current: List[List[List[str]]] = []
        for table in tables:
            if not table:
                continue
            header = [cell for cell in table[0] if cell]
            if "环比" not in header or "同比" not in header:
                if current:
                    logical.append(current)
                    current = []
                continue
            if header.count("城市") >= 2:  # 左右两栏的完整表，独立成表
                if current:
                    logical.append(current)
                    current = []
                logical.append([table])
            else:  # 单栏表：可能与相邻单栏表同属一张逻辑表
                current.append(table)
        if current:
            logical.append(current)

        def parse_group(group: List[List[List[str]]]) -> List[Tuple[str, float, float]]:
            cities: List[Tuple[str, float, float]] = []
            for table in group:
                starts = [i for i, cell in enumerate(table[0]) if cell == "城市"]
                for row in table[1:]:
                    for start in starts:
                        if len(row) < start + 3:
                            continue
                        name = row[start]
                        if name in header_names:
                            continue
                        try:
                            mom, yoy = float(row[start + 1]), float(row[start + 2])
                        except (ValueError, IndexError):
                            continue
                        cities.append((name, mom, yoy))
            return cities

        new = parse_group(logical[0]) if logical else []
        second = parse_group(logical[1]) if len(logical) > 1 else []
        if new and new == second:  # 页面重复渲染同一张表：避免把新建误当二手
            second = []
        return new, second

    @staticmethod
    def _parse_area_tables(tables: List[List[List[str]]]) -> List[Dict[str, Any]]:
        """解析分面积表：前四张（新建左右栏、二手左右栏），聚合全国 70 城平均。

        面积表列：0=城市，1/2/3=90㎡以下 环比/同比/平均，
        4/5/6=90-144㎡ 环比/同比/平均，7/8/9=144㎡以上 环比/同比/平均。
        每表单栏 35 城：新建 = 表1+表2（左右栏），二手 = 表3+表4。
        """
        area_tables: List[List[List[str]]] = []
        for table in tables:
            if not table:
                continue
            header = [cell for cell in table[0] if cell]
            if any("90m2及以下" in cell for cell in header):
                area_tables.append(table)
        if len(area_tables) < 4:
            return []

        def collect(group: List[List[List[str]]]) -> Dict[str, List[float]]:
            sums: Dict[str, List[float]] = {
                "a90_mom": [], "a90_yoy": [], "a90144_mom": [], "a90144_yoy": [],
                "a144_mom": [], "a144_yoy": []}
            for table in group:
                for row in table[1:]:
                    if not row or not row[0] or len(row) < 9 or row[0] == "城市":
                        continue
                    try:
                        sums["a90_mom"].append(float(row[1]))
                        sums["a90_yoy"].append(float(row[2]))
                        sums["a90144_mom"].append(float(row[4]))
                        sums["a90144_yoy"].append(float(row[5]))
                        sums["a144_mom"].append(float(row[7]))
                        sums["a144_yoy"].append(float(row[8]))
                    except ValueError:
                        continue
            return sums

        rows: List[Dict[str, Any]] = []
        for prefix, sums in (("new", collect(area_tables[:2])),
                             ("sec", collect(area_tables[2:4]))):
            for key, values in sums.items():
                if not values:
                    continue
                unit = "上月=100" if key.endswith("mom") else "上年同月=100"
                rows.append({"period": "", "kind": "{}_{}".format(prefix, key),
                             "city": "",
                             "value": round(sum(values) / len(values), 2), "unit": unit})
        return rows

    @staticmethod
    def _period_from_link(text: str) -> str:
        match = HOUSE_LINK_PATTERN.search(text or "")
        if not match:
            return ""
        return "{}-{:0>2}".format(match.group(1), int(match.group(2)))

    # ---------- 工业企业利润 ----------

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
            norm = self._normalize_row_name(name)
            industry_kind = self._PROFIT_INDUSTRY_KINDS.get(norm)
            if industry_kind:
                rows.append({"period": period, "kind": industry_kind, "city": "",
                             "value": yoy, "unit": "%"})
                continue
            type_kinds = self._PROFIT_TYPE_KINDS.get(norm)
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

    # ---------- 新闻稿分类细项 ----------

    @staticmethod
    def _normalize_row_name(name: str) -> str:
        """行名归一化：去「其中：」前缀与「一、」等序号前缀，便于跨月份匹配。"""
        return _SECTION_NO.sub("", name).removeprefix("其中：")

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
                name_to_row[self._normalize_row_name(row[name_col])] = row
        if not name_to_row:
            raise SourceError("新闻稿中未解析到数据表格: {}".format(spec.get("news")))
        rows: List[Dict[str, Any]] = []
        for item in spec.get("rows") or []:
            row = name_to_row.get(self._normalize_row_name(str(item["name"])))
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

    # ---------- 城镇调查失业率（国民经济运行情况稿） ----------

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

    # ---------- PMI 分项细项 ----------

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
                if cell in StatsWebSource._PMI_TABLE_FEATURES:
                    group = StatsWebSource._PMI_TABLE_FEATURES[cell]
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
