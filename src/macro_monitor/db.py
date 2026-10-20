from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS observations (
  indicator_id TEXT NOT NULL,
  period TEXT NOT NULL,          -- 'YYYY-MM'
  kind TEXT NOT NULL,            -- 'value' | 'yoy' | 'mom' | 'export' | 'city_mom' | ...
  city TEXT NOT NULL DEFAULT '', -- 70 城城市名；聚合与普通指标为空字符串
  value REAL,
  unit TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT '',
  fetched_at INTEGER NOT NULL,
  PRIMARY KEY (indicator_id, period, kind, city)
);
CREATE INDEX IF NOT EXISTS idx_obs_period ON observations(indicator_id, period);

CREATE TABLE IF NOT EXISTS interpretations (
  sector TEXT NOT NULL,          -- 'overall' 或板块 id
  label TEXT NOT NULL DEFAULT '',
  content TEXT NOT NULL,         -- JSON：{headline, points, risks, ...}
  model TEXT NOT NULL DEFAULT '',
  updated_at INTEGER NOT NULL,
  PRIMARY KEY (sector, label)
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS network_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  requested_at INTEGER NOT NULL,
  finished_at INTEGER,
  mode TEXT NOT NULL,
  purpose TEXT NOT NULL,
  host TEXT NOT NULL,
  status_code INTEGER,
  outcome TEXT NOT NULL DEFAULT 'started',
  error TEXT
);
CREATE INDEX IF NOT EXISTS idx_network_requested ON network_requests(requested_at);

CREATE TABLE IF NOT EXISTS provider_usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  account_label TEXT NOT NULL DEFAULT '',
  task_type TEXT NOT NULL,
  units REAL NOT NULL DEFAULT 0,
  success INTEGER NOT NULL,
  error TEXT,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_provider_usage_created ON provider_usage(created_at);

CREATE TABLE IF NOT EXISTS sync_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at INTEGER NOT NULL,
  finished_at INTEGER,
  status TEXT NOT NULL DEFAULT 'running',
  fetched_count INTEGER NOT NULL DEFAULT 0,
  inserted_count INTEGER NOT NULL DEFAULT 0,
  error TEXT
);

CREATE TABLE IF NOT EXISTS data_warnings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  indicator_id TEXT NOT NULL,
  period TEXT NOT NULL,
  kind TEXT NOT NULL,
  city TEXT NOT NULL DEFAULT '',
  value REAL,
  message TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_warnings_created ON data_warnings(created_at);
