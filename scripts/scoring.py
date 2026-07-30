# -*- coding: utf-8 -*-
"""
stock-screener · V2.0 多因子评分引擎（AI产业聚焦版）
核心逻辑：
  - 护城河难以复制 → 转化为更大市占率与利润（成长因子核心）
  - 聚焦 AI 产业四类（核心基础/模型平台/AI革命/AI医药）；非AI行业一票否决
  - 资金面只看主力长期趋势（过滤散户/短期游资）
  - 不做技术分析、不承诺收益率、不自动连接下单
权重：基本面35 / 估值20 / 成长25(护城河核心) / 资金15(主力长期) / 风险5 = 100
所有“结论字段”均标注为推断（非事实），UI 层会显式区隔。
"""
from datetime import datetime

# ---------- 工具函数 ----------
def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def _yn(v):
    return str(v) in ("1", "true", "True", "是", "True", "1.0")

def _half(maxp, val, hit, partial=None, miss=0.0):
    """三态计分：命中=maxp，未知(None/空)=maxp*0.5，未命中=miss。"""
    if val is None or val == "":
        return maxp * 0.5 if partial is None else partial
    return maxp if hit else miss

def _txt(v):
    return "" if v is None else str(v)


# ---------- 基本面 35 ----------
def _fundamental(r):
    s = 0.0
    roe = _num(r.get("roe")); s += _half(8, roe, roe is not None and roe > 15)
    if roe is not None and 10 < roe <= 15: s += 4
    elif roe is not None and 0 < roe <= 10: s += 1.5
    roa = _num(r.get("roa")); s += _half(5, roa, roa is not None and roa > 8)
    if roa is not None and 5 < roa <= 8: s += 2.5
    elif roa is not None and 0 < roa <= 5: s += 1
    rg = _num(r.get("rev_growth_years"))
    s += _half(5, rg, rg == 3) if rg not in (2, 1) else (3 if rg == 2 else 1)
    ng = _num(r.get("netprofit_growth_years"))
    s += _half(5, ng, ng == 3) if ng not in (2, 1) else (3 if ng == 2 else 1)
    s += _half(4, r.get("fcf_positive"), _yn(r.get("fcf_positive")))
    dr = _num(r.get("debt_ratio")); st = _txt(r.get("sector_type"))
    if dr is None:
        s += 4
    else:
        if st == "科技":
            s += 8 if dr < 50 else (4 if dr < 65 else 0)
        elif st == "金融":
            s += 4
        else:
            s += 8 if dr < 60 else (4 if dr < 70 else 0)
    return min(s, 35.0)

# ---------- 估值 20 ----------
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

# ---------- 成长 25（护城河核心逻辑） ----------
def _growth(r):
    s = 0.0
    s += _half(4, r.get("rd_increase"), _yn(r.get("rd_increase")))
    # 护城河 → 市占率转化
    s += _half(5, r.get("mkt_share_growth"), _yn(r.get("mkt_share_growth")))
    isp = _txt(r.get("industry_space"))
    s += {"大": 4, "中": 2, "小": 0}.get(isp, 2)
    # 护城河难以复制
    moat = _txt(r.get("moat"))
    s += {"明显": 8, "强": 8, "中等": 4, "弱": 0, "无": 0}.get(moat, 4)
    # 护城河 → 利润转化
    pf = _num(r.get("profit_forecast_3y"))
    if pf is None: s += 2
    elif pf >= 15: s += 4
    elif pf >= 8: s += 2
    elif pf > 0: s += 1
    return min(s, 25.0)

# ---------- 资金 15（主力长期趋势） ----------
def _capital(r):
    s = 0.0
    mft = _txt(r.get("main_force_trend"))
    s += {"流入": 8, "流出": 0, "持平": 4}.get(mft, 4)
    nb = _txt(r.get("northbound"))
    s += {"增持": 4, "持平": 2, "减持": 0}.get(nb, 2)
    ic = _txt(r.get("institution_change"))
    s += {"增仓": 3, "持平": 1.5, "减仓": 0}.get(ic, 1.5)
    # V2.1：纳入 20日主力净流入合计（net_capital_flow）作为资金加分项
    ncf = _num(r.get("net_capital_flow"))
    if ncf is not None and ncf > 0:
        s += 2  # 主力净流入为正，加 2 分（总分由 min(s,15) 封顶）
    return min(s, 15.0)

