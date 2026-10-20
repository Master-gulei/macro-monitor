from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import indicators
from .ai import BudgetExceeded, LLMAuthError, LLMClient, LLMUnavailable
from .db import Database
from .fetch import SafeFetcher
from .report import build_report as build_report_html
from .sources.customs import CustomsSource
from .sources.eastmoney import EastmoneySource
from .sources.mohrss import MohrssSource
from .sources.nbs import NBSSource
from .sources.statsweb import StatsWebSource


class PipelineError(RuntimeError):
    pass


# 注册表 source type -> (源实例键, 抓取方法名)
_SOURCE_DISPATCH: Dict[str, Tuple[str, str]] = {
    "nbs": ("nbs", "fetch_indicator"),
    "nbs_csyd": ("nbs", "fetch_city_indicator"),
    "eastmoney": ("eastmoney", "fetch_indicator"),
    "statsweb_house": ("statsweb", "fetch_house"),
    "statsweb_profit": ("statsweb", "fetch_profit"),
    "statsweb_news": ("statsweb", "fetch_news_detail"),
    "statsweb_unemp": ("statsweb", "fetch_unemp"),
    "statsweb_pmi_detail": ("statsweb", "fetch_pmi_detail"),
    "customs_trade": ("customs", "fetch_trade"),
    "customs_index": ("customs", "fetch_trade_index"),
    "mohrss_release": ("mohrss", "fetch_new_jobs"),
}

# 70 城分面积段聚合 kinds（新建/二手 × 90㎡以下/90-144㎡/144㎡以上 × 环比/同比）
_HOUSE_AREA_KINDS = (
    "new_a90_mom", "new_a90_yoy", "new_a90144_mom", "new_a90144_yoy",
    "new_a144_mom", "new_a144_yoy",
    "sec_a90_mom", "sec_a90_yoy", "sec_a90144_mom", "sec_a90144_yoy",
    "sec_a144_mom", "sec_a144_yoy")


def build_sources(db: Database, config: Dict[str, Any], fetcher: SafeFetcher) -> Dict[str, Any]:
    return {
        "nbs": NBSSource(fetcher, db, config),
        "eastmoney": EastmoneySource(fetcher, config),
        "statsweb": StatsWebSource(fetcher, config),
        "customs": CustomsSource(fetcher, config),
        "mohrss": MohrssSource(fetcher, config),
    }


