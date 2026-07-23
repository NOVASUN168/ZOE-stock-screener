# -*- coding: utf-8 -*-
"""
stock-screener · 多因子评分引擎
严格按用户给定的权重计算综合分(0-100)、等级、推荐指数、风险标记，
并实现三类风格（绩优/长线/短线）筛选与启发式结论字段。
所有"结论字段"均标注为推断（非事实），UI 层会显式区隔。
"""
from datetime import datetime

# ---------- 工具函数 ----------
def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def _yn(v):
    return str(v) in ("1", "true", "True", "是", "是", "True", "1.0")

def _half(maxp, val, hit, partial=None, miss=0.0):
    """三态计分：命中=maxp，未知(None/空)=maxp*0.5，未命中=miss。"""
    if val is None or val == "":
        return maxp * 0.5 if partial is None else partial
    return maxp if hit else miss

def _txt(v):
    return "" if v is None else str(v)


# ---------- 六大因子 ----------
def _fundamental(r):
    s = 0.0
    roe = _num(r.get("roe")); s += _half(6, roe, roe is not None and roe > 15)
    if roe is not None and 10 < roe <= 15: s += 3
    elif roe is not None and 0 < roe <= 10: s += 1
    roa = _num(r.get("roa")); s += _half(5, roa, roa is not None and roa > 8)
    if roa is not None and 5 < roa <= 8: s += 2.5
    elif roa is not None and 0 < roa <= 5: s += 1
    rg = _num(r.get("rev_growth_years"))
    s += _half(5, rg, rg == 3) if rg != 2 and rg != 1 else (3 if rg == 2 else 1)
    ng = _num(r.get("netprofit_growth_years"))
    s += _half(5, ng, ng == 3) if ng != 2 and ng != 1 else (3 if ng == 2 else 1)
    s += _half(4, r.get("fcf_positive"), _yn(r.get("fcf_positive")))
    dr = _num(r.get("debt_ratio")); st = _txt(r.get("sector_type"))
    if dr is None:
        s += 2.5
    else:
        if st == "科技":
            s += 5 if dr < 50 else (2.5 if dr < 65 else 0)
        elif st == "金融":
            s += 3
        else:
            s += 5 if dr < 60 else (2.5 if dr < 70 else 0)
    return min(s, 30.0)

def _valuation(r):
    s = 0.0
    pe = _num(r.get("pe")); pe_avg = _num(r.get("pe_industry_avg"))
    if pe is None: s += 2.5
    elif pe_avg is not None and pe < pe_avg: s += 5
    elif pe_avg is not None and pe < pe_avg * 1.2: s += 3
    pb = _num(r.get("pb"))
    if pb is None: s += 2
    elif pb <= 3: s += 4
    elif pb <= 5: s += 2
    peg = _num(r.get("peg"))
    if peg is None: s += 2.5
    elif peg < 1: s += 5
    elif peg < 1.5: s += 4
    elif peg < 2: s += 2
    ev = _num(r.get("ev_ebitda"))
    if ev is None: s += 1.5
    elif ev <= 15: s += 3
    elif ev <= 20: s += 1.5
    sm = _num(r.get("safety_margin"))
    if sm is None: s += 1.5
    elif sm >= 30: s += 3
    elif sm >= 15: s += 1.5
    return min(s, 20.0)

def _growth(r):
    s = 0.0
    s += _half(4, r.get("rd_increase"), _yn(r.get("rd_increase")))
    s += _half(4, r.get("mkt_share_growth"), _yn(r.get("mkt_share_growth")))
    isp = _txt(r.get("industry_space"))
    s += {"大": 4, "中": 2, "小": 0}.get(isp, 2)
    moat = _txt(r.get("moat"))
    s += {"明显": 4, "强": 4, "中等": 2, "弱": 0, "无": 0}.get(moat, 2)
    pf = _num(r.get("profit_forecast_3y"))
    if pf is None: s += 2
    elif pf >= 15: s += 4
    elif pf >= 8: s += 2
    return min(s, 20.0)

