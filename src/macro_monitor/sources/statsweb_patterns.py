"""统计局官网新闻稿链接标题 pattern 与文本匹配工具（核心类与各指标 mixin 共用）。"""

from __future__ import annotations

import re
from typing import Dict

# 70 城房价 / 工业企业利润 / 失业率运行情况稿链接标题
HOUSE_LINK_PATTERN = re.compile(
    r"(\d{4})年(\d{1,2})月份70个大中城市商品住宅销售价格变动情况")
PROFIT_LINK_PATTERN = re.compile(
    r"(\d{4})年1—(\d{1,2})月份全国规模以上工业企业利润")
# 城镇调查失业率：2026 年起不再单独发布，内嵌在「国民经济运行情况」新闻稿
# （/sj/zxfbhjd/）就业段落；月度稿如「8月份国民经济运行平稳」、
# 季度稿如「前三季度经济运行总体平稳」、年度稿如「2025年国民经济运行总体平稳」
# （12 月数据只在次年 1 月的年度稿中发布，必须单独匹配）
UNEMP_LINK_PATTERN = re.compile(r"(\d{1,2})月份国民经济")
UNEMP_QUARTER_PATTERN = re.compile(r"(一季度|上半年|前三季度)经济")
# 「国民经济运行」限定年度稿本身，避免误中「国民经济和社会发展统计公报」等链接
UNEMP_ANNUAL_PATTERN = re.compile(r"(\d{4})年国民经济运行")

# 链接标题过滤：解读/署名文章与答记者问不含完整数据表，必须跳过
# （如「郑学工：前三季度经济运行总体平稳、向新向优」会排在官方发布稿之前）
_COMMENTARY_MARKERS = ("答记者问", "解读")
_AUTHOR_PREFIX = re.compile(r"^[^\s：:]{2,4}[：:]")


def is_commentary_title(text: str) -> bool:
    """判断链接标题是否为解读/署名/答记者问类文章。"""
    if any(marker in text for marker in _COMMENTARY_MARKERS):
        return True
    return _AUTHOR_PREFIX.match(text) is not None
# 新闻稿分类细项：链接标题 pattern（retail 为累计期标题，如「1—9月份」）
NEWS_LINK_PATTERNS: Dict[str, re.Pattern] = {
    "cpi": re.compile(r"(\d{4})年(\d{1,2})月份居民消费价格"),
    "ppi": re.compile(r"(\d{4})年(\d{1,2})月份工业生产者出厂价格"),
    "indva": re.compile(r"(\d{4})年(\d{1,2})月份规模以上工业增加值增长"),
    "retail": re.compile(r"(\d{4})年1—(\d{1,2})月份社会消费品零售总额增长"),
    "pmi": re.compile(r"(\d{4})年(\d{1,2})月中国采购经理指数运行情况"),
}

_SECTION_NO = re.compile(r"^[一二三四五六七八九十]+、")
_MONTH_CELL = re.compile(r"^(\d{4})年(\d{1,2})月$")


def normalize_row_name(name: str) -> str:
    """行名归一化：去「其中：」前缀与「一、」等序号前缀，便于跨月份匹配。"""
    return _SECTION_NO.sub("", name).removeprefix("其中：")
