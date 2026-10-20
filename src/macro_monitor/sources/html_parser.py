"""通用 HTML 解析：链接、表格与纯文本提取（统计局部/海关总署/人社部共用）。"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import List, Optional, Tuple

WHITESPACE = re.compile(r"[\s\u3000\u00a0]+")


class _ContentParser(HTMLParser):
    """提取页面里的链接、表格与纯文本（供新闻稿解析使用）。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: List[Tuple[str, str]] = []   # (href, text)
        self.tables: List[List[List[str]]] = []  # 每个表格: 行 -> 单元格文本
        self.text_parts: List[str] = []
        self._current_link: Optional[Tuple[Optional[str], List[str]]] = None
        self._table: Optional[List[List[str]]] = None
        self._row: Optional[List[str]] = None
        self._cell: Optional[List[str]] = None
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attributes = dict(attrs)
        if tag in ("script", "style"):
            self._skip_depth += 1
            return
        if tag == "a" and attributes.get("href"):
            self._current_link = (attributes.get("href"), [])
        elif tag == "table" and self._table is None:
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "a" and self._current_link is not None:
            href, parts = self._current_link
            text = WHITESPACE.sub("", "".join(parts))
            if text:
                self.links.append((href or "", text))
            self._current_link = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None
        elif tag == "tr" and self._row is not None:
            if self._table is not None:
                self._table.append(self._row)
            self._row = None
        elif tag in ("td", "th") and self._cell is not None:
            if self._row is not None:
                self._row.append(WHITESPACE.sub("", "".join(self._cell)))
            self._cell = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._current_link is not None:
            self._current_link[1].append(data)
        if self._cell is not None:
            self._cell.append(data)
        if self._table is None and self._row is None:
            self.text_parts.append(data)

    def text(self) -> str:
        return WHITESPACE.sub(" ", " ".join(self.text_parts))


def parse_html(body: bytes) -> _ContentParser:
    text = body.decode("utf-8", errors="replace")
    parser = _ContentParser()
    parser.feed(text)
    if parser._skip_depth:
        # HTMLParser 对 script/style 启用 CDATA 模式：只找对应的闭合标签，未闭合时
        # 其后所有内容（含链接与表格标签）都不会再触发任何回调，静默丢失。
        # 此时剔除 script/style 标签后重解析，让后续内容重新可见。
        cleaned = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1\s*>", "", text)
        cleaned = re.sub(r"(?is)<(script|style)\b[^>]*>", "", cleaned)
        parser = _ContentParser()
        parser.feed(cleaned)
    return parser
