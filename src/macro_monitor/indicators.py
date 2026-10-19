from __future__ import annotations

import calendar
from typing import Any, Dict, List, Optional

# 七大板块
SECTORS: List[Dict[str, str]] = [
    {"id": "prosperity", "name": "宏观景气"},
    {"id": "employment", "name": "就业"},
    {"id": "inflation", "name": "通胀"},
    {"id": "consumption", "name": "消费"},
    {"id": "housing", "name": "房价"},
    {"id": "industry", "name": "工业"},
    {"id": "trade", "name": "进出口"},
]

# 70 个大中城市（统计局官方口径的一线/二线/三线划分）
CITY_TIERS: Dict[str, List[str]] = {
    "一线": ["北京", "上海", "广州", "深圳"],
    "二线": ["天津", "石家庄", "太原", "呼和浩特", "沈阳", "大连", "长春",
             "哈尔滨", "南京", "杭州", "宁波", "合肥", "福州", "厦门", "南昌",
             "济南", "青岛", "郑州", "武汉", "长沙", "南宁", "海口", "重庆",
             "成都", "贵阳", "昆明", "西安", "兰州", "西宁", "银川", "乌鲁木齐"],
    "三线": ["唐山", "秦皇岛", "包头", "丹东", "锦州", "吉林", "牡丹江", "无锡",
             "徐州", "扬州", "温州", "金华", "蚌埠", "安庆", "泉州", "九江", "赣州",
             "烟台", "济宁", "洛阳", "平顶山", "宜昌", "襄阳", "岳阳", "常德",
             "韶关", "湛江", "惠州", "桂林", "北海", "三亚", "泸州", "南充",
             "遵义", "大理"],
}

ALL_CITIES: List[str] = [city for cities in CITY_TIERS.values() for city in cities]


def city_tier(city: str) -> str:
    for tier, cities in CITY_TIERS.items():
        if city in cities:
            return tier
    return ""