"""


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(str(self.path), timeout=30, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)
        self.con.execute("PRAGMA busy_timeout=30000")

    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ---------- settings ----------

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: Any) -> None:
        now = int(time.time())
        self.con.execute(
            "INSERT INTO settings(key,value,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
            (key, str(value), now),
        )
        self.con.commit()

    # ---------- 观测值 ----------

    def upsert_observation(self, indicator_id: str, period: str, kind: str,
                           value: float, source: str, city: str = "",
                           unit: str = "") -> str:
        now = int(time.time())
        old = self.con.execute(
            "SELECT 1 FROM observations WHERE indicator_id=? AND period=? AND kind=? AND city=?",
            (indicator_id, period, kind, city or ""),
        ).fetchone()
        if old is None:
            self.con.execute(
                "INSERT INTO observations(indicator_id,period,kind,city,value,unit,source,fetched_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (indicator_id, period, kind, city or "", float(value), unit, source, now),
            )
            event = "inserted"
        else:
            self.con.execute(
                "UPDATE observations SET value=?,unit=?,source=?,fetched_at=? "
                "WHERE indicator_id=? AND period=? AND kind=? AND city=?",
                (float(value), unit, source, now, indicator_id, period, kind, city or ""),
            )
            event = "updated"
        self.con.commit()
        return event

    def upsert_observations(self, rows: List[Dict[str, Any]]) -> Tuple[int, int]:
        """批量写入观测值：单事务一次提交，返回 (inserted, updated)。

        rows 元素字段：indicator_id / period / kind / city / value / unit / source。
        与 upsert_observation 等价，但避免逐行 commit（70 城一次抓取约 280 行）。
        """
        now = int(time.time())
        inserts: List[tuple] = []
        updates: List[tuple] = []
        # 批内去重：同 (indicator, period, kind, city) 保留最后一条，
        # 避免页面重复渲染导致同一批里插入主键冲突
        deduped: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
        for row in rows:
            key = (str(row["indicator_id"]), str(row["period"]), str(row["kind"]),
                   str(row.get("city") or ""))
            deduped[key] = row
        for row in deduped.values():
            indicator_id = str(row["indicator_id"])
            period = str(row["period"])
            kind = str(row["kind"])
            city = str(row.get("city") or "")
            value = float(row["value"])
            unit = str(row.get("unit") or "")
            source = str(row.get("source") or "")
            exists = self.con.execute(
                "SELECT 1 FROM observations WHERE indicator_id=? AND period=? "
                "AND kind=? AND city=?",
                (indicator_id, period, kind, city),
            ).fetchone()
            if exists is None:
                inserts.append((indicator_id, period, kind, city, value,
                                unit, source, now))
            else:
                updates.append((value, unit, source, now, indicator_id,
                                period, kind, city))
        if inserts:
            self.con.executemany(
                "INSERT INTO observations(indicator_id,period,kind,city,value,unit,"
                "source,fetched_at) VALUES(?,?,?,?,?,?,?,?)", inserts)
        if updates:
            self.con.executemany(
                "UPDATE observations SET value=?,unit=?,source=?,fetched_at=? "
                "WHERE indicator_id=? AND period=? AND kind=? AND city=?", updates)
        self.con.commit()
        return len(inserts), len(updates)

    def series(self, indicator_id: str, kind: Optional[str] = None,
               city: Optional[str] = "", limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """观测序列；city 为 None 表示不过滤城市（取全部城市行）。"""
        sql = ("SELECT * FROM observations WHERE indicator_id=?"
               + ("" if city is None else " AND city=?")
               + (" AND kind=?" if kind else "")
               + " ORDER BY period ASC")
        params: List[Any] = [indicator_id]
        if city is not None:
            params.append(city or "")
        if kind:
            params.append(kind)
        rows = self.con.execute(sql, params).fetchall()
        result = [dict(row) for row in rows]
        if limit:
            result = result[-limit:]
        return result

    def latest(self, indicator_id: str, kind: str, city: str = "") -> Optional[Dict[str, Any]]:
        row = self.con.execute(
            "SELECT * FROM observations WHERE indicator_id=? AND kind=? AND city=? "
            "ORDER BY period DESC LIMIT 1",
            (indicator_id, kind, city or ""),
        ).fetchone()
        return dict(row) if row else None

    def latest_by_kinds(self, indicator_id: str, city: str = "") -> Dict[str, Dict[str, Any]]:
        """每个 kind 的最新一条观测。"""
        rows = self.con.execute(
            "SELECT * FROM observations WHERE indicator_id=? AND city=? ORDER BY period ASC",
            (indicator_id, city or ""),
        ).fetchall()
        out: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            out[str(row["kind"])] = dict(row)
        return out

    def latest_period(self, indicator_id: str) -> Optional[str]:
        row = self.con.execute(
            "SELECT MAX(period) p FROM observations WHERE indicator_id=?",
            (indicator_id,),
        ).fetchone()
        return row["p"] if row else None

    def observation_count(self) -> int:
        row = self.con.execute("SELECT COUNT(*) n FROM observations").fetchone()
        return int(row["n"])

    def distinct_periods(self) -> int:
        row = self.con.execute("SELECT COUNT(DISTINCT period) n FROM observations").fetchone()
        return int(row["n"])

    # ---------- 月份预算（LLM token） ----------

    @staticmethod
    def current_month_key(now: Optional[datetime] = None) -> str:
        value = now or datetime.now()
        return value.strftime("%Y-%m")

    def budget_month_start(self, now: Optional[datetime] = None) -> int:
        """本月预算起点：进入新的自然月自动前滚，无需手动 reset-budget。"""
        current_key = self.current_month_key(now)
        stored = self.get_setting("budget_month")
        if stored != current_key:
            self.set_setting("budget_month", current_key)
        value = now or datetime.now()
        month_start = datetime(value.year, value.month, 1)
        return int(time.mktime(month_start.timetuple()))

    def reset_budget_month(self) -> str:
        """重置本月 LLM 用量计数：删除本月 provider_usage 记录，历史月份保留。

        用量统计（llm_usage_this_month）按时间戳计算，仅改设置值无法清零，
        必须删除本月记录才能真正重置。
        """
        value = self.current_month_key()
        self.con.execute(
            "DELETE FROM provider_usage WHERE created_at>=?",
            (self.budget_month_start(),),
        )
        self.con.commit()
        self.set_setting("budget_month", value)
        return value

    def llm_usage_this_month(self) -> int:
        row = self.con.execute(
            "SELECT COALESCE(SUM(units),0) n FROM provider_usage WHERE success=1 AND created_at>=?",
            (self.budget_month_start(),),
        ).fetchone()
        return int(row["n"])

    def record_llm_result(self, account_label: str, task_type: str, units: float,
                          success: bool, error: str = "") -> None:
        now = int(time.time())
        self.con.execute(
            "INSERT INTO provider_usage(account_label,task_type,units,success,error,created_at) "
            "VALUES(?,?,?,?,?,?)",
            ((account_label or "")[:80], task_type, float(units), int(success),
             error[:500], now),
        )
        self.con.commit()

    # ---------- 请求审计 ----------

    def request_count_this_month(self, mode: str) -> int:
        row = self.con.execute(
            "SELECT COUNT(*) n FROM network_requests WHERE mode=? AND requested_at>=?",
            (mode, self.budget_month_start()),
        ).fetchone()
        return int(row["n"])

    def last_request_time(self) -> int:
        row = self.con.execute("SELECT COALESCE(MAX(requested_at),0) t FROM network_requests").fetchone()
        return int(row["t"])

    def start_request(self, mode: str, purpose: str, host: str) -> int:
        cur = self.con.execute(
            "INSERT INTO network_requests(requested_at,mode,purpose,host) VALUES(?,?,?,?)",
            (int(time.time()), mode, purpose, host),
        )
        self.con.commit()
        return int(cur.lastrowid)

    def finish_request(self, request_id: int, outcome: str, status_code: Optional[int] = None,
                       error: str = "") -> None:
        self.con.execute(
            "UPDATE network_requests SET finished_at=?,outcome=?,status_code=?,error=? WHERE id=?",
            (int(time.time()), outcome, status_code, error[:500], request_id),
        )
        self.con.commit()

    # ---------- 同步记录 ----------

    def begin_sync(self) -> int:
        cur = self.con.execute("INSERT INTO sync_runs(started_at) VALUES(?)", (int(time.time()),))
        self.con.commit()
        return int(cur.lastrowid)

    def finish_sync(self, run_id: int, status: str, fetched: int = 0,
                    inserted: int = 0, error: str = "") -> None:
        self.con.execute(
            "UPDATE sync_runs SET finished_at=?,status=?,fetched_count=?,inserted_count=?,error=? WHERE id=?",
            (int(time.time()), status, fetched, inserted, error[:500], run_id),
        )
        self.con.commit()

    # ---------- 数据合理性告警 ----------

    def record_warning(self, indicator_id: str, period: str, kind: str,
                       value: float, message: str, city: str = "") -> None:
        """写入一条数据合理性告警；同一事件（指标/数据期/kind/城市/文案/数值）不重复写入。"""
        message = message[:500]
        key = (indicator_id, period, kind, city or "", message, float(value))
        existing = self.con.execute(
            "SELECT 1 FROM data_warnings WHERE indicator_id=? AND period=? AND kind=? "
            "AND city=? AND message=? AND value=? LIMIT 1", key).fetchone()
        if existing:
            return
        self.con.execute(
            "INSERT INTO data_warnings(indicator_id,period,kind,city,value,message,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (indicator_id, period, kind, city or "", float(value),
             message, int(time.time())),
        )
        self.con.commit()

    def warning_count(self) -> int:
        row = self.con.execute("SELECT COUNT(*) n FROM data_warnings").fetchone()
        return int(row["n"])

    def recent_warnings(self, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.con.execute(
            "SELECT * FROM data_warnings ORDER BY id DESC LIMIT ?", (int(limit),),
        ).fetchall()
        return [dict(row) for row in rows]

    # ---------- 备份 ----------

    def backup(self, target: Path) -> Path:
        """用 SQLite 在线备份 API 快照到 target（WAL 模式下同样安全）。"""
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        backup_con = sqlite3.connect(str(target))
        try:
            self.con.backup(backup_con)
        finally:
            # with 块只提交/回滚事务，不关闭连接；Windows 上必须显式关闭才能释放文件锁
            backup_con.close()
        return target

    # ---------- 审计清理 ----------

    def prune_audit(self, retention_days: int = 90) -> Dict[str, int]:
        """清理超过保留期的审计/告警/用量/同步记录（默认 90 天），防止无限增长。

        只清理审计与告警类记录，观察数据与 AI 解读不动。
        """
        days = max(1, int(retention_days))
        cutoff = int(time.time()) - days * 86400
        pruned: Dict[str, int] = {}
        for table, column in (("network_requests", "requested_at"),
                              ("provider_usage", "created_at"),
                              ("sync_runs", "started_at"),
                              ("data_warnings", "created_at")):
            cur = self.con.execute(
                "DELETE FROM {} WHERE {}<?".format(table, column), (cutoff,))
            pruned[table] = cur.rowcount
        self.con.commit()
        return pruned

    # ---------- AI 解读 ----------

    def set_interpretation(self, sector: str, label: str, content: Dict[str, Any],
                           model: str) -> None:
        now = int(time.time())
        self.con.execute(
            "INSERT INTO interpretations(sector,label,content,model,updated_at) "
            "VALUES(?,?,?,?,?) ON CONFLICT(sector,label) DO UPDATE SET "
            "content=excluded.content,model=excluded.model,updated_at=excluded.updated_at",
            (sector, label or "", json.dumps(content, ensure_ascii=False), model, now),
        )
        self.con.commit()

    def interpretations(self) -> Dict[str, Dict[str, Any]]:
        rows = self.con.execute("SELECT * FROM interpretations").fetchall()
        out: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            key = row["sector"] if not row["label"] else "{}/{}".format(row["sector"], row["label"])
            try:
                out[key] = json.loads(row["content"])
            except json.JSONDecodeError:
                out[key] = {"headline": "（解读内容损坏）", "points": [], "risks": []}
        return out

    # ---------- 状态 ----------

    def indicator_freshness(self, now: Optional[datetime] = None) -> Dict[str, Dict[str, Any]]:
        """每个指标最新数据期与距今月数（新数据未入库的指标不会出现）。"""
        value = now or datetime.now()
        current = value.year * 12 + value.month
        rows = self.con.execute(
            "SELECT indicator_id, MAX(period) p FROM observations GROUP BY indicator_id",
        ).fetchall()
        result: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            period = str(row["p"])
            try:
                year, month = int(period[:4]), int(period[5:7])
            except ValueError:
                continue
            result[str(row["indicator_id"])] = {
                "latest_period": period,
                "months_behind": current - (year * 12 + month),
            }
        return result

    def status(self) -> Dict[str, Any]:
        used = self.llm_usage_this_month()
        budget = int(self.get_setting("monthly_token_budget", "0") or 0)
        last_sync = self.con.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
        return {
            "observations": self.observation_count(),
            "periods": self.distinct_periods(),
            "llm_tokens_this_month": used,
            "llm_budget": budget,
            "llm_budget_remaining": max(0, budget - used) if budget else None,
            "last_fetch_month": self.get_setting("last_fetch_month", ""),
            "last_sync": dict(last_sync) if last_sync else None,
            "data_warnings": self.warning_count(),
        }
