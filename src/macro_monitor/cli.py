from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

from . import indicators
from .ai import LLMClient
from .config import ConfigError, load_config, project_paths
from .db import Database
from .fetch import SafeFetcher
from .pipeline import MonthlyPipeline


def load_core(project: Path) -> Tuple[Dict[str, Any], Dict[str, Path], Database]:
    """加载配置与数据库（不构造网络与 LLM 客户端），dry-run 与 build 共用。"""
    config = load_config(project)
    paths = project_paths(project)
    db = Database(paths["database"])
    # 每次启动把 config 里的月预算同步到 settings，供 status 展示与审计
    db.set_setting("monthly_token_budget", config["llm"]["monthly_token_budget"])
    return config, paths, db


def build(project: Path) -> Tuple[Dict[str, Any], Dict[str, Path], Database, MonthlyPipeline]:
    config, paths, db = load_core(project)
    fetcher = SafeFetcher(db, config, paths["data"] / "network.lock")
    llm = LLMClient(db, config)
    pipeline = MonthlyPipeline(project, db, config, fetcher, llm)
    return config, paths, db, pipeline


def output(value: Any) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台默认 GBK，避免中文 JSON 乱码
    except (AttributeError, OSError):
        pass
    print(json.dumps(value, ensure_ascii=False, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="宏观监测看板：月度宏观指标抓取 + AI 解读 + 单文件 HTML 看板")
    parser.add_argument("--project", type=Path, default=Path.cwd(),
                        help="项目根目录（默认当前目录）")
    commands = parser.add_subparsers(dest="command", required=True)
    run_cmd = commands.add_parser("run", help="完整月度流水线：抓取 → 聚合 → AI 解读 → 看板")
    run_cmd.add_argument("--force", action="store_true",
                         help="忽略本月抓取标记，强制重新抓取")
    run_cmd.add_argument("--no-ai", action="store_true",
                         help="跳过 AI 解读（只抓取数据并生成看板）")
    run_cmd.add_argument("--refresh-ai", action="store_true",
                         help="忽略本月解读标记，强制重新生成 AI 解读")
    run_cmd.add_argument("--dry-run", action="store_true",
                         help="仅校验配置并输出状态，不访问网络与 LLM")
    report_cmd = commands.add_parser("report", help="仅用已有数据重新生成 HTML 看板（不抓取）")
    report_cmd.add_argument("--refresh-ai", action="store_true",
                            help="用库内数据重新生成 AI 解读")
    commands.add_parser("status", help="查看数据量、LLM 预算用量与最近同步")
    commands.add_parser("reset-budget", help="手动重置本月 LLM token 预算计数")
    prune_cmd = commands.add_parser("prune", help="清理过期的审计/告警/用量/同步记录（默认保留 90 天）")
    prune_cmd.add_argument("--days", type=int, default=90, help="保留天数（默认 90，最小 1）")
    args = parser.parse_args()

    project = args.project.expanduser().resolve()
    try:
        if args.command == "run" and args.dry_run:
            # 仅校验配置并输出状态，不构造网络与 LLM 客户端（与 build 共用 load_core）
            config, paths, db = load_core(project)
            output({"status": "config_ok",
                    "site": config["site"],
                    "llm": {key: config["llm"][key] for key in
                            ("provider", "base_url", "model", "monthly_token_budget")},
                    **db.status()})
            db.close()
            return
        config, paths, db, pipeline = build(project)
        try:
            if args.command == "run":
                output(pipeline.run(force=args.force, no_ai=args.no_ai,
                                    refresh_ai=args.refresh_ai))
            elif args.command == "report":
                if args.refresh_ai:
                    output({"interpret": pipeline.interpret(force=True),
                            **pipeline.build_report()})
                else:
                    output(pipeline.build_report())
            elif args.command == "status":
                freshness = db.indicator_freshness()
                output({**db.status(), "database": str(paths["database"]),
                        "out_dir": str(paths["out"]),
                        "indicator_freshness": {
                            spec["id"]: {
                                "name": spec["name"],
                                "latest_period": freshness.get(spec["id"], {}).get(
                                    "latest_period", ""),
                                "months_behind": freshness.get(spec["id"], {}).get(
                                    "months_behind"),
                            } for spec in indicators.INDICATORS},
                        "recent_warnings": db.recent_warnings(10)})
            elif args.command == "reset-budget":
                output({"ok": True, "budget_month": db.reset_budget_month(),
                        "llm_tokens_this_month": db.llm_usage_this_month()})
            elif args.command == "prune":
                days = max(1, int(args.days))
                output({"ok": True, "retention_days": days,
                        "pruned": db.prune_audit(days)})
        finally:
            db.close()
    except ConfigError as exc:
        output({"error": "配置错误：{}".format(exc)})
        sys.exit(1)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:
        output({"error": "{}: {}".format(type(exc).__name__, exc)})
        sys.exit(1)


if __name__ == "__main__":
    main()
