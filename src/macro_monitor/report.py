from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import indicators
from .db import Database

# 黑底暗色主题：立体感表格（多层阴影+内高光）、全屏铺满布局、发光信号灯
_STYLE = """
:root{--bg:#07090f;--card:#10141d;--ink:#e6eaf4;--muted:#8b93a7;--line:#1e2534;--line-2:#2a3245;
--accent:#8b7cff;--accent-2:#a78bfa;--accent-soft:rgba(139,124,255,.14);
--gold:#e8b13c;--gold-soft:rgba(232,177,60,.12);
--green:#34d399;--green-soft:rgba(52,211,153,.12);
--red:#f87171;--red-soft:rgba(248,113,113,.12);
--yellow:#e0b84e;--yellow-soft:rgba(224,184,78,.12);
--blue:#58a6ff;--blue-soft:rgba(88,166,255,.12);
--shadow:0 18px 44px rgba(0,0,0,.5)}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:"Segoe UI","PingFang SC","Microsoft YaHei",system-ui,sans-serif;
background:radial-gradient(1200px 800px at 50% -12%,#111626 0%,#07090f 58%) fixed,var(--bg);
color:var(--ink);line-height:1.7;padding-bottom:64px}
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-thumb{background:#232b3d;border-radius:8px}
::-webkit-scrollbar-track{background:#0b0e15}
.wrap{width:100%;padding:0 clamp(20px,3vw,64px)}
header.hero{padding:54px 0 30px;border-bottom:1px solid var(--line);
background:radial-gradient(1100px 500px at 10% -14%,rgba(139,124,255,.18),transparent 60%),
radial-gradient(860px 420px at 96% -8%,rgba(232,177,60,.10),transparent 55%)}
.kicker{font-size:11.5px;letter-spacing:.32em;text-transform:uppercase;color:var(--accent);font-weight:700}
.brand{display:flex;align-items:center;gap:20px}
.logo{flex:0 0 auto;width:64px;height:64px;border-radius:18px;
background:linear-gradient(135deg,var(--accent),var(--accent-2));
display:flex;align-items:center;justify-content:center;
box-shadow:0 10px 30px rgba(139,124,255,.4),inset 0 1px 0 rgba(255,255,255,.25)}
.logo svg{width:38px;height:38px;display:block}
h1{font-size:32px;margin:6px 0 4px;letter-spacing:.01em;color:#f4f6fb;
text-shadow:0 2px 18px rgba(139,124,255,.35)}
.sub{color:var(--muted);font-size:13.5px}
.nav{display:flex;flex-wrap:wrap;gap:8px;margin-top:20px}
.nav a{font-size:12.5px;color:#aab3c8;background:var(--card);border:1px solid var(--line);
border-radius:999px;padding:5px 15px;text-decoration:none;box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}
.nav a:hover{border-color:var(--accent);color:var(--accent)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:28px 0 6px}
.stat{background:linear-gradient(170deg,#141a28,#0f141f);border:1px solid var(--line);border-radius:16px;
padding:16px 20px;box-shadow:0 10px 26px rgba(0,0,0,.4),inset 0 1px 0 rgba(255,255,255,.05)}
.stat b{display:block;font-size:23px;color:var(--accent);font-variant-numeric:tabular-nums}
.stat span{color:var(--muted);font-size:12px}
h2.sec{margin:52px 0 6px;font-size:21px;border-left:4px solid var(--accent);border-radius:2px;
padding-left:14px;display:flex;align-items:center;gap:12px}
.sec-num{font-size:13px;color:var(--accent-2);background:var(--accent-soft);
border:1px solid rgba(139,124,255,.32);border-radius:8px;padding:2px 9px;font-variant-numeric:tabular-nums}
.sec-note{color:var(--muted);font-size:13px;margin:6px 0 18px}
table{width:100%;border-collapse:separate;border-spacing:0;
background:linear-gradient(180deg,#141927,#0e1219);border:1px solid var(--line-2);
border-radius:18px;overflow:hidden;font-size:14px;
box-shadow:0 26px 52px rgba(0,0,0,.55),0 8px 16px rgba(0,0,0,.45),inset 0 1px 0 rgba(255,255,255,.06)}
th{background:linear-gradient(180deg,#1c2333,#151a28);color:#a6b0c6;text-align:left;font-size:12.5px;
padding:13px 16px;border-bottom:1px solid var(--line-2);white-space:nowrap;
text-shadow:0 1px 0 rgba(0,0,0,.5)}
td{padding:11px 16px;border-bottom:1px solid #1a2130;vertical-align:top;color:#d7ddea}
tr:last-child td{border-bottom:none}
tbody tr:nth-child(even) td{background:rgba(255,255,255,.015)}
tbody tr:hover td{background:rgba(139,124,255,.07)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.light{display:inline-block;min-width:34px;text-align:center;font-size:12px;font-weight:700;
border-radius:999px;padding:2px 10px;color:#0b0e15}
.light.green{background:var(--green);box-shadow:0 0 14px rgba(52,211,153,.5)}
.light.yellow{background:var(--yellow);box-shadow:0 0 14px rgba(224,184,78,.5)}
.light.red{background:var(--red);box-shadow:0 0 14px rgba(248,113,113,.5)}
.light.gray{background:#3a4358;color:#aab3c8}
.row-missing td{color:var(--muted)}
.tag{display:inline-block;font-size:11.5px;font-weight:600;border-radius:999px;padding:2px 9px;margin-right:6px}
.tag.src{background:var(--accent-soft);color:var(--accent-2)}
.tag.miss{background:var(--red-soft);color:var(--red)}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:9px;vertical-align:1px}
.dir{font-size:12px;font-weight:600;margin-left:8px;white-space:nowrap;font-variant-numeric:tabular-nums}
.card{background:linear-gradient(165deg,#141a28 0%,#0f131c 100%);border:1px solid var(--line);
border-radius:18px;padding:20px 24px;
box-shadow:0 16px 38px rgba(0,0,0,.45),inset 0 1px 0 rgba(255,255,255,.05)}
.ai-overall{border-color:rgba(139,124,255,.45);
box-shadow:0 18px 48px rgba(0,0,0,.5),0 0 30px rgba(139,124,255,.12),inset 0 1px 0 rgba(255,255,255,.06);
background:linear-gradient(160deg,#161c2c 45%,#12101f 150%)}
.ai-overall h3{font-size:19px;line-height:1.5;margin-bottom:6px}
.stance{display:inline-block;background:var(--accent-soft);color:var(--accent-2);
border-radius:10px;padding:6px 13px;font-size:13.5px;margin:8px 0 14px}
.ai-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(430px,1fr));gap:16px;margin-top:18px}
.ai-card h4{font-size:15.5px;color:var(--accent-2);margin-bottom:4px}
.ai-card .head{font-size:14px;font-weight:600;margin-bottom:8px}
.ai-card li{font-size:13.5px;margin:3px 0 3px 18px;color:#c3cad9}
.risks{margin-top:8px}
.risks li{color:var(--red)}
.risks b,.signals b{display:block;font-size:12px;color:var(--muted);margin-bottom:2px}
.chart-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:18px}
.chart-wrap{background:linear-gradient(165deg,#141a28,#0f131c);border:1px solid var(--line);
border-radius:18px;padding:16px 20px 8px;
box-shadow:0 16px 38px rgba(0,0,0,.45),inset 0 1px 0 rgba(255,255,255,.05)}
.chart-title{font-size:14.5px;font-weight:600;margin-bottom:4px;color:#d7ddea}
.chart{width:100%;height:300px}
.chart-fallback{font-size:12.5px;margin-top:8px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.mini{background:linear-gradient(170deg,#141a28,#0f141f);border:1px solid var(--line);border-radius:14px;
padding:12px 16px;box-shadow:inset 0 1px 0 rgba(255,255,255,.05)}
.mini b{display:block;font-size:19px;color:var(--accent-2);font-variant-numeric:tabular-nums}
.mini span{color:var(--muted);font-size:12px}
details.city{background:var(--card);border:1px solid var(--line);border-radius:16px;margin-top:14px}
details.city summary{cursor:pointer;list-style:none;padding:13px 18px;font-size:14px;font-weight:600}
details.city summary::-webkit-details-marker{display:none}
details.city summary::before{content:"▸";color:var(--accent);margin-right:8px}
details.city[open] summary::before{content:"▾"}
details.city table{border:none;border-radius:0;box-shadow:none}
h3.sub-sec{margin:24px 0 8px;font-size:16px;color:#c3cad9}
footer{margin-top:60px;border-top:1px solid var(--line);padding-top:22px;color:var(--muted);font-size:12.5px}
footer li{margin:3px 0 3px 18px}
"""

