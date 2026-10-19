from __future__ import annotations

import contextlib
import os
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .db import Database

if os.name == "nt":  # Windows
    import msvcrt

    def _acquire(handle: Any) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)

    def _release(handle: Any) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
else:  # POSIX
    import fcntl

    def _acquire(handle: Any) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)

    def _release(handle: Any) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def file_lock(path: Path):
    """跨进程文件锁：Windows 用 msvcrt.locking，POSIX 用 fcntl.flock。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write("\n")
            handle.flush()
        _acquire(handle)
        try:
            yield
        finally:
            _release(handle)


class RequestBudgetExceeded(RuntimeError):
    pass


class FetchFailed(RuntimeError):
    pass


# 单个响应体上限：防止异常上游返回超大响应耗尽内存。
MAX_BODY_BYTES = 20 * 1024 * 1024


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """不跟随重定向：域名白名单只校验初始 URL，跟随重定向会绕过校验。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _default_openers():
    """与 urlopen 同签名（request, timeout）的可调用 opener 对：
    一个正常校验证书，一个不校验（仅用于本机代理劫持 TLS 的官方站点）。
    """
    verified = urllib.request.build_opener(_NoRedirectHandler())
    insecure = urllib.request.build_opener(
        _NoRedirectHandler(), urllib.request.HTTPSHandler(context=ssl._create_unverified_context())
    )

    def open_verified(request, timeout=None):
        return verified.open(request, timeout=timeout)

    def open_insecure(request, timeout=None):
        return insecure.open(request, timeout=timeout)

    return open_verified, open_insecure


# purpose -> 期望的内容类型（异常类型会触发 FetchFailed，由上层切换兜底源）
_JSON_PURPOSES = ("nbs_tree", "nbs_query", "eastmoney_query")
_HTML_PURPOSES = ("stats_page", "customs_page")


class SafeFetcher:
    """白名单、月度请求预算、间隔、跨进程锁与审计。

    各数据源相互独立：单个请求失败只抛 FetchFailed，由流水线切换到下一兜底源，
    不做全局熔断，避免一个源的风控拖垮其他源。
    """

    def __init__(self, db: Database, config: Dict[str, Any], lock_path: Path,
                 openers: Optional[Any] = None, sleeper: Any = time.sleep):
        self.db = db
        self.config = config
        self.lock_path = lock_path
        verified, insecure = openers or _default_openers()
        self._openers = (verified, insecure)
        self.sleeper = sleeper
        safety = config.get("safety") or {}
        self.tls_exceptions = set(safety.get("tls_verify_exceptions") or [])

    @property
    def opener(self) -> Any:
        # 默认 opener（校验证书）：测试断言 callable 时使用
        return self._openers[0]

    def fetch(self, url: str, *, mode: str = "automatic", purpose: str,
              accept: str, optional_404: bool = False) -> Optional[bytes]:
        if mode not in ("automatic", "user"):
            raise ValueError("mode 必须是 automatic 或 user")
        parsed = urlparse(url)
        safety = self.config["safety"]
        if parsed.scheme != "https" or parsed.hostname not in set(safety["allowed_hosts"]):
            raise ValueError("拒绝访问未授权地址：{}".format(url))
        with file_lock(self.lock_path):
            budget_key = "automatic_requests_per_month" if mode == "automatic" else "user_requests_per_month"
            if self.db.request_count_this_month(mode) >= int(safety.get(budget_key, 100000)):
                raise RequestBudgetExceeded("{} 本月请求预算已用完".format(mode))
            interval = int(safety.get("minimum_request_interval_seconds", 1))
            wait = self.db.last_request_time() + interval - int(time.time())
            if wait > 0:
                self.sleeper(wait)
            request_id = self.db.start_request(mode, purpose, parsed.hostname or "")
            request = urllib.request.Request(url, headers={
                "User-Agent": "macro-monitor/0.1 (personal macro dashboard)",
                "Accept": accept,
            })
            opener = self._openers[1] if parsed.hostname in self.tls_exceptions else self._openers[0]
            try:
                with opener(request, timeout=45) as response:
                    status = int(getattr(response, "status", 200))
                    content_type = response.headers.get("Content-Type", "").lower()
                    body = response.read()
                    if len(body or b"") > MAX_BODY_BYTES:
                        message = "响应体过大（{:,} 字节），已拒绝".format(len(body))
                        self.db.finish_request(request_id, "failed", status, message)
                        raise FetchFailed(message)
                    if purpose in _JSON_PURPOSES and not (
                        "json" in content_type or body.lstrip().startswith(b"{")):
                        reason = "返回了异常内容类型：{}".format(content_type or "unknown")
                        self.db.finish_request(request_id, "failed", status, reason)
                        raise FetchFailed(reason)
                    if purpose in _HTML_PURPOSES and not (
                        "html" in content_type or b"<" in body[:200]):
                        reason = "返回了异常内容类型：{}".format(content_type or "unknown")
                        self.db.finish_request(request_id, "failed", status, reason)
                        raise FetchFailed(reason)
                    self.db.finish_request(request_id, "success", status)
                    return body
            except urllib.error.HTTPError as exc:
                status = int(exc.code)
                if status == 404 and optional_404:
                    self.db.finish_request(request_id, "not_found", status)
                    return None
                if status in (301, 302, 303, 307, 308):
                    message = "拒绝跟随重定向（HTTP {}）：{}".format(status, purpose)
                    self.db.finish_request(request_id, "failed", status, message)
                    raise FetchFailed(message)
                message = "HTTP {}: {}".format(status, purpose)
                self.db.finish_request(request_id, "failed", status, message)
                raise FetchFailed(message)
            except FetchFailed:
                raise
            except Exception as exc:
                message = "{}: {}".format(type(exc).__name__, str(exc))
                self.db.finish_request(request_id, "failed", None, message)
                raise FetchFailed(message)
