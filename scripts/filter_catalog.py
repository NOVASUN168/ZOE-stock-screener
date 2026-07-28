# -*- coding: utf-8 -*-
"""
stock-screener · 综合筛选条件目录（数据驱动筛选的“单一事实来源”）
对齐 i问财 / 同花顺式多因子条件，覆盖六大分组：财务/估值/资金/技术/题材/风险。
每个条目映射 stocks 表的真实列（field=列名）或计算字段（field=computed:xxx，
暂无底层数据时由 screen_engine 填 None，作为未来扩展占位）。
- is_premium=1 表示付费墙功能（云端校验订阅后开放）。
- 硬过滤类（风险分组）统一用 eq 0 表达“排除”。
依赖：仅 sqlite3（Python 标准库）。
"""
import sqlite3

# 六大分组常量
GRP_FINANCE = "财务"
GRP_VALUATION = "估值"
GRP_CAPITAL = "资金"
GRP_TECH = "技术"
GRP_THEME = "题材"
GRP_RISK = "风险"

# 算子：gt/lt/between/eq/in/neq/like
# ftype：numeric/enum/bool/text

CATALOG = [
    # ---------------- 财务 ----------------
    {"key": "roe", "name": "ROE(净资产收益率)", "grp": GRP_FINANCE, "ftype": "numeric",
     "operator": "gt", "unit": "%", "description": "净资产收益率，越高越好", "field": "roe",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "roa", "name": "ROA(总资产收益率)", "grp": GRP_FINANCE, "ftype": "numeric",
     "operator": "gt", "unit": "%", "description": "总资产收益率", "field": "roa",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "rev_growth_years", "name": "营收增长年数", "grp": GRP_FINANCE, "ftype": "enum",
     "operator": "eq", "unit": "年", "description": "连续营收正增长年数（1/2/3）", "field": "rev_growth_years",
     "is_premium": 0, "default_visible": 1, "enum_values": ["3", "2", "1"]},
    {"key": "netprofit_growth_years", "name": "净利增长年数", "grp": GRP_FINANCE, "ftype": "enum",
     "operator": "eq", "unit": "年", "description": "连续净利润正增长年数（1/2/3）", "field": "netprofit_growth_years",
     "is_premium": 0, "default_visible": 1, "enum_values": ["3", "2", "1"]},
    {"key": "fcf_positive", "name": "自由现金流为正", "grp": GRP_FINANCE, "ftype": "bool",
     "operator": "eq", "unit": "", "description": "自由现金流转正（1=是）", "field": "fcf_positive",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "debt_ratio", "name": "资产负债率", "grp": GRP_FINANCE, "ftype": "numeric",
     "operator": "lt", "unit": "%", "description": "资产负债率越低越好", "field": "debt_ratio",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "gross_margin", "name": "毛利率", "grp": GRP_FINANCE, "ftype": "numeric",
     "operator": "gt", "unit": "%", "description": "销售毛利率（暂未采集，占位）", "field": "computed:gross_margin",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "rev_cagr", "name": "营收复合增速", "grp": GRP_FINANCE, "ftype": "numeric",
     "operator": "gt", "unit": "%", "description": "近N年营收复合增速（占位）", "field": "computed:rev_cagr",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "netprofit_cagr", "name": "净利复合增速", "grp": GRP_FINANCE, "ftype": "numeric",
     "operator": "gt", "unit": "%", "description": "近N年净利润复合增速（占位）", "field": "computed:netprofit_cagr",
     "is_premium": 0, "default_visible": 1, "enum_values": None},

    # ---------------- 估值 ----------------
    {"key": "pe", "name": "PE(市盈率)", "grp": GRP_VALUATION, "ftype": "numeric",
     "operator": "lt", "unit": "倍", "description": "市盈率，越低越便宜", "field": "pe",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "pe_percentile", "name": "PE历史分位", "grp": GRP_VALUATION, "ftype": "numeric",
     "operator": "lt", "unit": "%", "description": "PE所处历史分位（占位）", "field": "computed:pe_percentile",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "pb", "name": "PB(市净率)", "grp": GRP_VALUATION, "ftype": "numeric",
     "operator": "lt", "unit": "倍", "description": "市净率", "field": "pb",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "peg", "name": "PEG", "grp": GRP_VALUATION, "ftype": "numeric",
     "operator": "lt", "unit": "倍", "description": "PEG，<1 高估值的成长性更优", "field": "peg",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "ps", "name": "PS(市销率)", "grp": GRP_VALUATION, "ftype": "numeric",
     "operator": "lt", "unit": "倍", "description": "市销率（占位）", "field": "computed:ps",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "ev_ebitda", "name": "EV/EBITDA", "grp": GRP_VALUATION, "ftype": "numeric",
     "operator": "lt", "unit": "倍", "description": "企业价值倍数", "field": "ev_ebitda",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "dividend_yield", "name": "股息率", "grp": GRP_VALUATION, "ftype": "numeric",
     "operator": "gt", "unit": "%", "description": "股息率（占位）", "field": "computed:dividend_yield",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "safety_margin", "name": "安全边际", "grp": GRP_VALUATION, "ftype": "numeric",
     "operator": "gt", "unit": "%", "description": "估算安全边际", "field": "safety_margin",
     "is_premium": 0, "default_visible": 1, "enum_values": None},

    # ---------------- 资金 ----------------
    {"key": "net_capital_flow", "name": "主力净流入20日", "grp": GRP_CAPITAL, "ftype": "numeric",
     "operator": "gt", "unit": "万元", "description": "20日主力资金净流入合计（万元，可负）", "field": "net_capital_flow",
     "is_premium": 1, "default_visible": 1, "enum_values": None},
    {"key": "main_inflow_20d", "name": "主力资金净流入20日", "grp": GRP_CAPITAL, "ftype": "numeric",
     "operator": "gt", "unit": "万元", "description": "20日主力资金净流入额", "field": "main_inflow_20d",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "main_outflow_20d", "name": "主力资金净流出20日", "grp": GRP_CAPITAL, "ftype": "numeric",
     "operator": "lt", "unit": "万元", "description": "20日主力资金净流出额（越低越好）", "field": "main_outflow_20d",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "northbound", "name": "北向持仓变化", "grp": GRP_CAPITAL, "ftype": "enum",
     "operator": "eq", "unit": "", "description": "北向资金持仓变化", "field": "northbound",
     "is_premium": 0, "default_visible": 1, "enum_values": ["增持", "持平", "减持"]},
    {"key": "institution_change", "name": "机构增仓", "grp": GRP_CAPITAL, "ftype": "enum",
     "operator": "eq", "unit": "", "description": "机构持仓动向", "field": "institution_change",
     "is_premium": 0, "default_visible": 1, "enum_values": ["增仓", "减仓", "持平"]},
    {"key": "margin_change", "name": "融资余额变化", "grp": GRP_CAPITAL, "ftype": "numeric",
     "operator": "gt", "unit": "%", "description": "融资余额环比变化（占位）", "field": "computed:margin_change",
     "is_premium": 1, "default_visible": 1, "enum_values": None},
    {"key": "hotmoney_ratio", "name": "游资参与度", "grp": GRP_CAPITAL, "ftype": "numeric",
     "operator": "lt", "unit": "%", "description": "游资参与度占比（排除用，越低越好）", "field": "hotmoney_ratio",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "hotmoney_flag", "name": "游资主导标记", "grp": GRP_CAPITAL, "ftype": "bool",
     "operator": "eq", "unit": "", "description": "1=游资主导（排除用，取 0）", "field": "hotmoney_flag",
     "is_premium": 0, "default_visible": 1, "enum_values": None},

    # ---------------- 技术（保留展示，不参与评分） ----------------
    {"key": "ma_trend", "name": "均线多头", "grp": GRP_TECH, "ftype": "enum",
     "operator": "eq", "unit": "", "description": "均线排列形态", "field": "ma_trend",
     "is_premium": 0, "default_visible": 1, "enum_values": ["多头", "空头", "缠绕"]},
    {"key": "macd", "name": "MACD", "grp": GRP_TECH, "ftype": "enum",
     "operator": "eq", "unit": "", "description": "MACD 金叉/死叉", "field": "macd",
     "is_premium": 0, "default_visible": 1, "enum_values": ["金叉", "死叉", "持平"]},
    {"key": "kdj", "name": "KDJ", "grp": GRP_TECH, "ftype": "enum",
     "operator": "eq", "unit": "", "description": "KDJ 状态", "field": "kdj",
     "is_premium": 0, "default_visible": 1, "enum_values": ["金叉", "死叉", "超买", "超卖"]},
    {"key": "rsi", "name": "RSI区间", "grp": GRP_TECH, "ftype": "numeric",
     "operator": "between", "unit": "", "description": "RSI 区间（between value~value2）", "field": "rsi",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "volume", "name": "量能", "grp": GRP_TECH, "ftype": "enum",
     "operator": "eq", "unit": "", "description": "成交量能状态", "field": "volume",
     "is_premium": 0, "default_visible": 1, "enum_values": ["温和放大", "放大", "萎缩", "持平"]},
    {"key": "volatility", "name": "波动率", "grp": GRP_TECH, "ftype": "enum",
     "operator": "eq", "unit": "", "description": "波动等级", "field": "volatility",
     "is_premium": 0, "default_visible": 1, "enum_values": ["低", "中", "高"]},
    {"key": "turnover_rate", "name": "换手率", "grp": GRP_TECH, "ftype": "numeric",
     "operator": "lt", "unit": "%", "description": "换手率（占位）", "field": "computed:turnover_rate",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "new_high", "name": "股价新高", "grp": GRP_TECH, "ftype": "enum",
     "operator": "eq", "unit": "", "description": "是否创阶段新高（占位）", "field": "computed:new_high",
     "is_premium": 1, "default_visible": 1, "enum_values": ["是", "否"]},

    # ---------------- 题材 ----------------
    {"key": "industry", "name": "行业", "grp": GRP_THEME, "ftype": "text",
     "operator": "like", "unit": "", "description": "所属行业（模糊匹配）", "field": "industry",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "board", "name": "板块", "grp": GRP_THEME, "ftype": "enum",
     "operator": "eq", "unit": "", "description": "上市板块", "field": "board",
     "is_premium": 0, "default_visible": 1, "enum_values": ["主板", "创业板", "科创板", "北交所", "H股", "红筹", "民营港股"]},
    {"key": "market", "name": "市场", "grp": GRP_THEME, "ftype": "enum",
     "operator": "eq", "unit": "", "description": "交易市场", "field": "market",
     "is_premium": 0, "default_visible": 1, "enum_values": ["A股", "港股", "A+H"]},
    {"key": "ai_category", "name": "AI分类", "grp": GRP_THEME, "ftype": "enum",
     "operator": "eq", "unit": "", "description": "AI 产业四分类", "field": "ai_category",
     "is_premium": 0, "default_visible": 1, "enum_values": ["核心基础", "模型平台", "AI革命", "AI医药"]},
    {"key": "concept_tags", "name": "概念标签", "grp": GRP_THEME, "ftype": "text",
     "operator": "like", "unit": "", "description": "概念标签模糊匹配（占位）", "field": "computed:concept_tags",
     "is_premium": 0, "default_visible": 1, "enum_values": None},

    # ---------------- 风险（硬过滤，统一 eq 0 表达排除） ----------------
    {"key": "st_exclude", "name": "排除ST", "grp": GRP_RISK, "ftype": "bool",
     "operator": "eq", "unit": "", "description": "排除 ST 股（取 0）", "field": "st_flag",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "delisting_exclude", "name": "排除退市风险", "grp": GRP_RISK, "ftype": "bool",
     "operator": "eq", "unit": "", "description": "排除退市风险（取 0）", "field": "delisting_risk",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "fraud_exclude", "name": "排除造假嫌疑", "grp": GRP_RISK, "ftype": "bool",
     "operator": "eq", "unit": "", "description": "排除财务造假嫌疑（取 0）", "field": "fraud_flag",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "consecutive_loss_exclude", "name": "排除连续亏损", "grp": GRP_RISK, "ftype": "bool",
     "operator": "eq", "unit": "", "description": "排除连续亏损（取 0）", "field": "consecutive_loss",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "litigation_exclude", "name": "排除重大诉讼", "grp": GRP_RISK, "ftype": "bool",
     "operator": "eq", "unit": "", "description": "排除重大诉讼（取 0）", "field": "litigation",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "high_pledge_exclude", "name": "排除高质押", "grp": GRP_RISK, "ftype": "bool",
     "operator": "eq", "unit": "", "description": "排除高质押（取 0）", "field": "high_pledge",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "goodwill_ratio", "name": "商誉占比", "grp": GRP_RISK, "ftype": "numeric",
     "operator": "lt", "unit": "%", "description": "商誉占净资产比（越低越好）", "field": "goodwill_ratio",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "major_holder_reduction_exclude", "name": "排除大股东减持", "grp": GRP_RISK, "ftype": "bool",
     "operator": "eq", "unit": "", "description": "排除大股东减持（取 0）", "field": "major_holder_reduction",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
    {"key": "hotmoney_exclude", "name": "排除游资主导", "grp": GRP_RISK, "ftype": "bool",
     "operator": "eq", "unit": "", "description": "排除游资主导个股（取 0）", "field": "hotmoney_flag",
     "is_premium": 0, "default_visible": 1, "enum_values": None},
]


def get_catalog() -> list:
    """返回完整条件目录（list[dict]），供前端渲染筛选面板与后端解析。"""
    return CATALOG


def seed_catalog(conn):
    """将 CATALOG 写入 filter_catalog 表；key 已存在则跳过（INSERT OR IGNORE）。"""
    n = 0
    for e in CATALOG:
        cur = conn.execute(
            """INSERT OR IGNORE INTO filter_catalog
               (key, name, grp, ftype, operator, unit, description, is_premium, default_visible)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (e["key"], e["name"], e["grp"], e["ftype"], e["operator"], e["unit"],
             e["description"], e.get("is_premium", 0), e.get("default_visible", 1)))
        if cur.rowcount:
            n += 1
    conn.commit()
    return n


# 供 screen_engine 快速按 key 取条目
_CATALOG_MAP = {e["key"]: e for e in CATALOG}

def get_entry(key: str) -> dict:
    return _CATALOG_MAP.get(key)


if __name__ == "__main__":
    print(f"catalog entries: {len(CATALOG)}")
    premiums = [e["key"] for e in CATALOG if e.get("is_premium")]
    print("premium keys:", premiums)