# ---------- 风险 5 ----------
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
    ("non_ai", "非AI驱动行业"),
    ("hotmoney_flag", "游资主导"),  # V2.1：游资主导个股一票否决
]
def _hard_excluded(r):
    hits = []
    for key, label in HARD_FILTERS:
        if key == "non_ai":
            if str(r.get("ai_driven")) == "0":
                hits.append(label)
        elif key in ("litigation", "high_pledge"):
            if _yn(r.get(key)):
                hits.append(label)
        else:
            if _yn(r.get(key)):
                hits.append(label)
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


# ---------- 启发式结论（标注：推断；V2.0 改为研究逻辑，不承诺收益） ----------
def _heuristics(r, score):
    peg = _num(r.get("peg"))
    pf = _num(r.get("profit_forecast_3y"))
    pe_avg = _num(r.get("pe_industry_avg"))
    moat = _txt(r.get("moat"))

    # 估值看法（定性，非目标价）
    if peg is not None and pf is not None:
        val_view = f"合理PE≈{peg*pf:.1f}（PEG×三年利润增速，推断）"
    elif pe_avg is not None:
        val_view = f"参考行业PE均值 {pe_avg:.1f}（推断）"
    else:
        val_view = "待补充估值数据（推断）"

    # 配置视图（定性，按评分，非收益承诺）
    if score >= 80: alloc = "核心配置"
    elif score >= 70: alloc = "卫星配置"
    elif score >= 60: alloc = "观察"
    else: alloc = "回避"

    # 持有期（长期，无短线）
    hold = "5年以上（长期持有）" if score >= 80 else "3年以上（长期持有）"

    # 核心竞争力（护城河摘要）
    comp = []
    if moat in ("明显", "强"): comp.append(f"护城河{moat}")
    if _yn(r.get("fcf_positive")): comp.append("自由现金流转正")
    roe = _num(r.get("roe"))
    if roe and roe > 15: comp.append(f"ROE {roe:.1f}%")
    if _txt(r.get("main_force_trend")) == "流入": comp.append("主力资金长期流入")
    core = "、".join(comp) if comp else "待补充护城河分析"

    # 长期研究逻辑
    thesis = []
    if _txt(r.get("industry_space")) == "大": thesis.append("行业空间大")
    if _yn(r.get("mkt_share_growth")): thesis.append("市占率持续提升，护城河正转化为份额")
    if pf is not None and pf >= 15: thesis.append(f"三年利润预期增速 {pf:.1f}%")
    mft = _txt(r.get("main_force_trend"))
    if mft == "流入": thesis.append("大资金长期趋势向好")
    elif mft == "流出": thesis.append("大资金长期趋势偏弱，需观察")
    else: thesis.append("大资金趋势持平，待确认")
    if not thesis: thesis.append("待补充产业与资金信号")

    return {
        "reasonable_valuation": val_view,
        "suggested_position": alloc,
        "expected_hold": hold,
        "core_competence": core,
        "long_term_thesis": "；".join(thesis),
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
        reasons.append(f"护城河{moat}：具备长期难以复制的竞争壁垒")
    if _yn(r.get("mkt_share_growth")):
        reasons.append("市占率持续提升，护城河正转化为市场份额")
    pf = _num(r.get("profit_forecast_3y"))
    if pf is not None and pf >= 15:
        reasons.append(f"成长预期高：未来三年利润预测增速 {pf:.1f}%")
    mft = _txt(r.get("main_force_trend"))
    if mft == "流入":
        reasons.append("主力资金长期趋势流入，大资金意图偏多")
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
    if _txt(r.get("main_force_trend")) == "流入": adv.append("主力长期流入")
    return "、".join(adv) if adv else "—"


# ---------- 五维雪花图（借鉴 Simply Wall St Snowflake：一张图看懂一只股票） ----------
def _dim_level(pct):
    """0-100 → 大白话等级"""
    if pct >= 80: return "优秀"
    if pct >= 60: return "良好"
    if pct >= 40: return "一般"
    return "偏弱"

_DIM_LABELS = [
    ("dim_fundamental", "基本面"),
    ("dim_valuation", "估值"),
    ("dim_growth", "成长"),
    ("dim_capital", "资金"),
    ("dim_safety", "安全"),
]

def _snowflake(f, v, g, c, rk):
    """把 5 个原始子分归一化为 0-100，供雪花图与维度条使用。
    注意：风险维度 rk 满分5 = 无风险，归一化后直接命名为「安全」，越高越安全。"""
    dims = {
        "dim_fundamental": round(f / 35 * 100),
        "dim_valuation": round(v / 20 * 100),
        "dim_growth": round(g / 25 * 100),
        "dim_capital": round(c / 15 * 100),
        "dim_safety": round(rk / 5 * 100),
    }
    # 大白话一句总结（学 Simply Wall St：小白 3 秒看懂）
    parts = ["{}{}".format(label, _dim_level(dims[key])) for key, label in _DIM_LABELS]
    dims["dim_summary"] = " · ".join(parts)
    return dims


# ---------- 主入口 ----------
def score_stock(row: dict) -> dict:
    row = dict(row)
    f = _fundamental(row); v = _valuation(row); g = _growth(row)
    c = _capital(row); rk = _risk(row)
    total = round(f + v + g + c + rk, 1)
    row.update(_snowflake(f, v, g, c, rk))

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


# ---------- 风格筛选（V2.0：仅保留 绩优 / 长线；移除短线，因不做技术分析） ----------
def screen_by_style(rows: list, style: str) -> list:
    scored = rescore_all(rows)
    def _key(r): return r.get("id") or r.get("code") or id(r)
    excluded = {_key(r) for r in scored if "排除" in r["rating"]}
    out = [r for r in scored if _key(r) not in excluded]

    if style in ("绩优", "quality"):
        # 偏好 AI 产业 + 主力长期流入
        pref = ["核心基础", "模型平台", "AI革命", "AI医药", "AI", "人工智能",
                "半导体", "芯片", "机器人", "医药", "软件", "云计算"]
        def q_key(r):
            base = r["total_score"]
            if _txt(r.get("ai_category")) in pref: base += 3
            if _txt(r.get("main_force_trend")) == "流入": base += 2
            return base
        out = sorted(out, key=q_key, reverse=True)

    elif style in ("长线", "long"):
        # 要求护城河 + 自由现金流转正 + 主力长期流入；持有5年以上
        def l_key(r):
            base = r["total_score"]
            if _txt(r.get("moat")) in ("明显", "强"): base += 5
            if _yn(r.get("fcf_positive")): base += 3
            if _txt(r.get("main_force_trend")) == "流入": base += 2
            return base
        out = [r for r in out if _txt(r.get("moat")) in ("明显", "强", "")]
        out = sorted(out, key=l_key, reverse=True)
        for r in out:
            r["expected_hold"] = "5年以上（长线持有）"

    # 短线模式已移除（V2.0：不做技术分析、不以短期涨跌为目标）
    return out


if __name__ == "__main__":
    demo = {"code": "sz002230", "name": "科大讯飞", "industry": "计算机/AI", "price": 39.73,
            "roe": 8, "roa": 5, "rev_growth_years": 3, "netprofit_growth_years": 3,
            "fcf_positive": 1, "debt_ratio": 40, "sector_type": "科技",
            "pe": 110, "pe_industry_avg": 60, "pb": 4.2, "peg": 3.5, "ev_ebitda": 25, "safety_margin": 10,
            "rd_increase": 1, "mkt_share_growth": 1, "industry_space": "大", "moat": "强", "profit_forecast_3y": 30,
            "ma_trend": "多头", "macd": "金叉", "kdj": "金叉", "rsi": 55, "volume": "温和放大", "volatility": "低",
            "main_fund_flow": "净流入", "northbound": "持平", "institution_change": "增仓", "main_force_trend": "流出",
            "market": "A股", "board": "主板", "ai_category": "模型平台", "ai_driven": 1, "research_signals": "产品进展;技术突破",
            "financial_risk": 0, "litigation": 0, "pledge_ratio": 0, "regulatory_penalty": 0, "goodwill_ratio": 2,
            "st_flag": 0, "delisting_risk": 0, "fraud_flag": 0, "consecutive_loss": 0,
            "major_holder_reduction": 0, "high_pledge": 0}
    print(score_stock(demo))