# kind -> 展示标签
KIND_META: Dict[str, str] = {
    "value": "最新值",
    "yoy": "同比",
    "mom": "环比",
    "accum": "累计值",
    "accum_yoy": "累计同比",
    "month_yoy": "当月同比",
    "export": "出口额",
    "import": "进口额",
    "export_yoy": "出口同比",
    "import_yoy": "进口同比",
    "city_mom": "环比指数",
    "city_yoy": "同比指数",
    "city_mom_2nd": "二手环比指数",
    "city_yoy_2nd": "二手同比指数",
    "rise_count_mom": "环比上涨城市数",
    "rise_count_yoy": "同比上涨城市数",
    "tier1_mom": "一线环比均值",
    "tier1_yoy": "一线同比均值",
    "tier2_mom": "二线环比均值",
    "tier2_yoy": "二线同比均值",
    "tier3_mom": "三线环比均值",
    "tier3_yoy": "三线同比均值",
    # CPI 分类细项
    "cpi_urban_yoy": "城市同比",
    "cpi_rural_yoy": "农村同比",
    "cpi_food_yoy": "食品同比",
    "cpi_nonfood_yoy": "非食品同比",
    "cpi_goods_yoy": "消费品同比",
    "cpi_services_yoy": "服务同比",
    "cpi_core_yoy": "核心CPI同比",
    "cpi_foodtobacco_yoy": "食品烟酒及在外餐饮同比",
    "cpi_vegetable_yoy": "鲜菜同比",
    "cpi_meat_yoy": "畜肉类同比",
    "cpi_pork_yoy": "猪肉同比",
    "cpi_egg_yoy": "蛋类同比",
    "cpi_fruit_yoy": "鲜果同比",
    "cpi_clothing_yoy": "衣着同比",
    "cpi_residence_yoy": "居住同比",
    "cpi_daily_yoy": "生活用品及服务同比",
    "cpi_transport_yoy": "交通通信同比",
    "cpi_education_yoy": "教育文化娱乐同比",
    "cpi_healthcare_yoy": "医疗保健同比",
    "cpi_other_yoy": "其他用品及服务同比",
    # PPI 生产资料/生活资料与重点行业
    "ppi_means_yoy": "生产资料同比",
    "ppi_mining_yoy": "采掘工业同比",
    "ppi_rawmat_yoy": "原材料工业同比",
    "ppi_processing_yoy": "加工工业同比",
    "ppi_life_yoy": "生活资料同比",
    "ppi_life_food_yoy": "生活资料·食品同比",
    "ppi_life_clothing_yoy": "生活资料·衣着同比",
    "ppi_life_daily_yoy": "生活资料·一般日用品同比",
    "ppi_life_durable_yoy": "生活资料·耐用消费品同比",
    "ppi_buy_yoy": "购进价格同比",
    "ppi_coal_yoy": "煤炭采选业同比",
    "ppi_oilgas_yoy": "油气开采业同比",
    "ppi_oilprocess_yoy": "石油煤炭燃料加工业同比",
    "ppi_chemical_yoy": "化学原料制品业同比",
    "ppi_ferrous_yoy": "黑色金属冶炼同比",
    "ppi_nonferrous_yoy": "有色金属冶炼同比",
    "ppi_electronics_yoy": "电子设备制造业同比",
    "ppi_auto_yoy": "汽车制造业同比",
    "ppi_power_yoy": "电力热力生产同比",
    # 工业增加值门类与经济类型
    "indva_mining_yoy": "采矿业同比",
    "indva_manufacturing_yoy": "制造业同比",
    "indva_utilities_yoy": "电力热力燃气水同比",
    "indva_hightech_yoy": "高技术制造业同比",
    "indva_state_yoy": "国有控股同比",
    "indva_share_yoy": "股份制同比",
    "indva_foreign_yoy": "外商及港澳台同比",
    "indva_private_yoy": "私营同比",
    "indva_mom": "工业增加值环比",
    # 工业企业利润分类型/分行业
    "profit_state_accum": "国有控股累计利润",
    "profit_state_yoy": "国有控股累计同比",
    "profit_share_accum": "股份制累计利润",
    "profit_share_yoy": "股份制累计同比",
    "profit_foreign_accum": "外商及港澳台累计利润",
    "profit_foreign_yoy": "外商及港澳台累计同比",
    "profit_private_accum": "私营累计利润",
    "profit_private_yoy": "私营累计同比",
    "profit_mining_yoy": "采矿业利润同比",
    "profit_manufacturing_yoy": "制造业利润同比",
    "profit_utilities_yoy": "电力热力燃气水利润同比",
    # 社零分类
    "retail_goods_value": "商品零售额",
    "retail_goods_yoy": "商品零售同比",
    "retail_catering_value": "餐饮收入",
    "retail_catering_yoy": "餐饮收入同比",
    "retail_urban_yoy": "城镇同比",
    "retail_rural_yoy": "乡村同比",
    "retail_auto_yoy": "汽车类同比",
    "retail_food_yoy": "粮油食品类同比",
    "retail_oil_yoy": "石油及制品类同比",
    # 70城分面积段（全国平均）
    "new_a90_mom": "新建90㎡以下环比",
    "new_a90_yoy": "新建90㎡以下同比",
    "new_a90144_mom": "新建90-144㎡环比",
    "new_a90144_yoy": "新建90-144㎡同比",
    "new_a144_mom": "新建144㎡以上环比",
    "new_a144_yoy": "新建144㎡以上同比",
    "sec_a90_mom": "二手90㎡以下环比",
    "sec_a90_yoy": "二手90㎡以下同比",
    "sec_a90144_mom": "二手90-144㎡环比",
    "sec_a90144_yoy": "二手90-144㎡同比",
    "sec_a144_mom": "二手144㎡以上环比",
    "sec_a144_yoy": "二手144㎡以上同比",
    # 就业板块
    "unemp_rate": "全国城镇调查失业率",
    "lab_avg": "失业率平均值",
    "lab_local": "本地户籍失业率",
    "lab_migrant": "外来户籍失业率",
    "lab_agri": "外来农业户籍失业率",
    "lab_31cities": "31个大城市失业率",
    "lab_hours": "周平均工作时间",
    "lab_1624": "16-24岁失业率（不含在校生）",
    "lab_2529": "25-29岁失业率（不含在校生）",
    "lab_3059": "30-59岁失业率（不含在校生）",
    # PMI 分项指数（制造业/非制造业）
    "pmi_prod": "制造业·生产指数",
    "pmi_neworders": "制造业·新订单指数",
    "pmi_rawstock": "制造业·原材料库存指数",
    "pmi_emp_manuf": "制造业·从业人员指数",
    "pmi_supdelivery": "制造业·供应商配送时间指数",
    "pmi_newexport": "制造业·新出口订单指数",
    "pmi_import": "制造业·进口指数",
    "pmi_purchase": "制造业·采购量指数",
    "pmi_inputprice": "制造业·主要原材料购进价格指数",
    "pmi_exfactory": "制造业·出厂价格指数",
    "pmi_fgstock": "制造业·产成品库存指数",
    "pmi_backlog": "制造业·在手订单指数",
    "pmi_expectation": "制造业·生产经营活动预期指数",
    "npm_bizact": "非制造业·商务活动指数",
    "npm_neworders": "非制造业·新订单指数",
    "npm_newexport": "非制造业·新出口订单指数",
    "npm_backlog": "非制造业·在手订单指数",
    "npm_stock": "非制造业·存货指数",
    "npm_inputprice": "非制造业·投入品价格指数",
    "npm_saleprice": "非制造业·销售价格指数",
    "npm_emp": "非制造业·从业人员指数",
    "npm_supdelivery": "非制造业·供应商配送时间指数",
    "npm_expectation": "非制造业·业务活动预期指数",
    # 进出口细分
    "export_mom": "出口环比",
    "import_mom": "进口环比",
    "export_accum": "出口累计额",
    "import_accum": "进口累计额",
    "export_accum_yoy": "出口累计同比",
    "import_accum_yoy": "进口累计同比",
}