def _technical(r):
    s = 0.0
    ma = _txt(r.get("ma_trend"))
    s += {"多头": 4, "多头排列": 4, "震荡": 2, "空头": 0}.get(ma, 2)
    macd = _txt(r.get("macd"))
    s += {"金叉": 3, "红柱": 3, "持平": 1.5, "死叉": 0, "绿柱": 0}.get(macd, 1.5)
    kdj = _txt(r.get("kdj"))
    s += {"金叉": 2, "持平": 1, "死叉": 0}.get(kdj, 1)
    rsi = _num(r.get("rsi"))
    if rsi is None: s += 1
    elif 30 <= rsi <= 70: s += 2
    elif rsi < 30: s += 1.5
    else: s += 1
    vol = _txt(r.get("volume"))
    s += {"放量": 2, "温和放大": 2, "持平": 1, "萎缩": 0}.get(vol, 1)
    vlt = _txt(r.get("volatility"))
    s += {"低": 2, "中": 1, "高": 0}.get(vlt, 1)
    return min(s, 15.0)

def _capital(r):
    s = 0.0
    mf = _txt(r.get("main_fund_flow"))
    s += {"净流入": 4, "流入": 4, "持平": 2, "净流出": 0}.get(mf, 2)
    nb = _txt(r.get("northbound"))
    s += {"增持": 3, "持平": 1.5, "减持": 0}.get(nb, 1.5)
    ic = _txt(r.get("institution_change"))
    s += {"增仓": 3, "持平": 1.5, "减仓": 0}.get(ic, 1.5)
    return min(s, 10.0)

def _risk(r):
    s = 5.0
    if _yn(r.get("financial_risk")): s -= 1
    if _yn(r.get("litigation")): s -= 1
    pr = _num(r.get("pledge_ratio"))
    if pr is not None:
        s -= 1.5 if pr > 50 else (0.5 if pr > 30 else 0)
    if _yn(r.get("regulatory_penalty")): s -= 0.5
    gr = _num(r.get("goodwill_ratio"))
    if gr is not None:
        s -= 1 if gr > 40 else (0.5 if gr > 20 else 0)
    return max(s, 0.0)


# ---------- 硬过滤（一票否决） ----------
HARD_FILTERS = [
    ("st_flag", "ST股"),
    ("delisting_risk", "退市风险"),
    ("fraud_flag", "财务造假嫌疑"),
    ("litigation", "重大诉讼"),
    ("consecutive_loss", "连续亏损"),
    ("major_holder_reduction", "大股东减持"),
    ("high_pledge", "高质押"),
]
def _hard_excluded(r):
    hits = []
    for key, label in HARD_FILTERS:
        if key == "litigation":
            if _yn(r.get(key)): hits.append(label)
        elif key == "high_pledge":
            if _yn(r.get(key)): hits.append(label)
        else:
            if _yn(r.get(key)): hits.append(label)
    gr = _num(r.get("goodwill_ratio"))
    if gr is not None and gr > 40:
        hits.append("商誉过高(>40%)")
    return hits


# ---------- 软风险标记 ----------
def _soft_risks(r):
    flags = []
    if _yn(r.get("financial_risk")): flags.append("⚠️ 财务风险")
    pr = _num(r.get("pledge_ratio"))
    if pr is not None and pr > 30: flags.append(f"⚠️ 质押比例 {pr:.0f}%")
    if _yn(r.get("regulatory_penalty")): flags.append("⚠️ 监管处罚")
    gr = _num(r.get("goodwill_ratio"))
    if gr is not None and 20 < gr <= 40: flags.append(f"⚠️ 商誉占比 {gr:.0f}%")
    return flags


# ---------- 评级 ----------
def _rating(score):
    if score >= 95: return "★★★★★", "强烈推荐"
    if score >= 90: return "★★★★☆", "推荐"
    if score >= 80: return "★★★★", "关注"
    if score >= 70: return "★★★", "一般"
    return "★★", "不建议"


