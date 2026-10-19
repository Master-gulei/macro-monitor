from __future__ import annotations

import json
import urllib.parse
from typing import Any, Dict, List, Optional

from ..fetch import SafeFetcher
from . import SourceError


class EastmoneySource:
    """东方财富数据中心 JSON 接口（免 key，数据转载自国家统计局/海关总署）。"""

    def __init__(self, fetcher: SafeFetcher, config: Dict[str, Any]):
        self.fetcher = fetcher
        self.config = config
        self.base = str(config.get("eastmoney", {}).get(
            "base_url", "https://datacenter-web.eastmoney.com")).rstrip("/")
        self.page_size = int(config.get("eastmoney", {}).get("page_size", 120))

    def query_rows(self, report_name: str, columns: str,
                   page_size: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {
            "reportName": report_name,
            "columns": columns,
            "pageNumber": 1,
            "pageSize": page_size or self.page_size,
            "sortColumns": "REPORT_DATE",
            "sortTypes": -1,
            "source": "WEB",
            "client": "WEB",
        }
        url = self.base + "/api/data/v1/get?" + urllib.parse.urlencode(params)
        body = self.fetcher.fetch(url, mode="automatic", purpose="eastmoney_query",
                                  accept="application/json, text/plain;q=0.9")
        try:
            payload = json.loads(body.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, AttributeError) as exc:
            raise SourceError("东方财富返回了无法解析的内容：{}".format(exc))
        if not payload.get("success"):
            message = str(payload.get("message") or "未知错误")[:200]
            raise SourceError("东方财富查询失败（{}）：{}".format(report_name, message))
        rows = ((payload.get("result") or {}).get("data")) or []
        if not isinstance(rows, list):
            raise SourceError("东方财富返回结构异常（{}）".format(report_name))
        return rows

    @staticmethod
    def _normalize_fields(fields: Any) -> List[Dict[str, Any]]:
        """fields 支持两种写法：{kind: 字段名} 简写，或 [{kind, field|add, scale, unit}] 完整形式。"""
        if isinstance(fields, dict):
            return [{"kind": str(kind), "field": str(name)}
                    for kind, name in fields.items()]
        return [dict(field) for field in (fields or [])]

    @staticmethod
    def _field_refs(fields: List[Dict[str, Any]]) -> List[str]:
        refs: List[str] = []
        for field in fields:
            if field.get("field"):
                refs.append(str(field["field"]))
            refs.extend(field.get("add") or [])
        return refs

    def fetch_indicator(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        report_name = str(spec["report_name"])
        fields = self._normalize_fields(spec.get("fields"))
        columns = "REPORT_DATE,TIME," + ",".join(self._field_refs(fields))
        rows = self.query_rows(report_name, columns)
        parsed: List[Dict[str, Any]] = []
        for row in rows:
            date = str(row.get("REPORT_DATE") or "")
            period = date[:7]
            if len(period) != 7 or not period[4] == "-":
                continue
            for field in fields:
                value: Optional[float] = None
                if field.get("field"):
                    value = self._as_float(row.get(field["field"]))
                else:
                    parts = [self._as_float(row.get(name)) for name in (field.get("add") or [])]
                    if all(part is not None for part in parts):
                        value = sum(parts)
                if value is None:
                    continue
                if field.get("scale"):
                    value = value * float(field["scale"])
                if field.get("transform") == "minus100":
                    value = value - 100  # 上月=100 指数 → 环比涨幅（%）
                parsed.append({
                    "period": period,
                    "kind": str(field["kind"]),
                    "city": "",
                    "value": round(value, 4),
                    "unit": str(field.get("unit") or ""),
                })
        if not parsed:
            raise SourceError("东方财富（{}）没有返回数据".format(report_name))
        return {"rows": parsed,
                "source_label": "东方财富数据中心（{}）".format(report_name)}

    @staticmethod
    def _as_float(value: Any) -> Optional[float]:
        if value is None or value == "" or value == "-":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