_ECHARTS_CDN = "https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"

_PALETTE = ["#8b7cff", "#e8b13c", "#34d399", "#58a6ff", "#f87171", "#a78bfa"]

# 板块识别色：表格中板块列的色点
_SECTOR_COLORS = {
    "prosperity": "#8b7cff",
    "employment": "#34d399",
    "inflation": "#e8b13c",
    "consumption": "#58a6ff",
    "housing": "#f472b6",
    "industry": "#2dd4bf",
    "trade": "#fbbf24",
}

_LOGO_SVG = (
    '<svg viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" role="img" '
    'aria-label="宏观监测"><g stroke="#ffffff" stroke-width="1.8" fill="none" '
    'stroke-linecap="round"><path d="M6 38L18 24L27 30L42 12"/>'
    '<path d="M34 12H42V20"/></g><g fill="#ffffff">'
    '<circle cx="6" cy="38" r="3"/><circle cx="18" cy="24" r="3"/>'
    '<circle cx="27" cy="30" r="3"/><circle cx="42" cy="12" r="3"/></g></svg>'
)

_FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E"
    "%3Crect width='48' height='48' rx='12' fill='%236c4cf1'/%3E"
    "%3Cg stroke='%23ffffff' stroke-width='2' fill='none' stroke-linecap='round'%3E"
    "%3Cpath d='M6 38L18 24L27 30L42 12M34 12H42V20'/%3E%3C/g%3E"
    "%3Cg fill='%23ffffff'%3E%3Ccircle cx='6' cy='38' r='3'/%3E"
    "%3Ccircle cx='18' cy='24' r='3'/%3E%3Ccircle cx='27' cy='30' r='3'/%3E"
    "%3Ccircle cx='42' cy='12' r='3'/%3E%3C/g%3E%3C/svg%3E"
)