# ---------- 启发式结论（标注：推断） ----------
def _heuristics(r, score):
    price = _num(r.get("price"))
    peg = _num(r.get("peg"))
    pf = _num(r.get("profit_forecast_3y"))
    sm = _num(r.get("safety_margin"))
    pe_avg = _num(r.get("pe_industry_avg"))

    # 合理估值
    if peg is not None and pf is not None:
        fair_pe = peg * pf
        reasonable = f"合理PE≈{fair_pe:.1f}（PEG×三年利润增速，推断）"
    elif pe_avg is not None:
        reasonable = f"参考行业PE均值 {pe_avg:.1f}（推断）"
    else:
        reasonable = "待补充估值数据（推断）"

    # 目标价格
    tp = None
    if price:
        upside = None
        if sm is not None: upside = min(sm, 50)
        elif pf is not None: upside = min(pf, 40)
        if upside is None: upside = 20
        tp = price * (1 + upside / 100)
    target = f"{tp:.2f}" if tp else "待定"

    # 买点 / 止损 / 止盈
    buy = f"{price*0.95:.2f} 附近企稳" if price else "待定"
    stop = f"{price*0.90:.2f}（约-10%）" if price else "待定"
    take = f"{tp:.2f}" if tp else "待定"

    # 仓位
    if score >= 90: pos = "15-20%"
    elif score >= 80: pos = "10-15%"
    elif score >= 70: pos = "5-10%"
    else: pos = "暂不配置"

    # 预计收益
    er = f"{(tp/price-1)*100:.1f}%" if (tp and price) else "待定"

    # 预计持有时间（默认，按分数；风格筛选会覆盖）
    if score >= 90: hold = "1-3 年"
    elif score >= 80: hold = "6-18 个月"
    else: hold = "波段 / 观望"

    return {
        "reasonable_valuation": reasonable,
        "target_price": target,
        "buy_point": buy,
        "stop_loss": stop,
        "take_profit": take,
        "suggested_position": pos,
        "expected_return": er,
        "expected_hold": hold,
    }


def _reasons(r, score):
    reasons = []
    roe = _num(r.get("roe"))
    if roe is not None and roe > 15:
        reasons.append(f"盈利能力强：ROE {roe:.1f}% 高于 15% 阈值")
    peg = _num(r.get("peg"))
    if peg is not None and peg < 1.5:
        reasons.append(f"估值合理：PEG {peg:.2f}（<1.5）提供安全边际")
    moat = _txt(r.get("moat"))
    if moat in ("明显", "强"):
        reasons.append(f"护城河{moat}：具备长期竞争壁垒")
    mf = _txt(r.get("main_fund_flow"))
    if mf in ("净流入", "流入"):
        reasons.append("资金面友好：主力资金净流入")
    ma = _txt(r.get("ma_trend"))
    if ma in ("多头", "多头排列"):
        reasons.append("技术面多头排列，趋势向上")
    pf = _num(r.get("profit_forecast_3y"))
    if pf is not None and pf >= 15:
        reasons.append(f"成长预期高：未来三年利润预测增速 {pf:.1f}%")
    if not reasons:
        reasons.append("综合因子得分中等，暂无单项突出优势，建议补充数据后重评")
    return reasons[:4]


def _advantages(r):
    adv = []
    roe = _num(r.get("roe"))
    if roe and roe > 15: adv.append(f"ROE {roe:.1f}%")
    peg = _num(r.get("peg"))
    if peg and peg < 1.5: adv.append(f"PEG {peg:.2f}")
    if _yn(r.get("fcf_positive")): adv.append("自由现金流转正")
    moat = _txt(r.get("moat"))
    if moat in ("明显", "强"): adv.append("护城河明显")
    if _txt(r.get("ma_trend")) in ("多头", "多头排列"): adv.append("均线多头")
    return "、".join(adv) if adv else "—"


