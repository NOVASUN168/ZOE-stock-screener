# -*- coding: utf-8 -*-
"""
stock-screener · 预警与风控提醒引擎
说明：本系统是“基于当前数据库快照的规则引擎”，不是实时行情推送。
     - 预警规则：用户为某只股票设定阈值（评分跌破/价格突破/出现风险），evaluate 时比对当前快照判定是否触发。
     - 风控提醒：自动汇总所有带风险标记（ST/高质押/商誉高/财务·诉讼·监管风险）的股票，置顶醒目展示。
     价格类预警要变成“实时”，需接入行情源（见 README 的「行情接入」一节），这里用录入价做演示。
所有“触发/预计”均为推断，UI 会显式区隔。
"""
import sqlite3
from datetime import datetime

ALERT_TYPES = {
    "score_drop": "评分跌破",
    "price_up":   "价格涨破",
    "price_down": "价格跌破",
    "risk_trigger": "出现风险标记",
}


def add_alert(conn, stock_id, atype, threshold=None, note=""):
    conn.execute(
        "INSERT INTO alerts(stock_id, atype, threshold, note, active, triggered, created_at) "
        "VALUES(?,?,?,?,1,0,datetime('now','localtime'))",
        (stock_id, atype, threshold, note or ""))
    conn.commit()


def list_alerts(conn, active_only=False):
    sql = "SELECT * FROM alerts"
    if active_only:
        sql += " WHERE active=1"
    sql += " ORDER BY id DESC"
    return [dict(r) for r in conn.execute(sql).fetchall()]


def delete_alert(conn, aid):
    conn.execute("DELETE FROM alerts WHERE id=?", [aid])
    conn.commit()


def _set_triggered(conn, aid, triggered):
    conn.execute(
        "UPDATE alerts SET triggered=?, triggered_at=? WHERE id=?",
        (1 if triggered else 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S") if triggered else None, aid))
    conn.commit()


def evaluate_alerts(conn):
    """逐条比对当前快照，返回每条预警的触发状态。同时把触发态写回 DB。"""
    out = []
    for a in list_alerts(conn, active_only=True):
        stock = conn.execute("SELECT * FROM stocks WHERE id=?", [a["stock_id"]]).fetchone()
        if not stock:
            continue
        stock = dict(stock)
        trig, reason = False, ""
        atype, th = a["atype"], a["threshold"]
        score = stock.get("total_score")
        price = stock.get("price")
        flags = stock.get("risk_flags")
        if atype == "score_drop":
            if score is not None and th is not None and score <= th:
                trig, reason = True, f"综合评分 {score:.1f} ≤ 阈值 {th:.0f}"
        elif atype == "price_up":
            if price is not None and th is not None and price >= th:
                trig, reason = True, f"现价 {price:.2f} ≥ 目标 {th:.2f}"
        elif atype == "price_down":
            if price is not None and th is not None and price <= th:
                trig, reason = True, f"现价 {price:.2f} ≤ 止损 {th:.2f}"
        elif atype == "risk_trigger":
            if flags and flags != "无":
                trig, reason = True, f"风险标记：{flags}"
        _set_triggered(conn, a["id"], trig)
        out.append({"alert": a, "stock": stock, "triggered": trig, "reason": reason})
    return out


def risk_reminders(conn):
    """风控提醒：汇总所有带风险标记的股票（含已被硬过滤的），按风险严重度排序。"""
    rows = [dict(r) for r in conn.execute("SELECT * FROM stocks").fetchall()]
    out = []
    for r in rows:
        flags = r.get("risk_flags")
        if flags and flags != "无":
            # 严重度：硬过滤(排除) > 高质押/商誉高 > 软风险
            hard = "排除" in (r.get("rating") or "")
            sev = 3 if hard else (2 if ("高质押" in flags or "商誉" in flags) else 1)
            out.append({"stock": r, "flags": flags, "severity": sev, "hard": hard})
    out.sort(key=lambda x: (-x["severity"], -(x["stock"].get("total_score") or 0)))
    return out


def watch_add(conn, stock_id, note=""):
    conn.execute("INSERT INTO watchlist(stock_id, note, created_at) VALUES(?,?,datetime('now','localtime'))",
                 (stock_id, note or ""))
    conn.commit()


def watch_list(conn):
    out = []
    for w in conn.execute("SELECT * FROM watchlist ORDER BY id DESC").fetchall():
        w = dict(w)
        s = conn.execute("SELECT * FROM stocks WHERE id=?", [w["stock_id"]]).fetchone()
        if s:
            w["stock"] = dict(s)
            out.append(w)
    return out


def watch_remove(conn, wid):
    conn.execute("DELETE FROM watchlist WHERE id=?", [wid])
    conn.commit()


if __name__ == "__main__":
    c = sqlite3.connect("data/screener.db"); c.row_factory = sqlite3.Row
    print("风控提醒：")
    for x in risk_reminders(c):
        print(" ", x["stock"]["name"], "|", x["flags"], "| 硬过滤" if x["hard"] else "")
    print("评估预警（无规则时为空）：")
    for x in evaluate_alerts(c):
        print(" ", x["stock"]["name"], x["alert"]["atype"], "触发" if x["triggered"] else "未触发", x["reason"])
    c.close()