class MonthlyPipeline:
    """月度流水线：抓取（指标级容错）→ 房价聚合 → AI 解读（7 板块 + 综合）→ HTML 看板。

    每步幂等可重入：抓取按自然月去重，解读按自然月去重，已入库的观测按
    (indicator_id, period, kind, city) 覆盖更新。
    """

    # S2：同一类非确定性失败（响应解析失败等）连续达到该次数后熔断，
    # 跳过剩余板块，避免坏响应把整月预算烧完
    _MAX_CONSECUTIVE_LLM_FAILURES = 3

    def __init__(self, project: Path, db: Database, config: Dict[str, Any],
                 fetcher: SafeFetcher, llm: LLMClient,
                 sources: Optional[Dict[str, Any]] = None):
        self.project = project
        self.db = db
        self.config = config
        self.fetcher = fetcher
        self.llm = llm
        self.sources = sources or build_sources(db, config, fetcher)

    # ---------- 步骤 1：抓取 ----------

    def _save_payload(self, indicator_id: str, spec: Dict[str, Any],
                      payload: Dict[str, Any], result_period: str,
                      source_label: str) -> Tuple[int, int, int]:
        """把 payload 里的观测行批量写入数据库，返回 (saved, inserted, updated)。

        写入前逐行做数据合理性校验（S1）：越界值照常入库，但记录告警供
        status/看板展示——避免历史上 CPI 环比错误静默入库 12 个月的情况。
        """
        rows: List[Dict[str, Any]] = []
        for row in payload.get("rows") or []:
            period = str(row.get("period") or result_period)
            if len(period) != 7 or period[4] != "-":
                continue
            try:
                value = float(row["value"])
            except (KeyError, TypeError, ValueError):
                continue
            kind = str(row["kind"])
            city = str(row.get("city") or "")
            unit = (row.get("unit") or indicators.KIND_UNIT.get(kind, "")
                    or spec.get("unit", ""))
            rows.append({"indicator_id": indicator_id, "period": period,
                         "kind": kind, "city": city, "value": value,
                         "unit": unit, "source": source_label})
            message = indicators.sanity_check(indicator_id, kind, value)
            if message:
                self.db.record_warning(indicator_id, period, kind, value,
                                       message, city=city)
        inserted, updated = self.db.upsert_observations(rows)
        return len(rows), inserted, updated

    def fetch_data(self, force: bool = False) -> Dict[str, Any]:
        month_key = Database.current_month_key()
        if not force and self.db.get_setting("last_fetch_month") == month_key:
            return {"status": "skipped", "reason": "本月已经抓取过；可用 --force 重新抓取"}
        run_id = self.db.begin_sync()
        results: Dict[str, Any] = {}
        fetched = inserted = updated = 0
        for spec in indicators.INDICATORS:
            indicator_id = spec["id"]
            errors: List[str] = []
            payload: Optional[Dict[str, Any]] = None
            for source_spec in spec["sources"]:
                key, method = _SOURCE_DISPATCH[source_spec["type"]]
                try:
                    payload = getattr(self.sources[key], method)(source_spec)
                    break
                except Exception as exc:  # 指标级容错：单源失败切换下一兜底源
                    errors.append("[{}] {}: {}".format(
                        source_spec["type"], type(exc).__name__, str(exc)[:160]))
                    payload = None
            if not payload:
                results[indicator_id] = {"status": "failed", "errors": errors}
                continue
            result_period = str(payload.get("period") or "")
            source_label = str(payload.get("source_label") or "")
            saved, ins, upd = self._save_payload(
                indicator_id, spec, payload, result_period, source_label)
            inserted += ins
            updated += upd
            if not saved:
                results[indicator_id] = {"status": "failed",
                                         "errors": ["源返回了空数据"]}
                continue
            fetched += 1
            results[indicator_id] = {"status": "ok", "source": source_label,
                                     "rows": saved}
            # 分类细项：主指标成功后补充抓取；失败不影响主指标状态
            detail_errors: List[str] = []
            for detail_spec in spec.get("detail_sources") or []:
                key, method = _SOURCE_DISPATCH[detail_spec["type"]]
                try:
                    detail_payload = getattr(self.sources[key], method)(detail_spec)
                except Exception as exc:
                    detail_errors.append("[{}] {}: {}".format(
                        detail_spec["type"], type(exc).__name__, str(exc)[:160]))
                    continue
                detail_period = str(detail_payload.get("period") or result_period)
                _, ins, upd = self._save_payload(
                    indicator_id, spec, detail_payload, detail_period,
                    str(detail_payload.get("source_label") or source_label))
                inserted += ins
                updated += upd
            if detail_errors:
                results[indicator_id]["detail_errors"] = detail_errors
        inserted += self.aggregate_house()  # 幂等重算：覆盖更新不计入，新插入才计入
        # 验收标准：11 个指标至少 9 个拿到数据即视为 success
        if fetched == 0:
            status, error = "failed", "所有指标均获取失败"
        elif fetched >= len(indicators.INDICATORS) - 2:
            status, error = "success", ""
        else:
            status, error = "partial", ""
        self.db.finish_sync(run_id, status, fetched, inserted, error)
        # 仅在实际拿到数据时写月度标记：全失败（fetched==0）不写，
        # 否则下次运行会被静默跳过，掩盖整月无数据的事实。
        if fetched > 0:
            self.db.set_setting("last_fetch_month", month_key)
        return {"status": status, "fetched": fetched, "inserted": inserted,
                "updated": updated, "indicators": results,
                "data_warnings": self.db.warning_count()}

    # ---------- 步骤 2：70 城房价聚合 ----------

    def aggregate_house(self) -> int:
        """把 70 城明细按数据期预聚合为上涨城市数与各线城市均值，供 AI 与看板直接使用。

        对库内所有存在明细的数据期逐期聚合（幂等覆盖），补齐历史趋势。
        返回本次新插入的聚合观测数（幂等：已存在的行是覆盖更新，不计入）。
        """
        inserted = 0
        rows = self.db.series("house_70", city=None)
        periods = sorted({str(row["period"]) for row in rows if row["city"]})
        if not periods:
            return inserted
        for period in periods:
            by_city: Dict[str, Dict[str, float]] = {}
            for row in rows:
                if row["period"] != period or not row["city"]:
                    continue
                if row["kind"] not in ("city_mom", "city_yoy",
                                       "city_mom_2nd", "city_yoy_2nd"):
                    continue
                by_city.setdefault(str(row["city"]), {})[str(row["kind"])] = float(row["value"])
            if not by_city:
                continue
            for kind, key in (("rise_count_mom", "city_mom"),
                              ("rise_count_yoy", "city_yoy")):
                count = sum(1 for values in by_city.values()
                            if values.get(key) is not None and values[key] > 100)
                event = self.db.upsert_observation(
                    "house_70", period, kind, float(count), "聚合计算",
                    unit=indicators.KIND_UNIT[kind])
                inserted += int(event == "inserted")
            for tier_key in ("tier1", "tier2", "tier3"):
                tier_cities = set(indicators.CITY_TIERS[{"tier1": "一线",
                                                         "tier2": "二线",
                                                         "tier3": "三线"}[tier_key]])
                for base, city_kind in (("mom", "city_mom"), ("yoy", "city_yoy")):
                    values = [by_city[city][city_kind] for city in by_city
                              if city in tier_cities and by_city[city].get(city_kind) is not None]
                    if not values:
                        continue
                    kind = "{}_{}".format(tier_key, base)
                    event = self.db.upsert_observation(
                        "house_70", period, kind, round(sum(values) / len(values), 2),
                        "聚合计算", unit=indicators.KIND_UNIT[kind])
                    inserted += int(event == "inserted")
        return inserted

    # ---------- 步骤 3：AI 解读素材 ----------

    def _sector_material(self, sector: Dict[str, str]) -> str:
        sector_id = sector["id"]
        lines: List[str] = []
        has_data = False
        unemp_kinds: set = set()
        for spec in indicators.sector_indicators(sector_id):
            if spec["id"] == "house_70":
                agg = self.db.latest_by_kinds("house_70")
                parts: List[str] = []
                for kind in indicators.HOUSE_AGG_KINDS:
                    row = agg.get(kind)
                    if row:
                        parts.append("{} {}{}".format(
                            indicators.KIND_META.get(kind, kind),
                            row["value"], row.get("unit") or ""))
                area_parts: List[str] = []
                for kind in _HOUSE_AREA_KINDS:
                    row = agg.get(kind)
                    if row:
                        area_parts.append("{} {}{}".format(
                            indicators.KIND_META.get(kind, kind),
                            row["value"], row.get("unit") or ""))
                if area_parts:
                    parts.append("分面积段全国均值：" + "；".join(area_parts))
                if parts:
                    has_data = True
                    ref = agg.get("rise_count_mom") or {}
                    lines.append("70城房价（数据期 {}，来源 {}）：{}".format(
                        ref.get("period", "?"), ref.get("source", ""), "；".join(parts)))
                continue
            latest = self.db.latest_by_kinds(spec["id"])
            if not latest:
                # 指标缺失（源不可达/未发布）时，把指标自带的说明写进素材，做到“没有的归没有，注明就行”
                if spec.get("missing_note"):
                    lines.append("注：{}本期未获取——{}".format(
                        spec["name"], spec["missing_note"]))
                continue
            has_data = True
            if spec["id"] == "unemp_rate":
                unemp_kinds = set(latest)
            for kind in sorted(latest):
                row = latest[kind]
                if kind.startswith(indicators.DETAIL_KIND_PREFIXES):
                    # 分类细项：只给最新值与上期值，控制素材长度
                    # db.series 按 period ASC 取最后 limit 个，即 [上期, 最新]
                    series = [point["value"]
                              for point in self.db.series(spec["id"], kind=kind, limit=2)]
                    prev = "，上期 {}".format(series[0]) if len(series) > 1 else ""
                    lines.append("{}·{}（数据期 {}）：{}{}{}".format(
                        spec["name"], indicators.KIND_META.get(kind, kind),
                        row["period"], row["value"], row.get("unit") or "", prev))
                else:
                    series = [point["value"]
                              for point in self.db.series(spec["id"], kind=kind, limit=12)]
                    lines.append("{}·{}（数据期 {}，来源 {}）：最新 {}{}；近12个月：{}".format(
                        spec["name"], indicators.KIND_META.get(kind, kind),
                        row["period"], row["source"], row["value"], row.get("unit") or "",
                        ",".join(str(value) for value in series)))
        if has_data:
            # 缺失注明：范围全量纳入，官方源不可达/未发布时明确注明
            if sector_id == "employment" and unemp_kinds and not (
                    unemp_kinds & {"lab_1624", "lab_2529", "lab_3059"}):
                lines.append(
                    "注：分年龄组城镇调查失业率（16—24/25—29/30—59岁，不含在校生）"
                    "仅在国家统计局数据发布库发布，当前网络环境无法访问，本期未获取。")
            if sector_id == "trade":
                lines.append(
                    "注：分贸易方式（一般贸易/加工贸易）进出口细分数据海关官网"
                    "在当前网络环境不可达，本期未获取。")
        return "\n".join(lines) if has_data else ""

    # ---------- 步骤 4：AI 解读 ----------

    def interpret(self, force: bool = False, no_ai: bool = False) -> Dict[str, Any]:
        if no_ai:
            return {"status": "skipped", "reason": "已指定 --no-ai"}
        month_key = Database.current_month_key()
        if not force and self.db.get_setting("last_interpret_month") == month_key:
            return {"status": "skipped", "reason": "本月已解读；可用 --refresh-ai 重新解读"}
        results: Dict[str, Any] = {}
        headlines: List[str] = []
        stop = False
        stop_reason = ""
        consecutive_failures = 0
        for sector in indicators.SECTORS:
            sector_id = sector["id"]
            if stop:
                results[sector_id] = {"status": "failed",
                                      "error": stop_reason or "预算或密钥异常，跳过"}
                continue
            material = self._sector_material(sector)
            if not material.strip():
                results[sector_id] = {"status": "no_data"}
                continue
            try:
                content = self.llm.interpret_sector(sector["name"], material)
                self.db.set_interpretation(
                    sector_id, "latest", content, content.get("model", ""))
                results[sector_id] = {"status": "ok", "model": content.get("model", "")}
                headlines.append("【{}】{}".format(sector["name"],
                                                   content.get("headline", "")))
                consecutive_failures = 0
            except (LLMUnavailable, BudgetExceeded, LLMAuthError) as exc:
                results[sector_id] = {"status": "failed", "error": str(exc)}
                stop = True
                stop_reason = "预算或密钥异常，跳过"
            except Exception as exc:
                consecutive_failures += 1
                results[sector_id] = {"status": "failed",
                                      "error": "{}: {}".format(type(exc).__name__, exc)}
                if consecutive_failures >= self._MAX_CONSECUTIVE_LLM_FAILURES:
                    stop = True
                    stop_reason = "LLM 连续失败 {} 次，熔断跳过剩余板块".format(
                        self._MAX_CONSECUTIVE_LLM_FAILURES)
        overall: Dict[str, Any] = {"status": "skipped"}
        if not stop and len(headlines) >= 2:
            try:
                content = self.llm.interpret_overall("\n".join(headlines))
                self.db.set_interpretation(
                    "overall", "latest", content, content.get("model", ""))
                overall = {"status": "ok", "model": content.get("model", "")}
            except (LLMUnavailable, BudgetExceeded, LLMAuthError) as exc:
                overall = {"status": "failed", "error": str(exc)}
            except Exception as exc:
                overall = {"status": "failed",
                           "error": "{}: {}".format(type(exc).__name__, exc)}
        # 仅在有板块成功解读时写月度标记：全部失败（如缺 key/坏 key/无数据）不写，
        # 否则修好配置后的下一次运行会被静默跳过。
        ok_count = sum(1 for value in results.values() if value.get("status") == "ok")
        if ok_count > 0:
            self.db.set_setting("last_interpret_month", month_key)
        if ok_count == 0:
            status = "failed"
        elif ok_count == len(indicators.SECTORS) and overall.get("status") == "ok":
            status = "success"
        else:
            status = "partial"
        return {"status": status, "sectors": results, "overall": overall}

    # ---------- 步骤 5：看板 ----------

    def build_report(self, today: Optional[Any] = None) -> Dict[str, Any]:
        self.aggregate_house()  # 幂等：仅依据库内明细重算聚合
        result = build_report_html(self.db, self.config, self.project / "out", today=today)
        self._prune_reports()
        return result

    def _prune_reports(self) -> None:
        """F2：out/ 目录只保留最近 keep_reports 份看板（按文件修改时间）。"""
        try:
            keep = int((self.config.get("site") or {}).get("keep_reports", 6))
            reports = sorted(
                (self.project / "out").glob("宏观监测-*.html"),
                key=lambda path: path.stat().st_mtime, reverse=True)
            for old in reports[keep:]:
                try:
                    old.unlink()
                except OSError:
                    continue
        except OSError:
            pass

    def _backup_db(self) -> None:
        """S5：抓取到新数据后备份库文件（SQLite 在线备份 API，WAL 安全）。"""
        try:
            self.db.backup(self.db.path.with_suffix(".db.bak"))
        except Exception as exc:
            self.db.record_warning("_system", "", "backup", 0.0,
                                   "数据库备份失败: {}".format(exc))

    # ---------- 完整运行 ----------

    def run(self, force: bool = False, no_ai: bool = False,
            refresh_ai: bool = False) -> Dict[str, Any]:
        fetch = self.fetch_data(force=force)
        if fetch.get("fetched", 0) > 0:
            self._backup_db()
        interpret = self.interpret(force=refresh_ai, no_ai=no_ai)
        # S3：看板生成失败单独隔离，不影响已完成的抓取/解读结果
        try:
            report = self.build_report()
        except Exception as exc:
            report = {"status": "failed",
                      "error": "{}: {}".format(type(exc).__name__, exc)}
        ok = report.get("status") == "success" and fetch.get("status") != "failed"
        return {"status": "success" if ok else "partial",
                "fetch": fetch, "interpret": interpret, "report": report}
