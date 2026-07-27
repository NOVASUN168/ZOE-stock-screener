# -*- coding: utf-8 -*-
"""
stock-screener · 数据层（V2.0 AI产业聚焦版）
基于 Python 标准库 sqlite3，无外部依赖。
负责建表、增删改查（CRUD）、风险标记。
字段对应「V2.0 多因子量化评分模型」的原始输入与计算产物。
V2.0 新增：market/board/ai_category/ai_driven/research_signals/main_force_trend
V2.0 移除：target_price/buy_point/stop_loss/take_profit/expected_return
"""
import sqlite3
import os
import json

DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "screener.db")

# 全字段顺序：原始输入 + 计算产物（必须与 schema.sql 保持一致）
FIELDS = [
    # 基础
    "code", "name", "industry", "price",
    # 基本面 35%
    "roe", "roa", "rev_growth_years", "netprofit_growth_years", "fcf_positive",
    "debt_ratio", "sector_type",
    # 估值 20%
    "pe", "pe_industry_avg", "pb", "peg", "ev_ebitda", "safety_margin",
    # 成长 25%
    "rd_increase", "mkt_share_growth", "industry_space", "moat", "profit_forecast_3y",
    # 技术（保留列，不参与评分）
    "ma_trend", "macd", "kdj", "rsi", "volume", "volatility",
    # 资金（主力长期趋势）
    "main_fund_flow", "northbound", "institution_change", "main_force_trend",
    # 范围与 AI 分类
    "market", "board", "ai_category", "ai_driven", "research_signals",
    # 风险 5%（软因子）
    "financial_risk", "litigation", "pledge_ratio", "regulatory_penalty", "goodwill_ratio",
    # 硬过滤（一票否决）
    "st_flag", "delisting_risk", "fraud_flag", "consecutive_loss",
    "major_holder_reduction", "high_pledge",
    # 计算产物（写回）
    "total_score", "rating", "recommend_index", "risk_flags",
    "reasonable_valuation", "suggested_position", "expected_hold",
    "advantages", "risks_text", "recommend_reasons",
    "core_competence", "long_term_thesis",
]

# 数值型字段（其余视为文本/布尔）
NUMERIC = {
    "price", "roe", "roa", "rev_growth_years", "netprofit_growth_years",
    "debt_ratio", "pe", "pe_industry_avg", "pb", "peg", "ev_ebitda",
    "safety_margin", "profit_forecast_3y", "rsi",
    "pledge_ratio", "goodwill_ratio", "total_score",
}

# 布尔型（0/1）
BOOL = {
    "fcf_positive", "rd_increase", "mkt_share_growth", "financial_risk",
    "litigation", "regulatory_penalty", "st_flag", "delisting_risk",
    "fraud_flag", "consecutive_loss", "major_holder_reduction", "high_pledge",
    "ai_driven",
}


def connect(db_path=None):
    db_path = db_path or DEFAULT_DB
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _init_schema(conn)
    return conn


def _init_schema(conn):
    cols = ["id INTEGER PRIMARY KEY AUTOINCREMENT", "updated_at TEXT"]
    for f in FIELDS:
        if f in NUMERIC:
            cols.append(f"{f} REAL")
        elif f in BOOL:
            cols.append(f"{f} INTEGER DEFAULT 0")
        else:
            cols.append(f"{f} TEXT")
    conn.execute(f"CREATE TABLE IF NOT EXISTS stocks ({', '.join(cols)})")
    # 组合表（稳健/成长/激进）
    conn.execute("""CREATE TABLE IF NOT EXISTS portfolios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ptype TEXT,            -- robust / growth / aggressive
        name TEXT,
        stock_ids TEXT,        -- JSON list of stock id
        alloc TEXT,            -- JSON dict id->pct
        note TEXT,
        created_at TEXT
    )""")
    conn.commit()


def _coerce(row: dict):
    """把输入 dict 规范化为可写入的值。"""
    out = {}
    for f in FIELDS:
        v = row.get(f)
        if f in NUMERIC:
            try:
                out[f] = float(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                out[f] = None
        elif f in BOOL:
            out[f] = 1 if str(v) in ("1", "true", "True", "是", "True") else (0 if v in (0, "0", "false", "False", "否", None, "") else (1 if v else 0))
        else:
            out[f] = "" if v is None else str(v)
    return out


def create(conn, data: dict) -> int:
    d = _coerce(data)
    keys = FIELDS
    placeholders = ", ".join(["?"] * len(keys))
    sql = f"INSERT INTO stocks ({', '.join(keys)}, updated_at) VALUES ({placeholders}, datetime('now','localtime'))"
    cur = conn.execute(sql, [d[k] for k in keys])
    conn.commit()
    return cur.lastrowid


def update(conn, sid: int, data: dict):
    d = _coerce(data)
    keys = [k for k in FIELDS if k in data]  # 仅更新被提供的字段（patch 语义）
    if not keys:
        return
    sets = ", ".join([f"{k}=?" for k in keys]) + ", updated_at=datetime('now','localtime')"
    conn.execute(f"UPDATE stocks SET {sets} WHERE id=?", [d[k] for k in keys] + [sid])
    conn.commit()


COMPUTED_KEYS = [
    "total_score", "rating", "recommend_index", "risk_flags",
    "reasonable_valuation", "suggested_position", "expected_hold",
    "advantages", "risks_text", "recommend_reasons",
    "core_competence", "long_term_thesis",
]
def patch_computed(conn, sid: int, computed: dict):
    """仅回写评分计算字段，绝不触碰录入输入字段。"""
    keys = [k for k in COMPUTED_KEYS if k in computed]
    sets = ", ".join([f"{k}=?" for k in keys]) + ", updated_at=datetime('now','localtime')"
    conn.execute(f"UPDATE stocks SET {sets} WHERE id=?", [computed[k] for k in keys] + [sid])
    conn.commit()


def delete(conn, sid: int):
    conn.execute("DELETE FROM stocks WHERE id=?", [sid])
    conn.commit()


def get(conn, sid: int) -> dict:
    row = conn.execute("SELECT * FROM stocks WHERE id=?", [sid]).fetchone()
    return dict(row) if row else None


def list_all(conn, industry=None, style=None, min_score=None, ai_category=None, market=None) -> list:
    sql = "SELECT * FROM stocks WHERE 1=1"
    args = []
    if industry:
        sql += " AND industry LIKE ?"; args.append(f"%{industry}%")
    if ai_category:
        sql += " AND ai_category = ?"; args.append(ai_category)
    if market:
        sql += " AND market = ?"; args.append(market)
    if min_score is not None:
        sql += " AND total_score >= ?"; args.append(min_score)
    sql += " ORDER BY total_score DESC"
    rows = conn.execute(sql, args).fetchall()
    result = [dict(r) for r in rows]
    if style:
        # 风格筛选在 scoring 模块做（依赖评分逻辑），这里只做基础过滤
        from scoring import screen_by_style
        result = screen_by_style(result, style)
    return result


def count(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]


def save_portfolio(conn, ptype, name, stock_ids, alloc, note=""):
    conn.execute(
        "INSERT INTO portfolios (ptype, name, stock_ids, alloc, note, created_at) VALUES (?,?,?,?,?,datetime('now','localtime'))",
        (ptype, name, json.dumps(stock_ids, ensure_ascii=False), json.dumps(alloc, ensure_ascii=False), note))
    conn.commit()


if __name__ == "__main__":
    c = connect()
    print("DB ready at", DEFAULT_DB, "| rows:", count(c))
    c.close()
