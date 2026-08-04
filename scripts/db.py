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
    # 资金流/游资（V2.1 新增）
    "main_inflow_20d", "main_outflow_20d", "net_capital_flow", "hotmoney_ratio", "hotmoney_flag",
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
    "main_inflow_20d", "main_outflow_20d", "net_capital_flow", "hotmoney_ratio",
}

# 布尔型（0/1）
BOOL = {
    "fcf_positive", "rd_increase", "mkt_share_growth", "financial_risk",
    "litigation", "regulatory_penalty", "st_flag", "delisting_risk",
    "fraud_flag", "consecutive_loss", "major_holder_reduction", "high_pledge",
    "ai_driven", "hotmoney_flag",
}


def connect(db_path=None):
    db_path = db_path or DEFAULT_DB
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _init_schema(conn)
    migrate_stocks(conn)
    return conn


def migrate_stocks(conn):
    """向后兼容：为已存在的 stocks 表补齐缺失列（ALTER TABLE ADD COLUMN）。
    新列依据 FIELDS/NUMERIC/BOOL 推断类型；BOOL 给 DEFAULT 0，其余允许 NULL。"""
    cur = conn.execute("PRAGMA table_info(stocks)").fetchall()
    existing = {r[1] for r in cur}
    for f in FIELDS:
        if f in existing:
            continue
        if f in NUMERIC:
            conn.execute(f"ALTER TABLE stocks ADD COLUMN {f} REAL")
        elif f in BOOL:
            conn.execute(f"ALTER TABLE stocks ADD COLUMN {f} INTEGER DEFAULT 0")
        else:
            conn.execute(f"ALTER TABLE stocks ADD COLUMN {f} TEXT")
    conn.commit()


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
    # V2.1 协作 / 授权 / 数据驱动筛选 建表
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT,
        display_name TEXT,
        role TEXT DEFAULT 'viewer',
        status TEXT DEFAULT 'active',
        license_key TEXT,
        sub_tier TEXT DEFAULT 'free',
        sub_expiry TEXT,
        created_at TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS filter_catalog (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL,
        name TEXT, grp TEXT, ftype TEXT, operator TEXT, unit TEXT,
        description TEXT, is_premium INTEGER DEFAULT 0, default_visible INTEGER DEFAULT 1
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS filter_schemes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, owner_id INTEGER, is_pinned INTEGER DEFAULT 0,
        is_shared INTEGER DEFAULT 1, description TEXT, created_at TEXT, updated_at TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS scheme_conditions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scheme_id INTEGER, catalog_key TEXT, operator TEXT,
        value TEXT, value2 TEXT, sort_order INTEGER DEFAULT 0, enabled INTEGER DEFAULT 1
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS scheme_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scheme_id INTEGER, version_no INTEGER, snapshot_json TEXT,
        created_by INTEGER, created_at TEXT, note TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS operation_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, action TEXT, target_type TEXT, target_id INTEGER,
        detail TEXT, created_at TEXT
    )""")
    # 全局配置（key-value 存储；auth_secret 等敏感值由运行时写入，不进种子）
    conn.execute("""CREATE TABLE IF NOT EXISTS system_config (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT
    )""")
    for idx in (
        "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
        "CREATE INDEX IF NOT EXISTS idx_filter_catalog_key ON filter_catalog(key)",
        "CREATE INDEX IF NOT EXISTS idx_filter_schemes_owner ON filter_schemes(owner_id)",
        "CREATE INDEX IF NOT EXISTS idx_scheme_conditions_scheme ON scheme_conditions(scheme_id)",
        "CREATE INDEX IF NOT EXISTS idx_scheme_versions_scheme ON scheme_versions(scheme_id)",
        "CREATE INDEX IF NOT EXISTS idx_operation_logs_user ON operation_logs(user_id)",
    ):
        conn.execute(idx)
    conn.commit()


# ---------- 密码哈希（hashlib 加盐 sha256，零依赖） ----------
import hashlib as _hashlib
import os as _os

def hash_password(password: str, salt: str = None) -> str:
    salt = salt or _os.urandom(16).hex()
    h = _hashlib.sha256((salt + str(password)).encode("utf-8")).hexdigest()
    return f"{salt}${h}"

def verify_password(password: str, stored: str) -> bool:
    if not stored or "$" not in stored:
        return False
    salt, _ = stored.split("$", 1)
    return hash_password(password, salt) == stored


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


# =====================================================================
# V2.1 新增：用户 / 方案 / 条件 / 版本 / 日志 CRUD
# =====================================================================

# ---------- 用户 ----------
def create_user(conn, username, password, display_name=None, role="viewer",
                status="active", license_key=None, sub_tier="free", sub_expiry=None) -> int:
    cur = conn.execute(
        """INSERT INTO users (username, password_hash, display_name, role, status,
           license_key, sub_tier, sub_expiry, created_at)
           VALUES (?,?,?,?,?,?,?,?,datetime('now','localtime'))""",
        (username, hash_password(password), display_name or username, role, status,
         license_key, sub_tier, sub_expiry))
    conn.commit()
    return cur.lastrowid

def get_user(conn, username) -> dict:
    row = conn.execute("SELECT * FROM users WHERE username=?", [username]).fetchone()
    return dict(row) if row else None

def get_user_by_id(conn, uid) -> dict:
    row = conn.execute("SELECT * FROM users WHERE id=?", [uid]).fetchone()
    return dict(row) if row else None

def list_users(conn) -> list:
    rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    return [dict(r) for r in rows]

def update_user_role(conn, user_id, role):
    conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    conn.commit()

def set_license(conn, user_id, license_key, sub_tier="pro", sub_expiry=None):
    conn.execute("UPDATE users SET license_key=?, sub_tier=?, sub_expiry=? WHERE id=?",
                 (license_key, sub_tier, sub_expiry, user_id))
    conn.commit()

# ---------- 筛选方案 ----------
def create_scheme(conn, name, owner_id, description="", is_pinned=0, is_shared=1) -> int:
    cur = conn.execute(
        """INSERT INTO filter_schemes (name, owner_id, is_pinned, is_shared, description,
           created_at, updated_at) VALUES (?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))""",
        (name, owner_id, is_pinned, is_shared, description))
    conn.commit()
    return cur.lastrowid

def get_scheme(conn, scheme_id) -> dict:
    row = conn.execute("SELECT * FROM filter_schemes WHERE id=?", [scheme_id]).fetchone()
    return dict(row) if row else None

def list_schemes(conn, user_id=None, include_shared=True) -> list:
    """owner/admin 看全部；editor/viewer 看自己的 + 共享的（除非指定 user_id 限定）。"""
    if user_id is None:
        rows = conn.execute("SELECT * FROM filter_schemes ORDER BY is_pinned DESC, id").fetchall()
    elif include_shared:
        rows = conn.execute(
            "SELECT * FROM filter_schemes WHERE owner_id=? OR is_shared=1 ORDER BY is_pinned DESC, id",
            [user_id]).fetchall()
    else:
        rows = conn.execute("SELECT * FROM filter_schemes WHERE owner_id=? ORDER BY is_pinned DESC, id",
                            [user_id]).fetchall()
    return [dict(r) for r in rows]

def update_scheme(conn, scheme_id, **fields):
    fields.pop("id", None)
    if not fields:
        return
    sets = ", ".join([f"{k}=?" for k in fields]) + ", updated_at=datetime('now','localtime')"
    conn.execute(f"UPDATE filter_schemes SET {sets} WHERE id=?", list(fields.values()) + [scheme_id])
    conn.commit()

def delete_scheme(conn, scheme_id):
    conn.execute("DELETE FROM scheme_conditions WHERE scheme_id=?", [scheme_id])
    conn.execute("DELETE FROM scheme_versions WHERE scheme_id=?", [scheme_id])
    conn.execute("DELETE FROM filter_schemes WHERE id=?", [scheme_id])
    conn.commit()

def pin_scheme(conn, scheme_id, is_pinned=1):
    conn.execute("UPDATE filter_schemes SET is_pinned=?, updated_at=datetime('now','localtime') WHERE id=?",
                 (is_pinned, scheme_id))
    conn.commit()

# ---------- 方案条件 ----------
def add_condition(conn, scheme_id, catalog_key, operator, value, value2=None,
                  sort_order=0, enabled=1) -> int:
    cur = conn.execute(
        """INSERT INTO scheme_conditions (scheme_id, catalog_key, operator, value, value2, sort_order, enabled)
           VALUES (?,?,?,?,?,?,?)""",
        (scheme_id, catalog_key, operator, _to_text(value), _to_text(value2), sort_order, enabled))
    conn.commit()
    return cur.lastrowid

def update_condition(conn, cond_id, **fields):
    fields.pop("id", None)
    if not fields:
        return
    sets = ", ".join([f"{k}=?" for k in fields])
    vals = [(_to_text(v) if k in ("value", "value2") else v) for k, v in fields.items()]
    conn.execute(f"UPDATE scheme_conditions SET {sets} WHERE id=?", vals + [cond_id])
    conn.commit()

def remove_condition(conn, cond_id):
    conn.execute("DELETE FROM scheme_conditions WHERE id=?", [cond_id])
    conn.commit()

def list_conditions(conn, scheme_id) -> list:
    rows = conn.execute(
        "SELECT * FROM scheme_conditions WHERE scheme_id=? ORDER BY sort_order, id",
        [scheme_id]).fetchall()
    return [dict(r) for r in rows]

def _to_text(v):
    if v is None:
        return None
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)

def _from_text(v, ftype="numeric"):
    """scheme_conditions.value 以文本存储，按类型还原。"""
    if v is None or v == "":
        return None
    if ftype == "numeric":
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    if ftype in ("enum", "text"):
        # enum-in 可能存 JSON 数组
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return v

# ---------- 方案版本（版本化 + 回滚） ----------
def snapshot_version(conn, scheme_id, by_user, note="") -> int:
    scheme = get_scheme(conn, scheme_id)
    conds = list_conditions(conn, scheme_id)
    last = conn.execute(
        "SELECT MAX(version_no) FROM scheme_versions WHERE scheme_id=?", [scheme_id]).fetchone()[0]
    version_no = (last or 0) + 1
    snapshot = {"scheme": scheme, "conditions": conds}
    cur = conn.execute(
        """INSERT INTO scheme_versions (scheme_id, version_no, snapshot_json, created_by, created_at, note)
           VALUES (?,?,?,?,datetime('now','localtime'),?)""",
        (scheme_id, version_no, json.dumps(snapshot, ensure_ascii=False, default=str), by_user, note))
    conn.commit()
    return cur.lastrowid

def list_versions(conn, scheme_id) -> list:
    rows = conn.execute(
        "SELECT * FROM scheme_versions WHERE scheme_id=? ORDER BY version_no DESC",
        [scheme_id]).fetchall()
    return [dict(r) for r in rows]

def rollback_version(conn, scheme_id, version_id):
    v = conn.execute("SELECT * FROM scheme_versions WHERE id=? AND scheme_id=?",
                     [version_id, scheme_id]).fetchone()
    if not v:
        return False
    snap = json.loads(v["snapshot_json"])
    # 清空现有条件，按快照重建
    conn.execute("DELETE FROM scheme_conditions WHERE scheme_id=?", [scheme_id])
    for c in snap.get("conditions", []):
        add_condition(conn, scheme_id, c["catalog_key"], c["operator"],
                      c.get("value"), c.get("value2"), c.get("sort_order", 0), c.get("enabled", 1))
    conn.execute("UPDATE filter_schemes SET updated_at=datetime('now','localtime') WHERE id=?", [scheme_id])
    conn.commit()
    return True

# ---------- 操作日志 ----------
def log_operation(conn, user_id, action, target_type, target_id, detail=""):
    conn.execute(
        """INSERT INTO operation_logs (user_id, action, target_type, target_id, detail, created_at)
           VALUES (?,?,?,?,?,datetime('now','localtime'))""",
        (user_id, action, target_type, target_id, detail))
    conn.commit()

def list_logs(conn, user_id=None, role="viewer") -> list:
    """owner/admin 看全部；editor/viewer 仅看自己相关的。"""
    if role in ("owner", "admin") or user_id is None:
        rows = conn.execute("SELECT * FROM operation_logs ORDER BY id DESC").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM operation_logs WHERE user_id=? ORDER BY id DESC", [user_id]).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    c = connect()
    print("DB ready at", DEFAULT_DB, "| rows:", count(c))
    c.close()