_SOURCE_TYPE_LABELS = {
    "nbs": "国家统计局月度数据库 easyquery（data.stats.gov.cn）",
    "nbs_csyd": "国家统计局城市月度库 csyd（data.stats.gov.cn）",
    "eastmoney": "东方财富数据中心 JSON 接口（datacenter-web.eastmoney.com）",
    "statsweb_house": "国家统计局官网月度新闻稿（www.stats.gov.cn）",
    "statsweb_profit": "国家统计局官网月度新闻稿（www.stats.gov.cn）",
    "statsweb_unemp": "国家统计局官网·国民经济运行情况（www.stats.gov.cn）",
    "statsweb_pmi_detail": "国家统计局官网 PMI 月度报告（www.stats.gov.cn）",
    "customs_trade": "海关总署官网统计快讯（www.customs.gov.cn）",
    "customs_index": "海关总署外贸指数（tjs.customs.gov.cn）",
    "mohrss_release": "人力资源社会保障部官网发布会实录（www.mohrss.gov.cn）",
}

_SECTOR_NAME = {sector["id"]: sector["name"] for sector in indicators.SECTORS}


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def fmt_value(value: Any, unit: str = "") -> str:
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    text = "{:,.2f}".format(number).rstrip("0").rstrip(".")
    return text + (unit or "")


def _fmt_period(period: Any) -> str:
    text = str(period or "")
    return text.replace("-", "年", 1) + "月" if len(text) == 7 else (text or "—")


def _arrow(diff: float) -> str:
    if diff > 0.00005:
        return "↑"
    if diff < -0.00005:
        return "↓"
    return "→"


def _direction_text(unit: str, diff: float) -> str:
    """较上期变化文案：明确上升/下降（或增加/减少）与幅度。"""
    if abs(diff) < 0.00005:
        return "与上期持平"
    if diff > 0:
        verb = "增加" if unit == "城" else "上升"
    else:
        verb = "减少" if unit == "城" else "下降"
    magnitude = fmt_value(abs(diff))
    if unit == "城":
        return "较上期{} {} 城".format(verb, magnitude)
    if unit == "%":
        return "较上期{} {} 个百分点".format(verb, magnitude)
    if unit in ("上月=100", "上年同月=100"):
        return "较上期{} {} 点".format(verb, magnitude)
    return "较上期{} {} {}".format(verb, magnitude, unit)


def _change_text(db: Database, indicator_id: str, kind: str) -> Tuple[str, str]:
    """返回 (方向箭头, 较上期文案)；上期数据缺失时为空串。"""
    series = db.series(indicator_id, kind=kind, limit=2)
    if len(series) < 2:
        return "", ""
    current, previous = series[-1], series[-2]
    if current.get("value") is None or previous.get("value") is None:
        return "", ""
    diff = float(current["value"]) - float(previous["value"])
    return _arrow(diff), _direction_text(current.get("unit") or "", diff)


# ---------- 数据装配 ----------

def _light_cell(color: Optional[str]) -> str:
    label = {"green": "绿", "yellow": "黄", "red": "红"}.get(color or "", "无")
    cls = color or "gray"
    return '<span class="light {}">{}</span>'.format(cls, label)


def _overview_rows(db: Database) -> List[Dict[str, Any]]:
    rows = []
    for spec in indicators.INDICATORS:
        indicator_id = spec["id"]
        latest = db.latest_by_kinds(indicator_id)
        main = latest.get(spec.get("main_kind", "")) or {}
        light = None
        light_note = ""
        arrow = ""
        direction = ""
        rule_kind = ""
        for (rule_id, kind) in indicators.LIGHT_RULES:
            if rule_id != indicator_id:
                continue
            row = latest.get(kind)
            if row and row.get("value") is not None:
                light = indicators.light_for(indicator_id, kind, float(row["value"]))
                light_note = "{} {}".format(
                    indicators.KIND_META.get(kind, kind),
                    fmt_value(row["value"], row.get("unit") or ""))
                rule_kind = kind
                break
        if rule_kind:
            arrow, direction = _change_text(db, indicator_id, rule_kind)
        rows.append({
            "sector": _SECTOR_NAME.get(spec["sector"], spec["sector"]),
            "sector_color": _SECTOR_COLORS.get(spec["sector"], "#8b93a7"),
            "name": spec["name"],
            "period": main.get("period") or db.latest_period(indicator_id) or "",
            "value": fmt_value(main.get("value"), main.get("unit")) if main else "暂无数据",
            "light": light,
            "light_note": light_note,
            "arrow": arrow,
            "direction": direction,
        })
    return rows


def _series(db: Database, indicator_id: str, kind: str, name: str,
            bar: bool = False, axis: int = 0, color: Optional[str] = None) -> Dict[str, Any]:
    return {"name": name, "bar": bar, "axis": axis, "color": color,
            "points": [[row["period"], row["value"]]
                       for row in db.series(indicator_id, kind=kind)]}


