from __future__ import annotations

import json
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

from ..db import Database
from ..fetch import SafeFetcher
from . import SourceError

TREE_ENDPOINT = "easyquery.htm?m=GetTree&dbcode={dbcode}&wdcode={wdcode}&id={id}"
QUERY_ENDPOINT = "easyquery.htm?m=QueryData&dbcode={dbcode}&rowcode={rowcode}&colcode=sj&wds={wds}&dfwds={dfwds}"

NBS_SOURCE_LABEL = "国家统计局·月度数据库（easyquery）"


def _parse_period(raw: str) -> str:
    """'2025M10' -> '2025-10'；'2025' 原样返回。"""
    raw = str(raw)
    if "M" in raw:
        year, month = raw.split("M", 1)
        return "{}-{:0>2}".format(year, int(month))
    return raw


class NBSSource:
    """国家统计局 easyquery 公开接口（免 key，可能被站点风控拦截，失败即切换兜底源）。"""

    def __init__(self, fetcher: SafeFetcher, db: Database, config: Dict[str, Any]):
        self.fetcher = fetcher
        self.db = db
        self.config = config
        self.base = str(config.get("nbs", {}).get("base_url", "https://data.stats.gov.cn")).rstrip("/")
        self.query_months = int(config.get("nbs", {}).get("query_months", 60))

    # ---------- 通用请求 ----------

    def _fetch_json(self, params: Dict[str, str], purpose: str) -> Any:
        url = self.base + "/easyquery.htm?" + urllib.parse.urlencode(params)
        body = self.fetcher.fetch(url, mode="automatic", purpose=purpose,
                                  accept="application/json, text/plain;q=0.9")
        try:
            return json.loads(body.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, AttributeError) as exc:
            raise SourceError("国家统计局返回了无法解析的内容：{}".format(exc))

    def _walk_tree(self, tree: Any) -> List[Dict[str, Any]]:
        nodes: List[Dict[str, Any]] = []

        def visit(items: Any) -> None:
            for item in items or []:
                if not isinstance(item, dict):
                    continue
                nodes.append(item)
                visit(item.get("nodes") or item.get("children") or [])

        visit(tree)
        return nodes

    def get_tree(self, dbcode: str, wdcode: str) -> List[Dict[str, Any]]:
        payload = self._fetch_json({
            "m": "GetTree", "dbcode": dbcode, "wdcode": wdcode, "id": wdcode,
        }, "nbs_tree")
        if not isinstance(payload, list):
            raise SourceError("国家统计局指标树结构异常")
        return self._walk_tree(payload)

    def find_codes(self, dbcode: str, matches: List[Dict[str, Any]],
                   force: bool = False) -> Dict[str, str]:
        """按名称关键词在指标树中定位代码，结果缓存到 settings（跨月复用）。"""
        cache_key = json.dumps([dbcode, matches], ensure_ascii=False, sort_keys=True)
        cached: Optional[str] = None
        if not force:
            cached = self.db.get_setting("nbs_codes")
        if cached:
            store = json.loads(cached)
            if cache_key in store:
                return store[cache_key]
        nodes = self.get_tree(dbcode, "zb")
        found: Dict[str, str] = {}
        for spec in matches:
            include = spec.get("include") or []
            exclude = spec.get("exclude") or []
            for node in nodes:
                name = str(node.get("name", ""))
                if node.get("isParent") or "nodes" in node or "children" in node:
                    continue
                if not all(key in name for key in include):
                    continue
                if any(key in name for key in exclude):
                    continue
                found[str(spec["kind"])] = str(node["id"])
                break
        missing = [m["kind"] for m in matches if m["kind"] not in found]
        if missing:
            raise SourceError("国家统计局指标树中未找到：{}".format(missing))
        cached_store = json.loads(cached) if cached else {}
        cached_store[cache_key] = found
        self.db.set_setting("nbs_codes", json.dumps(cached_store, ensure_ascii=False))
        return found

    # ---------- 月度数据（hgyd） ----------

    def query_series(self, dbcode: str, codes: List[str],
                     limit: Optional[int] = None) -> Dict[str, List[Tuple[str, float]]]:
        dfwds = [{"wdcode": "zb", "valuecode": ",".join(codes)},
                 {"wdcode": "sj", "valuecode": "LAST{}".format(limit or self.query_months)}]
        payload = self._fetch_json({
            "m": "QueryData", "dbcode": dbcode, "rowcode": "zb", "colcode": "sj",
            "wds": "[]", "dfwds": json.dumps(dfwds),
        }, "nbs_query")
        result: Dict[str, List[Tuple[str, float]]] = {}
        for node in ((payload.get("returndata") or {}).get("datanodes") or []):
            data = node.get("data") or {}
            if not data.get("hasdata"):
                continue
            value = data.get("data")
            if value is None or value == "":
                continue
            wds = {str(w.get("wdcode")): str(w.get("valuecode")) for w in (node.get("wds") or [])}
            code, period = wds.get("zb"), _parse_period(wds.get("sj", ""))
            if code is None:
                continue
            try:
                result.setdefault(code, []).append((period, float(value)))
            except (TypeError, ValueError):
                continue
        for values in result.values():
            values.sort()
        return result

    # ---------- 城市月度数据（csyd，70 城房价） ----------

    def city_names(self, dbcode: str) -> Dict[str, str]:
        nodes = self.get_tree(dbcode, "reg")
        return {str(n["id"]): str(n.get("name", "")) for n in nodes if n.get("id")}

    def query_city_series(self, dbcode: str, zb_code: str,
                          limit: Optional[int] = None) -> Dict[Tuple[str, str], float]:
        wds = [{"wdcode": "zb", "valuecode": zb_code}]
        dfwds = [{"wdcode": "sj", "valuecode": "LAST{}".format(limit or self.query_months)}]
        payload = self._fetch_json({
            "m": "QueryData", "dbcode": dbcode, "rowcode": "reg", "colcode": "sj",
            "wds": json.dumps(wds), "dfwds": json.dumps(dfwds),
        }, "nbs_query")
        result: Dict[Tuple[str, str], float] = {}
        for node in ((payload.get("returndata") or {}).get("datanodes") or []):
            data = node.get("data") or {}
            if not data.get("hasdata"):
                continue
            value = data.get("data")
            if value is None or value == "":
                continue
            wds = {str(w.get("wdcode")): str(w.get("valuecode")) for w in (node.get("wds") or [])}
            if wds.get("zb") != zb_code:
                continue
            city_code, period = wds.get("reg"), _parse_period(wds.get("sj", ""))
            if city_code is None:
                continue
            try:
                result[(city_code, period)] = float(value)
            except (TypeError, ValueError):
                continue
        return result

    # ---------- 指标抓取 ----------

    def fetch_indicator(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        dbcode = str(spec["dbcode"])
        codes = self.find_codes(dbcode, spec["matches"])
        series = self.query_series(dbcode, sorted(set(codes.values())))
        code_to_kind = {code: kind for kind, code in codes.items()}
        rows: List[Dict[str, Any]] = []
        for code, points in series.items():
            kind = code_to_kind[code]
            match = next((m for m in spec["matches"] if m["kind"] == kind), {})
            for period, value in points:
                if match.get("transform") == "minus100":
                    value = value - 100
                rows.append({"period": period, "kind": kind, "city": "",
                             "value": round(value, 4), "unit": ""})
        if not rows:
            raise SourceError("国家统计局月度库没有返回数据")
        return {"rows": rows, "source_label": NBS_SOURCE_LABEL}

    def fetch_city_indicator(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """70 城新建商品住宅价格指数（csyd）：城市 × 环比/同比指数。"""
        dbcode = str(spec.get("dbcode", "csyd"))
        city_by_code = self.city_names(dbcode)
        all_series: Dict[Tuple[str, str, str], float] = {}
        for kind, include in (("city_mom", ["新建商品住宅", "上月=100"]),
                              ("city_yoy", ["新建商品住宅", "上年同月=100"])):
            codes = self.find_codes(dbcode, [{"kind": "x", "include": include}])
            zb_code = codes["x"]
            for (city_code, period), value in self.query_city_series(dbcode, zb_code).items():
                city = str(city_by_code.get(city_code, "")).strip()
                if city:
                    all_series[(city, period, kind)] = value
        rows: List[Dict[str, Any]] = []
        for (city, period, kind), value in sorted(all_series.items()):
            rows.append({"period": period, "kind": kind, "city": city,
                         "value": round(value, 4), "unit": ""})
        if not rows:
            raise SourceError("国家统计局城市月度库没有返回数据")
        return {"rows": rows, "source_label": "国家统计局·城市月度数据库（csyd）"}
