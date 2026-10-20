from __future__ import annotations

from typing import Optional


class SourceError(RuntimeError):
    """单个数据源获取失败（由流水线切换到下一兜底源）。"""
    pass


class HtmlSource:
    """HTML 数据源基类：统一 _fetch_html 封装（各源共用，C2 去重）。

    子类覆盖 html_purpose 即可让 SafeFetcher 按用途记录抓取日志；
    需要容忍 404 的列表页探测传入 optional_404=True。
    """

    html_purpose = "html_page"

    def _fetch_html(self, url: str, optional_404: bool = False) -> Optional[bytes]:
        return self.fetcher.fetch(url, mode="automatic", purpose=self.html_purpose,
                                  accept="text/html,application/xhtml+xml",
                                  optional_404=optional_404)
