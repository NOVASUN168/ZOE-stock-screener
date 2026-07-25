# -*- coding: utf-8 -*-
"""
fetch_real_data.py — 用 westock-data 抓取 15 只 A 股真实数据，生成 seed_real.json
数据源：腾讯自选股（westock-data skill，CLI 入口 scripts/index.js）
真实字段：price/pe/pb(quote)、roe/roa/debt_ratio/fcf( finance 三表计算)、
          ma/macd/kdj/rsi/vol/volatility(technical 推导)、
          main_fund_flow/institution_change(fund flow)、
          profit_forecast_3y / peg(consensus 推导)
说明：pe_industry_avg 用行业经验参考值（非逐股计算，已在教程注明）；
      northbound/st_flag/pledge_ratio/goodwill_ratio 等逐股深度风险字段未自动抓取（默认中性/安全），
      如需可后续用 westock-data risk 命令补齐。
"""
import os
import sys
import json
import subprocess
import re

NODE = "C:/Users/zsgre/.workbuddy/binaries/node/versions/22.22.2/node.exe"
SK = "C:/Program Files/WorkBuddy/resources/app.asar.unpacked/resources/builtin-skills/westock-data/scripts/index.js"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "scripts", "seed_real.json")

# 15 只 A 股（代码 / 名称 / 行业标签 / sector_type / 定性护城河等公开常识）
STOCKS = [
    # code,        name,       industry,            sector_type, rd, mkt, space, moat
    ("sh600519", "贵州茅台",   "消费/白酒",          "制造业", 0, 1, "大", "明显"),
    ("sz300750", "宁德时代",   "新能源/电池",        "制造业", 1, 1, "大", "强"),
    ("sz002594", "比亚迪",     "新能源/汽车",        "制造业", 1, 1, "大", "强"),
    ("sh600036", "招商银行",   "金融/银行",          "金融",   0, 0, "中", "强"),
    ("sh600900", "长江电力",   "公用事业/电力",      "制造业", 0, 0, "中", "明显"),
    ("sh603259", "药明康德",   "医药/CRO",           "制造业", 1, 1, "大", "中等"),
    ("sz002475", "立讯精密",   "电子/消费电子",      "科技",   1, 1, "大", "强"),
    ("sh601012", "隆基绿能",   "新能源/光伏",        "制造业", 1, 0, "中", "中等"),
    ("sh688981", "中芯国际",   "半导体",             "科技",   1, 1, "大", "中等"),
    ("sz002415", "海康威视",   "电子/安防",          "科技",   1, 1, "大", "强"),
    ("sz000333", "美的集团",   "家电",               "制造业", 1, 1, "中", "强"),
    ("sh601766", "中国中车",   "高端制造/轨交",      "制造业", 0, 0, "中", "明显"),
    ("sz300124", "汇川技术",   "高端制造/工控",      "制造业", 1, 1, "大", "强"),
    ("sh600031", "三一重工",   "高端制造/工程机械",  "制造业", 1, 1, "中", "中等"),
    ("sh601318", "中国平安",   "金融/保险",          "金融",   0, 0, "中", "强"),
]

# 行业参考 PE 均值（经验值，非逐股计算）— 仅用于估值比较
PE_INDUSTRY = {
    "消费/白酒": 28, "新能源/电池": 30, "新能源/汽车": 25, "金融/银行": 7,
    "公用事业/电力": 18, "医药/CRO": 30, "电子/消费电子": 25, "新能源/光伏": 20,
    "半导体": 55, "电子/安防": 22, "家电": 14, "高端制造/轨交": 15,
    "高端制造/工控": 32, "高端制造/工程机械": 18, "金融/保险": 10,
}


def run(args):
    try:
        p = subprocess.run([NODE, SK] + args, capture_output=True, text=True,
                           timeout=90, encoding="utf-8", errors="replace")
        return p.stdout
    except Exception as e:
        return f"__ERR__ {e}"


