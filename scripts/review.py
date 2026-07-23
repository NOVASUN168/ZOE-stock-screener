# -*- coding: utf-8 -*-
"""
stock-screener · 每日复盘引擎
基于当前快照生成：买点/卖点信号、持仓建议（观察池）、风险警示、市场热点、行业轮动、明日重点。
所有信号均为“推断”，依赖录入的指标与评分，非实时行情决策。需实时性请接入行情源（见 README）。
"""
import sqlite3
from datetime import datetime

from alerts import risk_reminders, watch_list, list_alerts


def _industry_cat(industry):
    return (industry or "其它").split("/")[0].strip()


def daily_review(conn):
    rows = [dict(r) for r in conn.execute("SELECT * FROM stocks").fetchall()]
    elig = [r for r in rows if "排除" not in (r.get("rating") or "")]

    buy, sell = [], []
    for r in elig:
        ma = r.get("ma_trend"); macd = r.get("macd"); mf = r.get("main_fund_flow")
        score = r.get("total_score") or 0
        reasons = []
        if ma in ("多头", "多头排列") and macd in ("金叉", "红柱") and mf in ("净流入", "流入") and score >= 80:
            if ma in ("多头", "多头排列"): reasons.append("均线多头")
            if macd in ("金叉", "红柱"): reasons.append(macd)
            if mf in ("净流入", "流入"): reasons.append("资金流入")
            buy.append({"stock": r, "reasons": reasons})
        if (ma in ("空头",) or macd == "死叉") and mf == "净流出":
            reasons.append("趋势走坏" if ma == "空头" else macd)
            if mf == "净流出": reasons.append("主力出逃")
            sell.append({"stock": r, "reasons": reasons})
        elif score < 70:
            sell.append({"stock": r, "reasons": [f"评分偏低({score:.0f})"]})

    # 观察池（持仓监控）
    watch = watch_list(conn)
    # 风险警示
    risks = risk_reminders(conn)
    # 市场热点：高分股票最多的行业
    ind_score = {}
    for r in elig:
        c = _industry_cat(r.get("industry"))
        ind_score.setdefault(c, []).append(r.get("total_score") or 0)
    hot = sorted(ind_score.items(), key=lambda x: (-len(x[1]), -sum(x[1]) / len(x[1])))[:3]
    # 行业轮动：各行业平均评分排名（前后对比用截面近似）
    rotation = [{"industry": k, "avg_score": round(sum(v) / len(v), 1), "count": len(v)}
                for k, v in sorted(ind_score.items(), key=lambda x: -sum(x[1]) / len(x[1]))]
    # 明日重点：买点候选 + 未触发预警
    alerts = [a for a in list_alerts(conn, active_only=True) if not a.get("triggered")]
    focus = []
    for b in buy[:5]:
        focus.append(f"{b['stock']['name']}（买点观察：{b['stock'].get('buy_point')}）")
    for a in alerts[:3]:
        s = conn.execute("SELECT name FROM stocks WHERE id=?", [a["stock_id"]]).fetchone()
        if s:
            focus.append(f"{s['name']} 预警待触发：{a['atype']}")

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "buy": buy,
        "sell": sell,
        "watch": watch,
        "risks": risks,
        "hot_topics": [{"industry": k, "count": len(v), "avg_score": round(sum(v) / len(v), 1)} for k, v in hot],
        "rotation": rotation,
        "tomorrow_focus": focus,
    }


if __name__ == "__main__":
    c = sqlite3.connect("data/screener.db"); c.row_factory = sqlite3.Row
    rv = daily_review(c)
    print("日期", rv["date"])
    print("买点", [b["stock"]["name"] for b in rv["buy"]])
    print("卖点", [s["stock"]["name"] for s in rv["sell"]])
    print("热点", rv["hot_topics"])
    print("轮动TOP", rv["rotation"][:4])
    print("明日重点", rv["tomorrow_focus"])
    c.close()
