from __future__ import annotations


class SourceError(RuntimeError):
    """单个数据源获取失败（由流水线切换到下一兜底源）。"""
    pass
