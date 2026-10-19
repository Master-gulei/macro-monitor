from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class ConfigError(ValueError):
    pass


def _config_int(data: Dict[str, Any], key: str, default: int, label: str) -> int:
    try:
        return int(data.get(key, default))
    except (TypeError, ValueError):
        raise ConfigError("{} 必须是整数（当前值：{!r}）".format(label, data.get(key)))


def load_config(project: Path) -> Dict[str, Any]:
    path = project / "config.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    # 本机私有配置（local_config.json，已被 gitignore 忽略）：浅合并覆盖，
    # 用于存放 API Key 等敏感值，避免进入版本库或出现在命令行历史里。
    local_path = project / "local_config.json"
    if local_path.exists():
        local = json.loads(local_path.read_text(encoding="utf-8"))
        for key, value in (local or {}).items():
            if isinstance(value, dict) and isinstance(data.get(key), dict):
                data[key] = {**data[key], **value}
            else:
                data[key] = value
    safety = data.get("safety") or {}
    if not safety.get("allowed_hosts"):
        raise ConfigError("必须配置至少一个允许访问的域名")
    if _config_int(safety, "automatic_requests_per_month", 0,
                   "safety.automatic_requests_per_month") < 1:
        raise ConfigError("automatic_requests_per_month 必须至少为 1")
    interval = _config_int(safety, "minimum_request_interval_seconds", 0,
                           "safety.minimum_request_interval_seconds")
    if interval < 1:
        raise ConfigError("minimum_request_interval_seconds 必须至少为 1 秒")
    llm = data.get("llm") or {}
    base_url = str(llm.get("base_url", ""))
    if base_url and not base_url.startswith("https://"):
        raise ConfigError("llm.base_url 必须是 https 地址")
    if _config_int(llm, "monthly_token_budget", 0, "llm.monthly_token_budget") <= 0:
        raise ConfigError("monthly_token_budget 必须大于 0")
    return data


def project_paths(project: Path) -> Dict[str, Path]:
    project = project.resolve()
    paths = {
        "project": project,
        "data": project / "data",
        "cache": project / "data" / "cache",
        "database": project / "data" / "macro.db",
        "out": project / "out",
    }
    for key in ("data", "cache", "out"):
        paths[key].mkdir(parents=True, exist_ok=True)
    return paths