# 分类细项 kind 的前缀：在 AI 素材中只输出最新值与上期值（不输出 12 个月序列）
DETAIL_KIND_PREFIXES: tuple = (
    "cpi_", "ppi_", "indva_", "retail_", "profit_", "new_a", "sec_a",
    "lab_", "pmi_", "npm_", "export_", "import_")

# 比率类 kind 的默认单位；绝对值类 kind 用注册表里的指标 unit
KIND_UNIT: Dict[str, str] = {
    "yoy": "%",
    "mom": "%",
    "accum_yoy": "%",
    "month_yoy": "%",
    "export_yoy": "%",
    "import_yoy": "%",
    "city_mom": "上月=100",
    "city_yoy": "上年同月=100",
    "city_mom_2nd": "上月=100",
    "city_yoy_2nd": "上年同月=100",
    "rise_count_mom": "城",
    "rise_count_yoy": "城",
    "tier1_mom": "上月=100",
    "tier1_yoy": "上年同月=100",
    "tier2_mom": "上月=100",
    "tier2_yoy": "上年同月=100",
    "tier3_mom": "上月=100",
    "tier3_yoy": "上年同月=100",
    # 分类细项：同比类统一 %，金额类亿元
    "indva_mom": "%",
    "retail_goods_value": "亿元",
    "retail_catering_value": "亿元",
    "profit_state_accum": "亿元",
    "profit_share_accum": "亿元",
    "profit_foreign_accum": "亿元",
    "profit_private_accum": "亿元",
    "new_a90_mom": "上月=100",
    "new_a90144_mom": "上月=100",
    "new_a144_mom": "上月=100",
    "new_a90_yoy": "上年同月=100",
    "new_a90144_yoy": "上年同月=100",
    "new_a144_yoy": "上年同月=100",
    "sec_a90_mom": "上月=100",
    "sec_a90144_mom": "上月=100",
    "sec_a144_mom": "上月=100",
    "sec_a90_yoy": "上年同月=100",
    "sec_a90144_yoy": "上年同月=100",
    "sec_a144_yoy": "上年同月=100",
    # 就业/PMI/贸易细分
    "lab_hours": "小时",
    "export_accum": "亿美元",
    "import_accum": "亿美元",
    "pmi_emp_manuf": "%",
    "npm_emp": "%",
}

