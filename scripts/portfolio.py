# -*- coding: utf-8 -*-
"""
stock-screener · 组合推荐引擎
生成三类组合（稳健 / 成长 / 激进），输出资金分配、行业占比、风险等级、收益预期、最大回撤（均为推断）。
数据来源：当前数据库快照（已评分）。所有结论标注为推断，非承诺。
"""
from datetime import datetime


def _industry_cat(industry):
    return (industry or "其它").split("/")[0].strip()


def _vol_rank(r, prefer_high=False):
    rank = {"低": 0, "中": 1, "高": 2}.get(r.get("volatility"), 1)
    return -rank if prefer_high else rank


def _parse_pct(s):
    try:
        return float(str(s).replace("%", ""))
    except Exception:
        return None


def generate(conn, ptype="robust", top_n=8):
    rows = [dict(r) for r in conn.execute("SELECT * FROM stocks").fetchall()]
    # 排除硬过滤
    elig = [r for r in rows if "排除" not in (r.get("rating") or "")]
    elig.sort(key=lambda r: -(r.get("total_score") or 0))

    if ptype == "robust":
        name = "稳健型组合"
        pool = [r for r in elig if (r.get("total_score") or 0) >= 80]
        # 偏好低波动 / 稳定（用 volatility 与股息代理：这里用 volatility 低 + score）
        pool.sort(key=lambda r: (_vol_rank(r), -(r.get("total_score") or 0)))
    elif ptype == "growth":
        name = "成长型组合"
        pool = [r for r in elig if (r.get("total_score") or 0) >= 82]
        pool.sort(key=lambda r: (-(r.get("profit_forecast_3y") or 0), -(r.get("total_score") or 0)))
    else:  # aggressive
        name = "激进型组合"
        pool = [r for r in elig if (r.get("total_score") or 0) >= 78]
        pool.sort(key=lambda r: (_vol_rank(r, prefer_high=True), -(r.get("total_score") or 0)))

    picks = pool[:top_n]
    if not picks:
        # 兜底：取全局前 top_n，保证有输出
        picks = elig[:top_n]

    n = len(picks)
    # 分配：头部略集中，尾部递减（等权基底 + 头部加成）
    weights = []
    base = 100.0 / n
    for i in range(n):
        w = base * (1.4 if i == 0 else (1.15 if i == 1 else (0.9 if i >= n - 2 else 1.0)))
        weights.append(w)
    s = sum(weights)
    alloc = [round(w / s * 100, 1) for w in weights]

    picks_out = []
    ind_pct = {}
    alloc_views = {}
    vols = []
    for i, r in enumerate(picks):
        ind = _industry_cat(r.get("industry"))
        ind_pct[ind] = ind_pct.get(ind, 0) + alloc[i]
        av = r.get("suggested_position") or "观察"
        alloc_views[av] = alloc_views.get(av, 0) + 1
        v = {"低": 0.06, "中": 0.12, "高": 0.22}.get(r.get("volatility"), 0.12)
        vols.append(v)
        picks_out.append({
            "id": r.get("id"), "code": r.get("code"), "name": r.get("name"),
            "industry": r.get("industry"), "score": r.get("total_score"),
            "alloc_pct": alloc[i], "suggested_position": r.get("suggested_position"),
            "expected_hold": r.get("expected_hold"), "risk_flags": r.get("risk_flags"),
        })

    # 组合层指标（推断；V2.0 不承诺收益率，改用配置视图与风险等级）
    avg_vol = sum(vols) / len(vols) if vols else 0.12
    max_dd = round(avg_vol * 2.2 * 100, 1)  # 经验：最大回撤 ≈ 年化波动*2.2
    avg_score = sum((r.get("total_score") or 0) for r in picks) / n if n else 0
    risk_level = "低" if avg_score >= 88 and avg_vol <= 0.08 else ("中" if avg_score >= 80 else "高")
    alloc_view = "、".join(f"{k}×{v}" for k, v in sorted(alloc_views.items(), key=lambda x: -x[1]))

    return {
        "ptype": ptype, "name": name, "count": n,
        "picks": picks_out,
        "industry_pct": {k: round(v, 1) for k, v in sorted(ind_pct.items(), key=lambda x: -x[1])},
        "risk_level": risk_level,
        "alloc_view": alloc_view,
        "max_drawdown": f"{max_dd:.1f}%",
        "avg_score": round(avg_score, 1),
        "note": "组合指标为模型推断，非收益承诺；V2.0 聚焦 AI 产业与护城河，不做技术分析、不自动下单。实战需结合实时行情与人工判断。",
    }


def save(conn, ptype, name, picks, note=""):
    ids = [p["id"] for p in picks]
    alloc = {str(p["id"]): p["alloc_pct"] for p in picks}
    conn.execute(
        "INSERT INTO portfolios(ptype, name, stock_ids, alloc, note, created_at) "
        "VALUES(?,?,?,?,?,datetime('now','localtime'))",
        (ptype, name, __import__("json").dumps(ids, ensure_ascii=False),
         __import__("json").dumps(alloc, ensure_ascii=False), note))
    conn.commit()


if __name__ == "__main__":
    import sqlite3
    c = sqlite3.connect("data/screener.db"); c.row_factory = sqlite3.Row
    for t in ("robust", "growth", "aggressive"):
        g = generate(c, t)
        print(f"\n【{g['name']}】风险={g['risk_level']} 配置视图={g['alloc_view']} 最大回撤={g['max_drawdown']}")
        for p in g["picks"][:5]:
            print(f"  {p['name']} {p['alloc_pct']}% 分={p['score']}")
    c.close()
