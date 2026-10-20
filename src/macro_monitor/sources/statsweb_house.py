"""统计局官网 70 城房价月度报告解析（HouseMixin）。"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from . import SourceError
from .html_parser import parse_html
from .statsweb_patterns import HOUSE_LINK_PATTERN


class HouseMixin:
    """70 城房价：新建/二手两栏 35 城表 + 分面积段聚合。"""

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