# 各指标发布规则：day 为该指标次月数据的例行发布日，None 表示月末最后一天
RELEASE_RULES: Dict[str, Dict[str, Any]] = {
    "month_end": {"day": None, "note": "当月最后一天发布"},
    "next_month_7": {"day": 7, "note": "次月 7 日左右发布（海关统计快讯）"},
    "next_month_9": {"day": 9, "note": "次月 9~10 日发布（统计局月度报告）"},
    "next_month_15": {"day": 15, "note": "次月 15~16 日发布（统计局月度报告）"},
    "next_month_20": {"day": 20, "note": "次月下旬发布（海关外贸指数）"},
    "next_month_27": {"day": 27, "note": "次月 27 日左右发布（统计局月度报告）"},
    "quarter_press": {"day": 27, "note": "季后次月下旬发布（人社部季度新闻发布会）"},
}

# 指标注册表：sources 按优先级排列，逐个尝试直到拿到数据
INDICATORS: List[Dict[str, Any]] = [
    {
        "id": "pmi",
        "sector": "prosperity",
        "name": "制造业PMI",
        "unit": "%",
        "main_kind": "value",
        "release": "month_end",
        "official": "国家统计局·制造业采购经理指数（月度报告）",
        "sources": [
            {"type": "nbs", "dbcode": "hgyd", "matches": [
                {"kind": "value", "include": ["制造业采购经理指数"],
                 "exclude": ["非制造业"]},
            ]},
            {"type": "eastmoney", "report_name": "RPT_ECONOMY_PMI",
             "fields": {"value": "MAKE_INDEX"}},
        ],
        # 分类细项：制造业/非制造业全部分项指数（PMI 月度报告时间序列表）
        "detail_sources": [
            {"type": "statsweb_pmi_detail", "news": "pmi",
             "source_label": "国家统计局官网·PMI月度报告分项指数",
             "rows": [
                 {"kind": "pmi_prod", "name": "生产", "table": 0, "unit": "%"},
                 {"kind": "pmi_neworders", "name": "新订单", "table": 0, "unit": "%"},
                 {"kind": "pmi_rawstock", "name": "原材料库存", "table": 0, "unit": "%"},
                 {"kind": "pmi_emp_manuf", "name": "从业人员", "table": 0, "unit": "%"},
                 {"kind": "pmi_supdelivery", "name": "供应商配送时间", "table": 0, "unit": "%"},
                 {"kind": "pmi_newexport", "name": "新出口订单", "table": 1, "unit": "%"},
                 {"kind": "pmi_import", "name": "进口", "table": 1, "unit": "%"},
                 {"kind": "pmi_purchase", "name": "采购量", "table": 1, "unit": "%"},
                 {"kind": "pmi_inputprice", "name": "主要原材料购进价格", "table": 1, "unit": "%"},
                 {"kind": "pmi_exfactory", "name": "出厂价格", "table": 1, "unit": "%"},
                 {"kind": "pmi_fgstock", "name": "产成品库存", "table": 1, "unit": "%"},
                 {"kind": "pmi_backlog", "name": "在手订单", "table": 1, "unit": "%"},
                 {"kind": "pmi_expectation", "name": "生产经营活动预期", "table": 1, "unit": "%"},
                 {"kind": "npm_bizact", "name": "商务活动", "table": 2, "unit": "%"},
                 {"kind": "npm_neworders", "name": "新订单", "table": 2, "unit": "%"},
                 {"kind": "npm_inputprice", "name": "投入品价格", "table": 2, "unit": "%"},
                 {"kind": "npm_saleprice", "name": "销售价格", "table": 2, "unit": "%"},
                 {"kind": "npm_emp", "name": "从业人员", "table": 2, "unit": "%"},
                 {"kind": "npm_expectation", "name": "业务活动预期", "table": 2, "unit": "%"},
                 {"kind": "npm_newexport", "name": "新出口订单", "table": 3, "unit": "%"},
                 {"kind": "npm_backlog", "name": "在手订单", "table": 3, "unit": "%"},
                 {"kind": "npm_stock", "name": "存货", "table": 3, "unit": "%"},
                 {"kind": "npm_supdelivery", "name": "供应商配送时间", "table": 3, "unit": "%"},
             ]},
        ],
    },
    {
        "id": "unemp_rate",
        "sector": "employment",
        "name": "全国城镇调查失业率",
        "unit": "%",
        "main_kind": "unemp_rate",
        "release": "next_month_15",
        "official": "国家统计局·国民经济运行情况月度报告（就业部分）",
        "missing_note": "分年龄组（16—24/25—29/30—59岁）失业率仅在国家统计局数据发布库发布（本机 403 风控），新闻稿含有时自动解析，缺失按缺失处理",
        "sources": [
            {"type": "statsweb_unemp"},
        ],
        # 景气先行：制造业/非制造业 PMI 从业人员指数
        "detail_sources": [
            {"type": "statsweb_pmi_detail", "news": "pmi",
             "source_label": "国家统计局官网·PMI月度报告（从业人员指数）",
             "rows": [
                 {"kind": "pmi_emp_manuf", "name": "从业人员", "table": 0, "unit": "%"},
                 {"kind": "npm_emp", "name": "从业人员", "table": 2, "unit": "%"},
             ]},
        ],
    },
    {
        "id": "new_jobs",
        "sector": "employment",
        "name": "城镇新增就业（累计）",
        "unit": "万人",
        "main_kind": "accum",
        "release": "quarter_press",
        "official": "人力资源社会保障部·季度例行新闻发布会实录",
        "missing_note": "人社部官网当前为动态渲染页面且部署反爬，本机无法访问；网络环境恢复后自动获取",
        "sources": [
            {"type": "mohrss_release"},
        ],
    },
    {
        "id": "cpi",
        "sector": "inflation",
        "name": "居民消费价格指数CPI",
        "unit": "%",
        "main_kind": "yoy",
        "release": "next_month_9",
        "official": "国家统计局·居民消费价格指数（月度报告）",
        "sources": [
            {"type": "nbs", "dbcode": "hgyd", "matches": [
                {"kind": "yoy", "include": ["居民消费价格指数", "上年同月=100"],
                 "transform": "minus100"},
                {"kind": "mom", "include": ["居民消费价格指数", "上月=100"],
                 "transform": "minus100"},
            ]},
            {"type": "eastmoney", "report_name": "RPT_ECONOMY_CPI",
             "fields": [
                 {"kind": "yoy", "field": "NATIONAL_SAME"},
                 {"kind": "mom", "field": "NATIONAL_BASE", "transform": "minus100"},
             ]},
        ],
        # 分类细项：八大类与食品细项（统计局官网 CPI 月度报告表格）
        "detail_sources": [
            {"type": "statsweb_news", "news": "cpi",
             "source_label": "国家统计局官网·CPI月度报告分类细项",
             "rows": [
                 {"kind": "cpi_urban_yoy", "name": "其中：城市", "unit": "%"},
                 {"kind": "cpi_rural_yoy", "name": "农村", "unit": "%"},
                 {"kind": "cpi_food_yoy", "name": "其中：食品", "unit": "%"},
                 {"kind": "cpi_nonfood_yoy", "name": "非食品", "unit": "%"},
                 {"kind": "cpi_goods_yoy", "name": "其中：消费品", "unit": "%"},
                 {"kind": "cpi_services_yoy", "name": "服务", "unit": "%"},
                 {"kind": "cpi_core_yoy", "name": "其中：不包括食品和能源", "unit": "%"},
                 {"kind": "cpi_foodtobacco_yoy", "name": "一、食品烟酒及在外餐饮", "unit": "%"},
                 {"kind": "cpi_vegetable_yoy", "name": "鲜菜", "unit": "%"},
                 {"kind": "cpi_meat_yoy", "name": "畜肉类", "unit": "%"},
                 {"kind": "cpi_pork_yoy", "name": "其中：猪肉", "unit": "%"},
                 {"kind": "cpi_egg_yoy", "name": "蛋类", "unit": "%"},
                 {"kind": "cpi_fruit_yoy", "name": "鲜果", "unit": "%"},
                 {"kind": "cpi_clothing_yoy", "name": "二、衣着", "unit": "%"},
                 {"kind": "cpi_residence_yoy", "name": "三、居住", "unit": "%"},
                 {"kind": "cpi_daily_yoy", "name": "四、生活用品及服务", "unit": "%"},
                 {"kind": "cpi_transport_yoy", "name": "五、交通通信", "unit": "%"},
                 {"kind": "cpi_education_yoy", "name": "六、教育文化娱乐", "unit": "%"},
                 {"kind": "cpi_healthcare_yoy", "name": "七、医疗保健", "unit": "%"},
                 {"kind": "cpi_other_yoy", "name": "八、其他用品及服务", "unit": "%"},
             ]},
        ],
    },
    {
        "id": "ppi",
        "sector": "inflation",
        "name": "工业生产者出厂价格指数PPI",
        "unit": "%",
        "main_kind": "yoy",
        "release": "next_month_9",
        "official": "国家统计局·工业生产者出厂价格指数（月度报告）",
        "sources": [
            {"type": "nbs", "dbcode": "hgyd", "matches": [
                {"kind": "yoy", "include": ["工业生产者出厂价格指数", "上年同月=100"],
                 "transform": "minus100"},
            ]},
            {"type": "eastmoney", "report_name": "RPT_ECONOMY_PPI",
             "fields": {"yoy": "BASE_SAME"}},
        ],
        # 分类细项：生产资料/生活资料、购进价格与重点行业（PPI 月度报告表格）
        "detail_sources": [
            {"type": "statsweb_news", "news": "ppi",
             "source_label": "国家统计局官网·PPI月度报告分类细项",
             "rows": [
                 {"kind": "ppi_means_yoy", "name": "生产资料", "unit": "%"},
                 {"kind": "ppi_mining_yoy", "name": "采掘", "unit": "%"},
                 {"kind": "ppi_rawmat_yoy", "name": "原材料", "unit": "%"},
                 {"kind": "ppi_processing_yoy", "name": "加工", "unit": "%"},
                 {"kind": "ppi_life_yoy", "name": "生活资料", "unit": "%"},
                 {"kind": "ppi_life_food_yoy", "name": "食品", "unit": "%"},
                 {"kind": "ppi_life_clothing_yoy", "name": "衣着", "unit": "%"},
                 {"kind": "ppi_life_daily_yoy", "name": "一般日用品", "unit": "%"},
                 {"kind": "ppi_life_durable_yoy", "name": "耐用消费品", "unit": "%"},
                 {"kind": "ppi_buy_yoy", "name": "二、工业生产者购进价格", "unit": "%"},
                 {"kind": "ppi_coal_yoy", "name": "煤炭开采和洗选业", "unit": "%"},
                 {"kind": "ppi_oilgas_yoy", "name": "石油和天然气开采业", "unit": "%"},
                 {"kind": "ppi_oilprocess_yoy", "name": "石油、煤炭及其他燃料加工业", "unit": "%"},
                 {"kind": "ppi_chemical_yoy", "name": "化学原料和化学制品制造业", "unit": "%"},
                 {"kind": "ppi_ferrous_yoy", "name": "黑色金属冶炼和压延加工业", "unit": "%"},
                 {"kind": "ppi_nonferrous_yoy", "name": "有色金属冶炼和压延加工业", "unit": "%"},
                 {"kind": "ppi_electronics_yoy", "name": "计算机、通信和其他电子设备制造业", "unit": "%"},
                 {"kind": "ppi_auto_yoy", "name": "汽车制造业", "unit": "%"},
                 {"kind": "ppi_power_yoy", "name": "电力、热力生产和供应业", "unit": "%"},
             ]},
        ],
    },
    {
        "id": "retail_sales",
        "sector": "consumption",
        "name": "社会消费品零售总额",
        "unit": "亿元",
        "main_kind": "yoy",
        "release": "next_month_15",
        "official": "国家统计局·社会消费品零售总额（月度报告）",
        "sources": [
            {"type": "nbs", "dbcode": "hgyd", "matches": [
                {"kind": "value", "include": ["社会消费品零售总额", "当期值"]},
                {"kind": "yoy", "include": ["社会消费品零售总额", "同比增长"]},
            ]},
            {"type": "eastmoney", "report_name": "RPT_ECONOMY_TOTAL_RETAIL",
             "fields": {"value": "RETAIL_TOTAL", "yoy": "RETAIL_TOTAL_SAME"}},
        ],
        # 分类细项：城乡、商品/餐饮与限额以上重点品类（社零月度报告表格）
        "detail_sources": [
            {"type": "statsweb_news", "news": "retail",
             "source_label": "国家统计局官网·社零月度报告分类细项",
             "rows": [
                 {"kind": "retail_goods_value", "name": "商品零售额", "col": "value", "unit": "亿元"},
                 {"kind": "retail_goods_yoy", "name": "商品零售额", "unit": "%"},
                 {"kind": "retail_catering_value", "name": "餐饮收入", "col": "value", "unit": "亿元"},
                 {"kind": "retail_catering_yoy", "name": "餐饮收入", "unit": "%"},
                 {"kind": "retail_urban_yoy", "name": "城镇", "unit": "%"},
                 {"kind": "retail_rural_yoy", "name": "乡村", "unit": "%"},
                 {"kind": "retail_auto_yoy", "name": "汽车类", "unit": "%"},
                 {"kind": "retail_food_yoy", "name": "其中：粮油、食品类", "unit": "%"},
                 {"kind": "retail_oil_yoy", "name": "石油及制品类", "unit": "%"},
             ]},
        ],
    },
    {
        "id": "house_70",
        "sector": "housing",
        "name": "70城新建商品住宅价格指数",
        "unit": "指数",
        "main_kind": "rise_count_mom",
        "release": "next_month_15",
        "official": "国家统计局·70个大中城市商品住宅销售价格变动情况（月度报告）",
        "sources": [
            {"type": "statsweb_house"},
            {"type": "nbs_csyd"},
        ],
    },
    {
        "id": "ind_va",
        "sector": "industry",
        "name": "规模以上工业增加值",
        "unit": "%",
        "main_kind": "yoy",
        "release": "next_month_15",
        "official": "国家统计局·规模以上工业生产月度报告",
        "sources": [
            {"type": "nbs", "dbcode": "hgyd", "matches": [
                {"kind": "yoy", "include": ["工业增加值", "同比增长"],
                 "exclude": ["累计"]},
            ]},
            {"type": "eastmoney", "report_name": "RPT_ECONOMY_INDUS_GROW",
             "fields": {"yoy": "BASE_SAME"}},
        ],
        # 分类细项：三大门类、高技术制造业与分经济类型（工业增加值月度报告）
        "detail_sources": [
            {"type": "statsweb_news", "news": "indva",
             "source_label": "国家统计局官网·工业增加值月度报告分类细项",
             "rows": [
                 {"kind": "indva_mining_yoy", "name": "采矿业", "unit": "%"},
                 {"kind": "indva_manufacturing_yoy", "name": "制造业", "unit": "%"},
                 {"kind": "indva_utilities_yoy", "name": "电力、热力、燃气及水生产和供应业", "unit": "%"},
                 {"kind": "indva_hightech_yoy", "name": "其中：高技术制造业", "unit": "%"},
                 {"kind": "indva_state_yoy", "name": "其中：国有控股企业", "unit": "%"},
                 {"kind": "indva_share_yoy", "name": "其中：股份制企业", "unit": "%"},
                 {"kind": "indva_foreign_yoy", "name": "外商及港澳台投资企业", "unit": "%"},
                 {"kind": "indva_private_yoy", "name": "其中：私营企业", "unit": "%"},
             ],
             "sentences": [
                 {"kind": "indva_mom", "unit": "%",
                  "pattern": r"规模以上工业增加值比上月增长\s*(-?[\d\.]+)\s*%"},
             ]},
        ],
    },
    {
        "id": "ind_profit",
        "sector": "industry",
        "name": "工业企业利润总额",
        "unit": "亿元",
        "main_kind": "accum",
        "release": "next_month_27",
        "official": "国家统计局·全国规模以上工业企业利润（月度报告）",
        "sources": [
            {"type": "statsweb_profit"},
            {"type": "nbs", "dbcode": "hgyd", "matches": [
                {"kind": "accum", "include": ["利润总额", "累计值"]},
                {"kind": "accum_yoy", "include": ["利润总额", "累计增长"]},
            ]},
        ],
    },
    {
        "id": "trade_total",
        "sector": "trade",
        "name": "进出口总值",
        "unit": "亿美元",
        "main_kind": "value",
        "release": "next_month_7",
        "official": "海关总署·全国进出口总值（统计快讯）",
        "sources": [
            {"type": "customs_trade"},
            {"type": "eastmoney", "report_name": "RPT_ECONOMY_CUSTOMS", "fields": [
                {"kind": "value", "add": ["EXIT_BASE", "IMPORT_BASE"], "scale": 0.00001,
                 "unit": "亿美元"},
                {"kind": "export", "field": "EXIT_BASE", "scale": 0.00001,
                 "unit": "亿美元"},
                {"kind": "import", "field": "IMPORT_BASE", "scale": 0.00001,
                 "unit": "亿美元"},
                {"kind": "export_yoy", "field": "EXIT_BASE_SAME"},
                {"kind": "import_yoy", "field": "IMPORT_BASE_SAME"},
                # 贸易细分：环比、累计额与累计同比（分贸易方式海关官网当前不可达，未获取）
                {"kind": "export_mom", "field": "EXIT_BASE_SEQUENTIAL"},
                {"kind": "import_mom", "field": "IMPORT_BASE_SEQUENTIAL"},
                {"kind": "export_accum", "field": "EXIT_ACCUMULATE", "scale": 0.00001,
                 "unit": "亿美元"},
                {"kind": "import_accum", "field": "IMPORT_ACCUMULATE", "scale": 0.00001,
                 "unit": "亿美元"},
                {"kind": "export_accum_yoy", "field": "EXIT_ACCUMULATE_SAME"},
                {"kind": "import_accum_yoy", "field": "IMPORT_ACCUMULATE_SAME"},
            ]},
        ],
    },
    {
        "id": "export_price_index",
        "sector": "trade",
        "name": "出口价格指数",
        "unit": "上年同月=100",
        "main_kind": "value",
        "release": "next_month_20",
        "official": "海关总署·中国外贸指数（出口价格指数）",
        "missing_note": "当前网络环境无法访问海关总署外贸指数页面，已标注缺失",
        "sources": [
            {"type": "customs_index"},
        ],
    },
]