def parse_tables(text):
    """返回 [(headers, [rowdict,...]), ...]"""
    lines = text.splitlines()
    blocks = []
    cur = None
    for ln in lines:
        if ln.strip().startswith("|"):
            if cur is None:
                cur = []
            cur.append(ln.strip())
        else:
            if cur:
                blocks.append(cur); cur = None
    if cur:
        blocks.append(cur)
    out = []
    for b in blocks:
        # 找表头（第一个含 | 的行），跳过分隔行
        hdr = None
        rows = []
        for i, ln in enumerate(b):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if hdr is None:
                hdr = cells
                continue
            if set(cells) <= {"", "-", ":"}:
                continue
            if len(cells) == len(hdr):
                # 跳过 Markdown 分隔行（|---|---|），其字符只含 - 和 :
                if set("".join(cells)) <= {"-", ":"}:
                    continue
                rows.append(dict(zip(hdr, cells)))
        if hdr and rows:
            out.append((hdr, rows))
    return out


def fnum(s):
    try:
        return float(str(s).replace(",", ""))
    except Exception:
        return None


def first_table_with(text, key_substr):
    for hdr, rows in parse_tables(text):
        if any(key_substr in h for h in hdr):
            return rows
    return None


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def build_one(code, name, industry, sector_type, rd, mkt, space, moat):
    d = dict(code=code, name=name, industry=industry, sector_type=sector_type,
             rd_increase=rd, mkt_share_growth=mkt, industry_space=space, moat=moat)
    # 默认中性/安全
    for k in ("st_flag", "delisting_risk", "fraud_flag", "consecutive_loss",
              "major_holder_reduction", "high_pledge", "financial_risk",
              "litigation", "regulatory_penalty"):
        d[k] = 0
    d["northbound"] = "持平"  # 免费接口无逐股北向净买卖，默认中性

    # 1) QUOTE
    q = first_table_with(run(["quote", code]), "price")
    if q:
        r = q[0]
        d["price"] = fnum(r.get("price"))
        d["pe"] = fnum(r.get("pe_ratio"))
        d["pb"] = fnum(r.get("pb_ratio"))
        vr = fnum(r.get("volume_ratio"))
        d["_volume_ratio"] = vr
        d["_chg_60d"] = fnum(r.get("chg_60d"))
        d["_mktcap"] = fnum(r.get("total_market_cap"))
    else:
        d["price"] = d["pe"] = d["pb"] = None

    # 2) FINANCE
    lrb = first_table_with(run(["finance", code]), "NPParentCompanyOwnersTTM")
    zcfz = first_table_with(run(["finance", code]), "TotalLiability")
    xjll = first_table_with(run(["finance", code]), "NetOperateCashFlowTTM")
    np_ttm = fnum(lrb[0].get("NPParentCompanyOwnersTTM")) if lrb else None
    op_ttm = fnum(lrb[0].get("OperatingProfitTTM")) if lrb else None
    if zcfz:
        z = zcfz[0]
        eq = fnum(z.get("TotalShareholderEquity"))
        tl = fnum(z.get("TotalLiability"))
        tca = fnum(z.get("TotalCurrentAssets"))
        tnca = fnum(z.get("TotalNonCurrentAssets"))
        cash = fnum(z.get("CashEquivalents"))
        ta = (tca + tnca) if (tca is not None and tnca is not None) else None
        if np_ttm is not None and eq:
            d["roe"] = round(np_ttm / eq * 100, 1)
        if np_ttm is not None and ta:
            d["roa"] = round(np_ttm / ta * 100, 1)
        if tl is not None and ta:
            d["debt_ratio"] = round(tl / ta * 100, 1)
        # EV/EBITDA 代理 = EV / OperatingProfitTTM
        if op_ttm and d.get("_mktcap"):
            ev = d["_mktcap"] + (tl or 0) - (cash or 0)
            d["ev_ebitda"] = round(ev / op_ttm, 1)
    if xjll:
        fcf = fnum(xjll[0].get("NetOperateCashFlowTTM"))
        d["fcf_positive"] = 1 if (fcf is not None and fcf > 0) else 0
    if "roe" not in d:
        d["roe"] = d["roa"] = d["debt_ratio"] = None
    if "ev_ebitda" not in d:
        d["ev_ebitda"] = None

    # 3) TECHNICAL
    t = first_table_with(run(["technical", code, "--group", "ma,macd,kdj,rsi"]), "closePrice")
    if t:
        r = t[0]
        ma5, ma20, ma60 = fnum(r.get("ma.MA_5")), fnum(r.get("ma.MA_20")), fnum(r.get("ma.MA_60"))
        if None not in (ma5, ma20, ma60):
            if ma5 > ma20 > ma60:
                d["ma_trend"] = "多头"
            elif ma5 < ma20 < ma60:
                d["ma_trend"] = "空头"
            else:
                d["ma_trend"] = "震荡"
        else:
            d["ma_trend"] = "震荡"
        dif, dea = fnum(r.get("macd.DIF")), fnum(r.get("macd.DEA"))
        d["macd"] = "金叉" if (dif is not None and dea is not None and dif > dea) else "死叉"
        kk, dd = fnum(r.get("kdj.KDJ_K")), fnum(r.get("kdj.KDJ_D"))
        if kk is not None and dd is not None:
            d["kdj"] = "金叉" if (kk > dd and kk > 50) else ("死叉" if kk < dd else "持平")
        else:
            d["kdj"] = "持平"
        d["rsi"] = fnum(r.get("rsi.RSI_6")) or fnum(r.get("rsi.RSI_12"))
    else:
        d["ma_trend"] = d["macd"] = d["kdj"] = "震荡" if False else "持平"
        d["rsi"] = None

    # volume / volatility 由 quote 推导
    vr = d.pop("_volume_ratio", None)
    d["volume"] = ("放量" if (vr and vr > 1.2) else ("温和放大" if (vr and vr >= 0.8) else "萎缩")) if vr is not None else "持平"
    c60 = d.pop("_chg_60d", None)
    d["volatility"] = ("低" if (c60 is not None and abs(c60) < 10) else ("中" if (c60 is not None and abs(c60) < 25) else "高")) if c60 is not None else "中"

    # 4) FUND FLOW
    fl = first_table_with(run(["fund", "flow", code]), "MainNetFlow")
    if fl:
        r = fl[0]
        main = fnum(r.get("MainNetFlow"))
        main20 = fnum(r.get("MainNetFlow20D"))
        if main is not None:
            d["main_fund_flow"] = "净流入" if main > 0 else ("净流出" if main < 0 else "流入")
        else:
            d["main_fund_flow"] = "持平"
        if main20 is not None:
            d["institution_change"] = "增仓" if main20 > 0 else ("减仓" if main20 < 0 else "持平")
        else:
            d["institution_change"] = "持平"
    else:
        d["main_fund_flow"] = "持平"
        d["institution_change"] = "持平"

    # 5) CONSENSUS
    cs = first_table_with(run(["consensus", code]), "netProfitYoy")
    if cs:
        yoys = [fnum(x.get("netProfitYoy")) for x in cs if fnum(x.get("netProfitYoy")) is not None]
        if yoys:
            d["profit_forecast_3y"] = round(sum(yoys) / len(yoys), 1)
        else:
            d["profit_forecast_3y"] = None
    else:
        d["profit_forecast_3y"] = None

    # 派生：peg / safety_margin / 增长年数 / pe_industry_avg
    pe = d.get("pe"); pf = d.get("profit_forecast_3y")
    d["peg"] = round(pe / pf, 2) if (pe and pf and pf > 0) else None
    d["safety_margin"] = round(clamp(100 * (1 - 0.03 * pe), 0, 40), 1) if pe else None
    d["pe_industry_avg"] = PE_INDUSTRY.get(industry)
    if pf is not None:
        d["rev_growth_years"] = 3 if pf >= 15 else (2 if pf >= 8 else 1)
        d["netprofit_growth_years"] = d["rev_growth_years"]
    else:
        d["rev_growth_years"] = d["netprofit_growth_years"] = 1

    # 清理内部临时字段
    for k in list(d.keys()):
        if k.startswith("_"):
            del d[k]
    return d


def main():
    result = []
    for code, name, industry, st, rd, mkt, space, moat in STOCKS:
        print(f"抓取 {code} {name} ...", flush=True)
        try:
            d = build_one(code, name, industry, st, rd, mkt, space, moat)
        except Exception as e:
            print(f"  ! {name} 出错: {e}", flush=True)
            d = dict(code=code, name=name, industry=industry, sector_type=st,
                     rd_increase=rd, mkt_share_growth=mkt, industry_space=space, moat=moat)
        result.append(d)
        print(f"  -> price={d.get('price')} pe={d.get('pe')} roe={d.get('roe')} "
              f"debt={d.get('debt_ratio')} pf3y={d.get('profit_forecast_3y')} "
              f"ma={d.get('ma_trend')} mf={d.get('main_fund_flow')}", flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n完成：{len(result)} 只 -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