# ---------- 主入口 ----------
def score_stock(row: dict) -> dict:
    row = dict(row)
    f = _fundamental(row); v = _valuation(row); g = _growth(row)
    t = _technical(row); c = _capital(row); rk = _risk(row)
    total = round(f + v + g + t + c + rk, 1)

    hard = _hard_excluded(row)
    soft = _soft_risks(row)
    stars, label = _rating(total)
    if hard:
        stars, label = "★★", "排除（硬过滤）"
        total = min(total, 65.0)  # 强制压低，UI 标红

    h = _heuristics(row, total)
    row.update({
        "total_score": total,
        "rating": label,
        "recommend_index": stars,
        "risk_flags": "; ".join(hard + soft) if (hard or soft) else "无",
        "advantages": _advantages(row),
        "risks_text": "; ".join(hard + soft) if (hard or soft) else "暂无显著风险",
        "recommend_reasons": " | ".join(_reasons(row, total)),
    })
    row.update(h)
    return row


def rescore_all(rows: list) -> list:
    return [score_stock(r) for r in rows]


# ---------- 三类风格筛选 ----------
def screen_by_style(rows: list, style: str) -> list:
    scored = rescore_all(rows)
    def _key(r): return r.get("id") or r.get("code") or id(r)
    excluded = {_key(r) for r in scored if "排除" in r["rating"]}
    out = [r for r in scored if _key(r) not in excluded]

    if style == "绩优" or style == "quality":
        # 偏好高基本面+估值+成长，行业偏好 AI/半导体/机器人/新能源/医药/消费/高端制造/云计算/软件
        pref = ["AI", "人工智能", "半导体", "芯片", "机器人", "新能源", "医药", "消费", "高端制造", "云计算", "软件"]
        def q_key(r):
            base = r["total_score"]
            ind = _txt(r.get("industry"))
            if any(p in ind for p in pref): base += 3
            return base
        out = sorted(out, key=q_key, reverse=True)

    elif style == "长线" or style == "long":
        # 要求护城河+ROE+自由现金流转正；持有5年以上
        def l_key(r):
            base = r["total_score"]
            if _txt(r.get("moat")) in ("明显", "强"): base += 5
            if _yn(r.get("fcf_positive")): base += 3
            return base
        out = [r for r in out if _txt(r.get("moat")) in ("明显", "强", "")]
        out = sorted(out, key=l_key, reverse=True)
        for r in out:
            r["expected_hold"] = "5年以上（长线持有）"

    elif style == "短线" or style == "short":
        # 要求技术多头+资金流入；持股 1-20 交易日
        def s_key(r):
            base = 0.0
            if _txt(r.get("ma_trend")) in ("多头", "多头排列"): base += 6
            if _txt(r.get("macd")) in ("金叉", "红柱"): base += 4
            if _txt(r.get("volume")) in ("放量", "温和放大"): base += 3
            if _txt(r.get("main_fund_flow")) in ("净流入", "流入"): base += 4
            if _txt(r.get("kdj")) == "金叉": base += 3
            return base
        out = [r for r in out if (s_key(r) >= 10)]
        out = sorted(out, key=s_key, reverse=True)
        for r in out:
            r["expected_hold"] = "1-20 交易日（短线）"
            r["suggested_position"] = "10-15%（短线，严控仓位）"

    return out


if __name__ == "__main__":
    demo = {"code": "sh600519", "name": "贵州茅台", "industry": "消费/白酒", "price": 1500,
            "roe": 30, "roa": 22, "rev_growth_years": 3, "netprofit_growth_years": 3,
            "fcf_positive": 1, "debt_ratio": 20, "sector_type": "制造业",
            "pe": 25, "pe_industry_avg": 30, "pb": 8, "peg": 1.2, "ev_ebitda": 18, "safety_margin": 25,
            "rd_increase": 1, "mkt_share_growth": 1, "industry_space": "大", "moat": "明显", "profit_forecast_3y": 15,
            "ma_trend": "多头", "macd": "金叉", "kdj": "金叉", "rsi": 55, "volume": "温和放大", "volatility": "低",
            "main_fund_flow": "净流入", "northbound": "增持", "institution_change": "增仓",
            "financial_risk": 0, "litigation": 0, "pledge_ratio": 0, "regulatory_penalty": 0, "goodwill_ratio": 2}
    print(score_stock(demo))
