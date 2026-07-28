# -*- coding: utf-8 -*-
"""
stock-screener · 数据驱动筛选引擎（纯函数，无 HTTP）
把前端/后端筛选方案（scheme_conditions）翻译成对 stocks 行的逐条判定。
- eval_condition(row, cond): 单条条件判定（按 operator）
- apply_conditions(rows, conditions): 多条件 AND 过滤
- screen_by_scheme(conn, scheme_id): 取方案 → 评分 → 过滤 → 按评分降序
- screen_by_conditions(conn, conditions): 直传条件列表，同上
依赖：db / scoring / filter_catalog（同目录，零外部依赖）
"""
import sqlite3
import json

import db
import scoring
import filter_catalog as fc


# ---------- 条件归一化 ----------
def _normalize(cond: dict) -> dict:
    """把 scheme_conditions 行（catalog_key/operator/value/value2/enabled）
    解析为带 field/ftype 的判定用 dict。"""
    key = cond.get("catalog_key")
    entry = fc.get_entry(key) or {}
    ftype = entry.get("ftype", "numeric")
    field = entry.get("field") or key
    operator = cond.get("operator") or entry.get("operator") or "gt"
    return {
        "catalog_key": key,
        "field": field,
        "ftype": ftype,
        "operator": operator,
        "value": db._from_text(cond.get("value"), ftype),
        "value2": db._from_text(cond.get("value2"), ftype),
        "enabled": cond.get("enabled", 1),
    }


def _enrich(row: dict) -> dict:
    """确保筛选用到的字段存在于 row（computed: 占位字段补 None，避免 eval 崩溃）。"""
    row = dict(row)
    for e in fc.get_catalog():
        f = e["field"]
        if f.startswith("computed:") and f not in row:
            row[f] = None
    # net_capital_flow 已是真实列；hotmoney_flag 已是真实列，原样保留
    return row


# ---------- 单条件判定 ----------
def eval_condition(row: dict, cond: dict) -> bool:
    """按 operator 判定单行是否命中该条件。
    cond 需含: field / operator / value / (value2) / ftype。
    operator: gt/lt/between(numeric) · eq/in/neq(enum) · eq(bool) · like(text)
    游资排除通过 hotmoney_flag eq 0 或 hotmoney_ratio lt X 自然实现。"""
    field = cond.get("field")
    op = cond.get("operator")
    val = row.get(field)
    value = cond.get("value")
    value2 = cond.get("value2")
    ftype = cond.get("ftype", "numeric")

    # 数值型
    if op in ("gt", "lt", "between"):
        try:
            v = float(val)
        except (TypeError, ValueError):
            return False
        try:
            lo = float(value)
        except (TypeError, ValueError):
            return False
        if op == "gt":
            return v > lo
        if op == "lt":
            return v < lo
        if op == "between":
            try:
                hi = float(value2)
            except (TypeError, ValueError):
                return False
            return lo <= v <= hi

    # 枚举型
    if op in ("eq", "in", "neq"):
        if val is None:
            return False
        sv = str(val)
        if op == "eq":
            return sv == str(value)
        if op == "neq":
            return sv != str(value)
        if op == "in":  # value 为列表或逗号串
            items = value if isinstance(value, list) else str(value).split(",")
            return sv in [str(x).strip() for x in items]

    # 布尔型（0/1）
    if ftype == "bool" or op == "eq" and isinstance(value, (int, float)):
        if val is None or value is None:
            return False
        try:
            return int(float(val)) == int(float(value))
        except (TypeError, ValueError):
            return False

    # 文本型（like）
    if op == "like":
        if val is None or value is None:
            return False
        return str(value) in str(val)

    return False


# ---------- 多条件过滤 ----------
def apply_conditions(rows: list, conditions: list) -> list:
    """仅启用（enabled=1）的条件参与 AND 过滤。conditions 为归一化 dict 列表。"""
    active = [c for c in conditions if c.get("enabled", 1)]
    if not active:
        return rows
    out = []
    for r in rows:
        if all(eval_condition(r, c) for c in active):
            out.append(r)
    return out


# ---------- 方案筛选 ----------
def _load_rows(conn) -> list:
    raw = db.list_all(conn)  # 全量 stocks（含已回写的评分）
    enriched = [_enrich(r) for r in raw]
    # 评分刷新：应用最新硬过滤（如游资主导一票否决）与因子
    return [scoring.score_stock(r) for r in enriched]


def screen_by_scheme(conn, scheme_id: int) -> list:
    """取方案条件 → 取 stocks → 评分 → 过滤 → 按评分降序返回。"""
    scheme = db.get_scheme(conn, scheme_id)
    if not scheme:
        return []
    conds_db = db.list_conditions(conn, scheme_id)
    conditions = [_normalize(c) for c in conds_db]
    rows = _load_rows(conn)
    filtered = apply_conditions(rows, conditions)
    filtered.sort(key=lambda r: (r.get("total_score") or 0), reverse=True)
    return filtered


def screen_by_conditions(conn, conditions: list) -> list:
    """直传条件列表（归一化 dict，含 field/operator/value/value2/ftype/enabled）。"""
    conditions = [c if "field" in c else _normalize(c) for c in conditions]
    rows = _load_rows(conn)
    filtered = apply_conditions(rows, conditions)
    filtered.sort(key=lambda r: (r.get("total_score") or 0), reverse=True)
    return filtered


if __name__ == "__main__":
    # 内联自检：构造几条条件验证 eval_condition
    r = {"net_capital_flow": 5000.0, "hotmoney_flag": 1, "hotmoney_ratio": 80.0,
         "roe": 20.0, "st_flag": 0, "ai_category": "核心基础"}
    assert eval_condition(r, {"field": "net_capital_flow", "operator": "gt", "value": 1000.0, "ftype": "numeric"}) is True
    assert eval_condition(r, {"field": "hotmoney_flag", "operator": "eq", "value": 0, "ftype": "bool"}) is False
    assert eval_condition(r, {"field": "hotmoney_ratio", "operator": "lt", "value": 50.0, "ftype": "numeric"}) is False
    assert eval_condition(r, {"field": "st_flag", "operator": "eq", "value": 0, "ftype": "bool"}) is True
    assert eval_condition(r, {"field": "ai_category", "operator": "in", "value": ["核心基础", "模型平台"], "ftype": "enum"}) is True
    print("eval_condition 自检通过")