# 红绿灯规则：green/yellow 为区间列表 [(low, high)]，None 表示无界；其余为红。
# 阈值为经验性设定，仅作视觉提示，以 AI 解读为准。
LIGHT_RULES: Dict[Any, Dict[str, List[Any]]] = {
    ("pmi", "value"): {"green": [(50.3, None)], "yellow": [(49.7, 50.3)]},
    ("cpi", "yoy"): {"green": [(0.5, 2.5)], "yellow": [(0.0, 0.5), (2.5, 3.5)]},
    ("ppi", "yoy"): {"green": [(0.5, None)], "yellow": [(-1.0, 0.5)]},
    ("retail_sales", "yoy"): {"green": [(5.0, None)], "yellow": [(2.0, 5.0)]},
    ("ind_va", "yoy"): {"green": [(5.5, None)], "yellow": [(3.5, 5.5)]},
    ("ind_profit", "accum_yoy"): {"green": [(0.0, None)], "yellow": [(-5.0, 0.0)]},
    ("trade_total", "export_yoy"): {"green": [(5.0, None)], "yellow": [(0.0, 5.0)]},
    ("house_70", "rise_count_mom"): {"green": [(40.0, None)], "yellow": [(25.0, 40.0)]},
    ("unemp_rate", "unemp_rate"): {"green": [(None, 5.0)], "yellow": [(5.0, 5.6)]},
}