def _chart_specs(db: Database, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    months = int(config.get("site", {}).get("chart_months", 24))

    def take(series: Dict[str, Any]) -> Dict[str, Any]:
        return {**series, "points": series["points"][-months:]}

    return [
        {"id": "chart-prosperity", "title": "制造业 PMI（%）", "unit0": "%",
         "series": [take(_series(db, "pmi", "value", "制造业PMI",
                                 color=_PALETTE[0]))]},
        {"id": "chart-employment", "title": "城镇调查失业率（%）", "unit0": "%",
         "series": [take(_series(db, "unemp_rate", "unemp_rate", "城镇调查失业率",
                                 color=_PALETTE[0])),
                    take(_series(db, "unemp_rate", "lab_1624", "16-24岁（不含在校生）",
                                 color=_PALETTE[4]))]},
        {"id": "chart-inflation", "title": "CPI / PPI 同比（%）", "unit0": "%",
         "series": [take(_series(db, "cpi", "yoy", "CPI同比", color=_PALETTE[0])),
                    take(_series(db, "ppi", "yoy", "PPI同比", color=_PALETTE[1]))]},
        {"id": "chart-consumption", "title": "社会消费品零售总额同比（%）", "unit0": "%",
         "series": [take(_series(db, "retail_sales", "yoy", "社零同比",
                                 color=_PALETTE[0]))]},
        {"id": "chart-housing", "title": "房价景气：分线环比指数与上涨城市数", "unit0": "上月=100", "unit1": "城",
         "series": [take(_series(db, "house_70", "tier1_mom", "一线环比", color=_PALETTE[0])),
                    take(_series(db, "house_70", "tier2_mom", "二线环比", color=_PALETTE[1])),
                    take(_series(db, "house_70", "tier3_mom", "三线环比", color=_PALETTE[2])),
                    take(_series(db, "house_70", "rise_count_mom", "环比上涨城市数",
                                 bar=True, axis=1, color=_PALETTE[4]))]},
        {"id": "chart-industry", "title": "工业增加值与工业企业利润同比（%）", "unit0": "%",
         "series": [take(_series(db, "ind_va", "yoy", "工业增加值同比", color=_PALETTE[0])),
                    take(_series(db, "ind_profit", "accum_yoy", "工业企业利润累计同比",
                                 color=_PALETTE[1]))]},
        {"id": "chart-trade", "title": "进出口总值（亿美元）", "unit0": "亿美元",
         "series": [take(_series(db, "trade_total", "value", "进出口总值", color=_PALETTE[0])),
                    take(_series(db, "trade_total", "export", "出口", color=_PALETTE[2])),
                    take(_series(db, "trade_total", "import", "进口", color=_PALETTE[1]))]},
    ]


def _chart_payload(spec: Dict[str, Any]) -> Dict[str, Any]:
    periods = sorted({period for series in spec["series"]
                      for period, _ in series["points"]})
    mapping = {series["name"]: dict(series["points"]) for series in spec["series"]}
    aligned = []
    for series in spec["series"]:
        aligned.append({
            "name": series["name"], "bar": series.get("bar", False),
            "axis": series.get("axis", 0), "color": series.get("color"),
            "data": [mapping[series["name"]].get(period) for period in periods],
        })
    return {"id": spec["id"], "title": spec["title"],
            "unit0": spec.get("unit0", ""), "unit1": spec.get("unit1", ""),
            "x": periods, "series": aligned}


def _house_agg_cards(db: Database) -> Tuple[str, List[Dict[str, Any]]]:
    latest = db.latest_by_kinds("house_70")
    period = (latest.get("rise_count_mom") or {}).get("period", "")
    cards = []
    for kind in ("rise_count_mom", "rise_count_yoy", "tier1_mom", "tier1_yoy",
                 "tier2_mom", "tier2_yoy", "tier3_mom", "tier3_yoy"):
        row = latest.get(kind)
        cards.append({
            "label": indicators.KIND_META.get(kind, kind),
            "value": fmt_value(row["value"], row.get("unit") or "") if row else "—",
        })
    return period, cards


def _house_city_rows(db: Database) -> Tuple[str, Dict[str, Dict[str, float]]]:
    period = db.latest_period("house_70") or ""
    cities: Dict[str, Dict[str, float]] = {}
    if not period:
        return period, cities
    for row in db.series("house_70", city=None):
        if row["period"] != period or not row["city"]:
            continue
        if row["kind"] not in ("city_mom", "city_yoy", "city_mom_2nd", "city_yoy_2nd"):
            continue
        cities.setdefault(str(row["city"]), {})[str(row["kind"])] = float(row["value"])
    return period, cities


def _city_cell(cities: Dict[str, Dict[str, float]], city: str, kind: str) -> str:
    value = cities.get(city, {}).get(kind)
    return fmt_value(value, "上月=100" if "mom" in kind else "上年同月=100") \
        if value is not None else "—"


def _calendar_rows(db: Database) -> List[Dict[str, Any]]:
    rows = []
    for spec in indicators.INDICATORS:
        indicator_id = spec["id"]
        latest = db.latest_by_kinds(indicator_id)
        period = db.latest_period(indicator_id) or ""
        missing = not period
        if spec["id"] == "house_70":
            value_text = fmt_value((latest.get("rise_count_mom") or {}).get("value"), "城")
            value_text += "（环比上涨）"
        elif spec["id"] == "trade_total":
            main = latest.get("value") or {}
            export_yoy = latest.get("export_yoy") or {}
            value_text = fmt_value(main.get("value"), "亿美元")
            if export_yoy:
                value_text += "，出口同比 {}%".format(export_yoy["value"])
        else:
            main = latest.get(spec.get("main_kind", "")) or {}
            value_text = fmt_value(main.get("value"), main.get("unit"))
        # 较上期方向（与最新值同口径）
        if spec["id"] == "house_70":
            change_kind = "rise_count_mom"
        elif spec["id"] == "trade_total":
            change_kind = "value"
        else:
            change_kind = spec.get("main_kind", "")
        arrow, direction = (_change_text(db, indicator_id, change_kind)
                            if change_kind else ("", ""))
        any_row = next(iter(latest.values()), None) if latest else None
        next_date = indicators.next_release_date(period, spec["release"]) if period else "—"
        rows.append({
            "sector": _SECTOR_NAME.get(spec["sector"], spec["sector"]),
            "sector_color": _SECTOR_COLORS.get(spec["sector"], "#8b93a7"),
            "name": spec["name"],
            "period": _fmt_period(period),
            "value": value_text if not missing else "暂无数据",
            "arrow": arrow if not missing else "",
            "direction": direction if not missing else "",
            "source": str((any_row or {}).get("source") or "—"),
            "next": next_date,
            "note": indicators.release_note(spec["release"])
            + (spec.get("missing_note", "") if missing else ""),
            "missing": missing,
        })
    return rows


def _source_rows() -> List[Dict[str, Any]]:
    rows = []
    for spec in indicators.INDICATORS:
        implemented = "；".join(_SOURCE_TYPE_LABELS.get(source["type"], source["type"])
                                for source in spec["sources"])
        rows.append({
            "name": spec["name"],
            "official": spec["official"],
            "implemented": implemented,
        })
    return rows


def _ai_blocks(db: Database) -> Tuple[Optional[Dict[str, Any]], List[Tuple[str, Optional[Dict[str, Any]]]]]:
    stored = db.interpretations()
    overall = stored.get("overall/latest")
    sectors = [(sector, stored.get(sector["id"] + "/latest"))
               for sector in indicators.SECTORS]
    return overall, sectors


# ---------- HTML 渲染 ----------

def _render_overview(rows: List[Dict[str, Any]], note: str) -> str:
    light_colors = {"green": "var(--green)", "yellow": "var(--yellow)",
                    "red": "var(--red)"}
    body = []
    for row in rows:
        sector_cell = ('<span class="dot" style="background:{color};'
                       'box-shadow:0 0 8px {color}"></span>{sector}').format(
            color=esc(row["sector_color"]), sector=esc(row["sector"]))
        if row["direction"]:
            color = light_colors.get(row["light"] or "", "var(--muted)")
            basis = '{}<span class="dir" style="color:{}">{} {}</span>'.format(
                esc(row["light_note"]), color, esc(row["arrow"]),
                esc(row["direction"]))
        else:
            basis = esc(row["light_note"]) or "—"
        cells = [
            "<td>{}</td>".format(sector_cell),
            "<td>{}</td>".format(esc(row["name"])),
            '<td class="num">{}</td>'.format(esc(row["value"])),
            "<td>{}</td>".format(esc(_fmt_period(row["period"]))),
            "<td>{}</td>".format(_light_cell(row["light"])),
            "<td>{}</td>".format(basis),
        ]
        body.append("<tr>{}</tr>".format("".join(cells)))
    return ('<table><thead><tr><th>板块</th><th>指标</th><th class="num">最新值</th>'
            '<th>数据期</th><th>信号</th><th>信号依据</th></tr></thead><tbody>{}</tbody></table>'
            '<p class="sec-note" style="margin-top:12px">{}</p>').format("".join(body), esc(note))


def _render_ai(overall: Optional[Dict[str, Any]],
               sectors: List[Tuple[str, Optional[Dict[str, Any]]]]) -> str:
    parts: List[str] = []
    if overall:
        parts.append('<div class="card ai-overall"><h3>{}</h3>'
                     '<span class="stance">{}</span>'
                     '<div class="signals"><b>组合信号</b><ul>{}</ul></div>'
                     '<div class="risks"><b>风险提示</b><ul>{}</ul></div>'
                     '<p class="sec-note" style="margin:10px 0 0">前瞻：{}</p></div>'.format(
                         esc(overall.get("headline", "")),
                         esc(overall.get("stance", "")),
                         "".join("<li>{}</li>".format(esc(item))
                                 for item in overall.get("signals") or []),
                         "".join("<li>{}</li>".format(esc(item))
                                 for item in overall.get("risks") or []) or
                         "<li>—</li>",
                         esc(overall.get("outlook", ""))))
    else:
        parts.append('<div class="card ai-overall"><h3>综合研判尚未生成</h3>'
                     '<span class="stance">运行 run 命令补齐 AI 解读</span></div>')
    cards = []
    for sector, content in sectors:
        if content:
            cards.append('<div class="card ai-card"><h4>{}</h4>'
                         '<p class="head">{}</p>'
                         '<div class="signals"><b>要点</b><ul>{}</ul></div>'
                         '<div class="risks"><b>风险提示</b><ul>{}</ul></div></div>'.format(
                             esc(sector["name"]), esc(content.get("headline", "")),
                             "".join("<li>{}</li>".format(esc(item))
                                     for item in content.get("points") or []),
                             "".join("<li>{}</li>".format(esc(item))
                                     for item in content.get("risks") or []) or
                             "<li>—</li>"))
        else:
            cards.append('<div class="card ai-card"><h4>{}</h4>'
                         '<p class="head" style="color:var(--muted)">本板块暂无解读（数据缺失或尚未生成）</p></div>'.format(
                             esc(sector["name"])))
    parts.append('<div class="ai-grid">{}</div>'.format("".join(cards)))
    return "".join(parts)


def _render_charts(specs: List[Dict[str, Any]]) -> str:
    blocks = []
    for spec in specs:
        payload = _chart_payload(spec)
        if not payload["x"]:
            blocks.append(
                '<div class="chart-wrap"><div class="chart-title">{}</div>'
                '<p style="color:var(--muted);font-size:13px;padding:40px 0 20px">暂无数据，运行 run 后展示</p></div>'.format(
                    esc(spec["title"])))
            continue
        header = "<tr><th>数据期</th>{}</tr>".format(
            "".join("<th>{}</th>".format(esc(series["name"]))
                    for series in payload["series"]))
        body_rows = []
        for index, period in enumerate(payload["x"]):
            cells = ["<td>{}</td>".format(esc(period))]
            for series in payload["series"]:
                value = series["data"][index]
                cells.append('<td class="num">{}</td>'.format(
                    fmt_value(value) if value is not None else "—"))
            body_rows.append("<tr>{}</tr>".format("".join(cells)))
        fallback = ('<table class="chart-fallback" hidden><thead>{}</thead>'
                    '<tbody>{}</tbody></table>').format(header, "".join(body_rows))
        blocks.append(
            '<div class="chart-wrap"><div class="chart-title">{}</div>'
            '<div class="chart" id="{}" data-spec="{}" role="img" '
            'aria-label="{}趋势图"></div>{}</div>'.format(
                esc(spec["title"]), esc(spec["id"]),
                html.escape(json.dumps(payload, ensure_ascii=False), quote=True),
                esc(spec["title"]), fallback))
    return ('<div class="chart-grid">{}</div>'
            '<p class="sec-note" style="margin-top:12px">图表由 ECharts CDN 渲染；'
            'CDN 不可用时自动降级为上方表格。</p>').format("".join(blocks))


def _render_house(db: Database) -> str:
    period, cards = _house_agg_cards(db)
    if not period:
        return ('<div class="card"><p style="color:var(--muted)">70 城房价数据尚未抓取，'
                '运行 run 后展示。</p></div>')
    card_html = "".join(
        '<div class="mini"><b>{}</b><span>{}</span></div>'.format(
            esc(card["value"]), esc(card["label"]))
        for card in cards)
    _, cities = _house_city_rows(db)
    ordered = sorted(cities, key=lambda city: -cities[city].get("city_mom", -999))
    top = ordered[:5]
    bottom = ordered[-5:][::-1]

    def city_table(names: List[str]) -> str:
        rows = []
        for city in names:
            rows.append(
                "<tr><td>{}</td><td class=\"num\">{}</td><td class=\"num\">{}</td>"
                "<td class=\"num\">{}</td><td class=\"num\">{}</td></tr>".format(
                    esc(city),
                    esc(_city_cell(cities, city, "city_mom")),
                    esc(_city_cell(cities, city, "city_yoy")),
                    esc(_city_cell(cities, city, "city_mom_2nd")),
                    esc(_city_cell(cities, city, "city_yoy_2nd"))))
        return ('<table><thead><tr><th>城市</th><th class="num">新建环比</th>'
                '<th class="num">新建同比</th><th class="num">二手环比</th>'
                '<th class="num">二手同比</th></tr></thead><tbody>{}</tbody></table>').format(
                    "".join(rows))

    full_rows = []
    for tier, city_list in indicators.CITY_TIERS.items():
        for city in city_list:
            if city not in cities:
                continue
            full_rows.append(
                "<tr><td>{}</td><td>{}</td><td class=\"num\">{}</td>"
                "<td class=\"num\">{}</td><td class=\"num\">{}</td>"
                "<td class=\"num\">{}</td></tr>".format(
                    esc(city), tier,
                    esc(_city_cell(cities, city, "city_mom")),
                    esc(_city_cell(cities, city, "city_yoy")),
                    esc(_city_cell(cities, city, "city_mom_2nd")),
                    esc(_city_cell(cities, city, "city_yoy_2nd"))))
    full_table = ('<table><thead><tr><th>城市</th><th>城市线</th><th class="num">新建环比</th>'
                  '<th class="num">新建同比</th><th class="num">二手环比</th>'
                  '<th class="num">二手同比</th></tr></thead><tbody>{}</tbody></table>').format(
                      "".join(full_rows))
    return ('<div class="cards">{}</div>'
            '<h3 class="sub-sec">新建住宅环比领涨前五</h3>{top}'
            '<h3 class="sub-sec">新建住宅环比领跌前五</h3>{bottom}'
            '<details class="city"><summary>70 城完整明细（数据期 {period}）</summary>{full}</details>'
            ).format(card_html, top=city_table(top), bottom=city_table(bottom),
                     period=esc(_fmt_period(period)), full=full_table)


def _render_calendar(rows: List[Dict[str, Any]]) -> str:
    body = []
    for row in rows:
        cls = " class=\"row-missing\"" if row["missing"] else ""
        tag = '<span class="tag miss">数据缺失</span>' if row["missing"] else ""
        sector_cell = ('<span class="dot" style="background:{color};'
                       'box-shadow:0 0 8px {color}"></span>{sector}').format(
            color=esc(row["sector_color"]), sector=esc(row["sector"]))
        dir_html = ('<span class="dir" style="color:var(--muted)">{} {}</span>'.format(
            esc(row["arrow"]), esc(row["direction"]))) if row["direction"] else "—"
        body.append(
            "<tr{}><td>{}</td><td>{}{}</td><td class=\"num\">{}</td><td>{}</td>"
            "<td>{}</td><td>{}</td><td class=\"num\">{}</td><td>{}</td></tr>".format(
                cls, sector_cell, esc(row["name"]), tag, esc(row["value"]),
                dir_html, esc(row["source"]), esc(row["period"]),
                esc(row["next"]), esc(row["note"])))
    return ('<table><thead><tr><th>板块</th><th>指标</th><th class="num">最新值</th>'
            '<th>较上期</th><th>数据来源</th><th>最新数据期</th>'
            '<th class="num">预计下期发布</th><th>备注</th></tr></thead>'
            '<tbody>{}</tbody></table>').format("".join(body))


def _render_sources(rows: List[Dict[str, Any]]) -> str:
    body = []
    for row in rows:
        body.append("<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            esc(row["name"]), esc(row["official"]), esc(row["implemented"])))
    return ('<table><thead><tr><th>指标</th><th>官方发布渠道</th><th>本项目接入的免费公开来源'
            '（按优先级）</th></tr></thead><tbody>{}</tbody></table>'
            '<div class="card" style="margin-top:14px"><b>付费终端参考</b>'
            '<p class="sec-note" style="margin:6px 0 0">Wind（万得）、CEIC、同花顺 iFinD '
            '均覆盖以上全部指标并可导出历史序列，适合机构级回测；完整对比与订阅要点见 '
            'DESIGN.md《官方数据源清单》。本项目默认只用免费公开接口，不依赖任何付费账号。</p></div>'
            ).format("".join(body))


_CHART_JS = """
const PALETTE = __PALETTE__;
function makeOption(spec){
  var hasSecond = spec.series.some(function(s){return s.axis===1;});
  var yAxis = [{type:'value', name: spec.unit0 || '', scale:true,
    nameTextStyle:{color:'#8b93a7'}, splitLine:{lineStyle:{color:'#1a2130'}},
    axisLabel:{color:'#8b93a7'}}];
  if(hasSecond){ yAxis.push({type:'value', name: spec.unit1 || '', scale:true,
    nameTextStyle:{color:'#8b93a7'}, splitLine:{show:false},
    axisLabel:{color:'#8b93a7'}}); }
  var series = spec.series.map(function(s, i){
    var color = s.color || PALETTE[i % PALETTE.length];
    if(s.bar){ return {name:s.name, type:'bar', yAxisIndex:s.axis, data:s.data,
      itemStyle:{color:color, borderRadius:[3,3,0,0]}, barMaxWidth:20}; }
    return {name:s.name, type:'line', yAxisIndex:s.axis, data:s.data, smooth:true,
      symbol:'circle', symbolSize:5, lineStyle:{width:2.5, color:color},
      itemStyle:{color:color}};
  });
  return {tooltip:{trigger:'axis', backgroundColor:'#141a28', borderColor:'#2a3245',
      textStyle:{color:'#d7ddea'}},
    legend:{top:0, type:'scroll', textStyle:{fontSize:11, color:'#a6b0c6'}},
    grid:{left:50, right:44, top:36, bottom:30},
    xAxis:{type:'category', data:spec.x,
      axisLabel:{rotate:45, fontSize:10, color:'#8b93a7'},
      axisLine:{lineStyle:{color:'#2a3245'}}},
    yAxis:yAxis, series:series};
}
function renderCharts(){
  var nodes = Array.prototype.slice.call(document.querySelectorAll('.chart'));
  if(typeof echarts === 'undefined'){
    document.querySelectorAll('.chart-fallback').forEach(function(el){el.hidden=false;});
    return;
  }
  document.querySelectorAll('.chart-fallback').forEach(function(el){el.hidden=true;});
  nodes.forEach(function(el){
    var chart = echarts.init(el, null, {renderer:'canvas'});
    chart.setOption(makeOption(JSON.parse(el.getAttribute('data-spec'))));
  });
  window.addEventListener('resize', function(){
    nodes.forEach(function(el){
      var chart = echarts.getInstanceByDom(el);
      if(chart){ chart.resize(); }
    });
  });
}
window.addEventListener('DOMContentLoaded', renderCharts);
"""


def render_report(db: Database, config: Dict[str, Any], today: Optional[Any] = None) -> str:
    now = today or datetime.now()
    site = config.get("site") or {}
    overview_rows = _overview_rows(db)
    covered = sum(1 for row in overview_rows if row["period"])
    total = len(indicators.INDICATORS)
    periods = db.distinct_periods()
    latest_periods = [row["period"] for row in overview_rows if row["period"]]
    latest_period = max(latest_periods) if latest_periods else ""
    overall, sector_blocks = _ai_blocks(db)
    ai_count = (1 if overall else 0) + sum(1 for _, content in sector_blocks if content)
    sector_total = len(indicators.SECTORS) + 1
    threshold_note = str(config.get("pipeline", {}).get(
        "light_threshold_note", "红绿灯阈值为经验性设定，仅作视觉提示，以 AI 解读为准"))
    html_text = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} · {date}</title>
<link rel="icon" href="{favicon}">
<style>{style}</style>
</head>
<body>
<header class="hero"><div class="wrap">
<div class="brand"><div class="logo">{logo}</div>
<div><div class="kicker">MACRO MONITOR · 月度宏观数据监测</div>
<h1>{name}</h1><div class="sub">{date} 生成 · 数据来自国家统计局 / 海关总署 / 人力资源社会保障部官方公开渠道</div></div></div>
<div class="stats">
<div class="stat"><b>{covered} / {total}</b><span>指标覆盖率</span></div>
<div class="stat"><b>{latest_period}</b><span>最新数据期</span></div>
<div class="stat"><b>{periods}</b><span>累计数据期数</span></div>
<div class="stat"><b>{ai_count} / {sector_total}</b><span>AI 解读段落</span></div>
<div class="stat"><b>{obs}</b><span>观测条数</span></div>
</div>
<nav class="nav">
<a href="#overview">景气总览</a><a href="#ai">AI 解读</a><a href="#charts">趋势图</a>
<a href="#housing">70城专项</a><a href="#calendar">数据日历</a><a href="#sources">数据源清单</a>
</nav>
</div></header>
<main class="wrap">
<h2 class="sec" id="overview"><span class="sec-num">01</span>景气总览红绿灯</h2>
<p class="sec-note">信号基于最新可得数据；箭头与“较上期”为与上一数据期的变化方向及幅度；部分指标数据期不同（如工业企业利润滞后一个月），以数据日历为准。</p>
{overview}
<h2 class="sec" id="ai"><span class="sec-num">02</span>AI 重点解读</h2>
<p class="sec-note">以下解读由 AI 仅依据本页官方数据生成，不引用外部信息、不预测具体数值。</p>
{ai}
<h2 class="sec" id="charts"><span class="sec-num">03</span>趋势图</h2>
<p class="sec-note">近 {chart_months} 个月走势。</p>
{charts}
<h2 class="sec" id="housing"><span class="sec-num">04</span>70 城房价专项</h2>
<p class="sec-note">国家统计局 70 个大中城市商品住宅销售价格指数（新建 / 二手）。</p>
{house}
<h2 class="sec" id="calendar"><span class="sec-num">05</span>数据日历</h2>
<p class="sec-note">最新数据期、较上期变化、来源与预计下期发布时间（例行日可能随节假日微调）。</p>
{calendar}
<h2 class="sec" id="sources"><span class="sec-num">06</span>数据源清单附录</h2>
<p class="sec-note">全部为官方免费公开渠道；付费终端对比详见 DESIGN.md。</p>
{sources}
</main>
<footer><div class="wrap">
本看板由 macro-monitor 自动生成；数据来自官方公开渠道，AI 解读仅供研究参考，不构成投资建议。
<ul><li>单一指标获取失败不会影响其他指标（多源兜底）；"数据缺失"标注表示当前网络环境无法访问对应官方渠道。</li>
<li>红绿灯阈值：{threshold}</li></ul>
</div></footer>
<script src="{echarts_cdn}"></script>
<script>{chart_js}</script>
</body>
</html>""".format(
        name=esc(site.get("name", "宏观经济主要指标AI解读")),
        date=now.strftime("%Y-%m-%d"),
        favicon=_FAVICON, style=_STYLE, logo=_LOGO_SVG,
        covered=covered, total=total, periods=periods,
        latest_period=_fmt_period(latest_period) if latest_period else "—",
        ai_count=ai_count, obs=db.observation_count(),
        sector_total=sector_total,
        overview=_render_overview(overview_rows, threshold_note),
        ai=_render_ai(overall, sector_blocks),
        chart_months=int(site.get("chart_months", 24)),
        charts=_render_charts(_chart_specs(db, config)),
        house=_render_house(db),
        calendar=_render_calendar(_calendar_rows(db)),
        sources=_render_sources(_source_rows()),
        threshold=esc(threshold_note),
        echarts_cdn=_ECHARTS_CDN,
        chart_js=_CHART_JS.replace("__PALETTE__", json.dumps(_PALETTE)),
    )
    return html_text


def build_report(db: Database, config: Dict[str, Any], out_dir: Path,
                 today: Optional[Any] = None) -> Dict[str, Any]:
    now = today or datetime.now()
    content = render_report(db, config, now)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "宏观监测-{}.html".format(now.strftime("%Y-%m-%d"))
    path.write_text(content, encoding="utf-8")
    return {"status": "success", "report": str(path), "size": path.stat().st_size}