def indicator_by_id(indicator_id: str) -> Optional[Dict[str, Any]]:
    for item in INDICATORS:
        if item["id"] == indicator_id:
            return item
    return None


def sector_indicators(sector_id: str) -> List[Dict[str, Any]]:
    return [item for item in INDICATORS if item["sector"] == sector_id]


def light_for(indicator_id: str, kind: str, value: Optional[float]) -> Optional[str]:
    rule = LIGHT_RULES.get((indicator_id, kind))
    if not rule or value is None:
        return None
    for color in ("green", "yellow"):
        for low, high in rule.get(color, []):
            if (low is None or value >= low) and (high is None or value < high):
                return color
    return "red"


def next_release_date(latest_period: str, release_key: str) -> str:
    """最新数据期之后的下一次发布日（即次月数据的例行发布日）。"""
    rule = RELEASE_RULES.get(release_key, {})
    day = rule.get("day")
    year, month = int(latest_period[:4]), int(latest_period[5:7])
    if month == 12:
        year, month = year + 1, 1
    else:
        month += 1
    if day is None:
        day = calendar.monthrange(year, month)[1]
    return "{:04d}-{:02d}-{:02d}".format(year, month, day)


def release_note(release_key: str) -> str:
    return str(RELEASE_RULES.get(release_key, {}).get("note", ""))
