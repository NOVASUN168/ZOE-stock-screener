# -*- coding: utf-8 -*-
"""
fetch_ai_data.py — V2.0 用 westock-data 抓取真实 AI 股票池，生成 seed_real_v2.json
数据源：腾讯自选股（westock-data skill，CLI 入口 scripts/index.js）
覆盖：A股(主板/创业板/科创板) + 港股(民营港股/红筹) + A+H，按 AI 四分类组织。
真实字段：price/pe/pb(quote)、roe/roa/debt_ratio/fcf(finance 三表)、
          main_force_trend(fund flow 的 MainNetFlow20D 主力长期趋势)、
          profit_forecast_3y(consensus netProfitYoy)。
V2.0 新增：market/board/ai_category/ai_driven/research_signals。
说明：pe_industry_avg 用 ai_category 参考值（教程已注明）；
      northbound 免费接口无逐股北向净买卖，默认中性(持平)。
"""
import os
import sys
import json
import time
import subprocess
import urllib.request

NODE = "C:/Users/zsgre/.workbuddy/binaries/node/versions/22.22.2/node.exe"
SK = "C:/Program Files/WorkBuddy/resources/app.asar.unpacked/resources/builtin-skills/westock-data/scripts/index.js"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "scripts", "seed_real_v2.json")

# 15 只真实 AI 股：(code, name, industry, sector_type, rd, mkt, space, moat, market, board, ai_category, research_signals)
STOCKS = [
    # —— 核心基础行业 ——
    ("sh688981", "中芯国际", "半导体/晶圆代工", "科技", 1, 1, "大", "中等", "A股", "科创板", "核心基础", "技术突破;客户采用;产业变化"),
    ("sh688256", "寒武纪",   "半导体/AI芯片",  "科技", 1, 1, "大", "强",   "A股", "科创板", "核心基础", "技术突破;产品进展;客户采用"),
    ("sh688041", "海光信息", "半导体/CPU",     "科技", 1, 1, "大", "强",   "A股", "科创板", "核心基础", "技术突破;客户采用"),
    ("sz300308", "中际旭创", "光模块",          "科技", 1, 1, "大", "强",   "A股", "创业板", "核心基础", "产品进展;客户采用;产业变化"),
    ("sh601138", "工业富联", "AI服务器",        "科技", 1, 1, "大", "强",   "A股", "主板",   "核心基础", "产品进展;客户采用;产业变化"),
    # —— 模型平台和软件生态行业 ——
    ("sz002230", "科大讯飞", "大模型/语音",     "科技", 1, 1, "大", "强",   "A股", "主板",   "模型平台", "产品进展;技术突破;客户采用"),
    ("sh688111", "金山办公", "AI办公软件",      "科技", 1, 1, "大", "中等", "A股", "科创板", "模型平台", "产品进展;客户采用"),
    ("hk00020",  "商汤-W",   "港股/视觉大模型", "科技", 1, 1, "大", "中等", "港股", "民营港股", "模型平台", "技术突破;产品进展;监管动态"),
    ("hk00700",  "腾讯控股", "港股/互联网AI",   "科技", 1, 1, "大", "强",   "港股", "红筹",   "模型平台", "产品进展;客户采用;产业变化"),
    ("sh601360", "三六零",   "安全/大模型",     "科技", 1, 1, "中", "中等", "A股", "主板",   "模型平台", "产品进展;技术突破"),
    # —— AI 革命性行业 ——
    ("sh601127", "赛力斯",   "智能车",          "制造业", 1, 1, "大", "强", "A股", "主板",   "AI革命", "产品进展;客户采用;产业变化"),
    ("sz300024", "机器人",   "工业机器人",       "制造业", 1, 1, "中", "中等", "A股", "创业板", "AI革命", "技术突破;产品进展"),
    ("sz002475", "立讯精密", "消费电子/AI终端", "科技", 1, 1, "大", "强", "A股", "主板",   "AI革命", "客户采用;产品进展;产业变化"),
    # —— AI 生物医药 ——
    ("sh603259", "药明康德", "CXO/AI制药",      "制造业", 1, 1, "大", "中等", "A+H", "主板", "AI医药", "客户采用;监管动态;产业变化"),
    ("sh688222", "成都先导", "AI药物发现",      "科技", 1, 1, "中", "中等", "A股", "科创板", "AI医药", "技术突破;产品进展"),
]

# AI 分类参考 PE 均值（经验值，仅用于估值比较；教程已注明）
PE_REF = {
    "核心基础": 55, "模型平台": 50, "AI革命": 35, "AI医药": 40,
}


def run(args):
    last = ""
    for _ in range(3):  # 重试：westock-data 偶发空输出/超时
        try:
            p = subprocess.run([NODE, SK] + args, capture_output=True, text=True,
                               timeout=90, encoding="utf-8", errors="replace")
            out = p.stdout
            if out and out.strip() and "__ERR__" not in out[:20]:
                return out
            last = out
        except Exception as e:
            last = f"__ERR__ {e}"
    return last


def parse_tables(text):
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
        hdr = None
        rows = []
        for ln in b:
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if hdr is None:
                hdr = cells
                continue
            if len(cells) == len(hdr):
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


# ---------- 新浪财经三表（主 ROE 数据源，quotes.sina.cn，稳定不封IP）----------
def _sina_report(paper_code, source, num=8):
    """新浪财报三表 JSON 接口（利润表 lrb / 资产负债表 fzb / 现金流量表 llb）。"""
    url = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"
    params = "paperCode=%s&source=%s&type=0&page=1&num=%d" % (paper_code, source, num)
    req = urllib.request.Request(url + "?" + params, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://quotes.sina.cn/",
    })
    d = json.loads(urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace"))
    rl = (d.get("result") or {}).get("data") or {}
    return rl.get("report_list") or {}


def _row_of(rl, prefer_annual=True):
    """取最新一期（优先年报 1231）的 {科目: 数值} 字典。"""
    periods = sorted(rl.keys(), reverse=True)
    if prefer_annual:
        for p in periods:
            if p.endswith("1231"):
                return p, {it.get("item_title"): fnum(it.get("item_value"))
                           for it in (rl[p].get("data") or [])}
    p = periods[0]
    return p, {it.get("item_title"): fnum(it.get("item_value"))
               for it in (rl[p].get("data") or [])}


def fetch_sina_financials(code):
    """新浪财报三表取 ROE/ROA/资产负债率/经营现金流。仅 A 股(sh/sz)；港股返回 None。"""
    if not code or code.startswith("hk"):
        return None
    digit = code[2:] if code[:2] in ("sh", "sz") else code
    paper = ("sh" if digit.startswith(("6", "9")) else "sz") + digit
    try:
        lrb = _sina_report(paper, "lrb", 8)
        time.sleep(0.4)
        fzb = _sina_report(paper, "fzb", 8)
        time.sleep(0.4)
        llb = _sina_report(paper, "llb", 4)
    except Exception:
        return None
    if not lrb or not fzb:
        return None

    np_period, np_row = _row_of(lrb, prefer_annual=True)
    fzb_period, fz_row = _row_of(fzb, prefer_annual=True)
    # 资产负债表的期次尽量与利润表一致（同口径 ROE）
    if fzb_period != np_period and np_period in fzb:
        fz_row = {it.get("item_title"): fnum(it.get("item_value"))
                  for it in (fzb[np_period].get("data") or [])}

    np_tsx = np_row.get("归属于母公司所有者的净利润")
    equity = fz_row.get("归属于母公司股东权益合计") or fz_row.get("所有者权益(或股东权益)合计")
    ta = fz_row.get("资产总计")
    tl = fz_row.get("负债合计")
    op = np_row.get("营业利润")
    cash = fz_row.get("货币资金")

    fcf = None
    if llb:
        lp = sorted(llb.keys(), reverse=True)[0]
        ll_row = {it.get("item_title"): fnum(it.get("item_value"))
                  for it in (llb[lp].get("data") or [])}
        fcf = ll_row.get("经营活动产生的现金流量净额")

    res = {"roe": None, "roa": None, "debt_ratio": None, "fcf_positive": 0,
           "op": op, "cash": cash, "tl": tl}
    if np_tsx is not None and equity:
        res["roe"] = round(np_tsx / equity * 100, 1)
    if np_tsx is not None and ta:
        res["roa"] = round(np_tsx / ta * 100, 1)
    if tl is not None and ta:
        res["debt_ratio"] = round(tl / ta * 100, 1)
    res["fcf_positive"] = 1 if (fcf is not None and fcf > 0) else 0
    return res


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def build_one(t):
    (code, name, industry, sector_type, rd, mkt, space, moat,
     market, board, ai_category, research_signals) = t
    d = dict(code=code, name=name, industry=industry, sector_type=sector_type,
             rd_increase=rd, mkt_share_growth=mkt, industry_space=space, moat=moat,
             market=market, board=board, ai_category=ai_category,
             ai_driven=1, research_signals=research_signals)
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
        d["_volume_ratio"] = fnum(r.get("volume_ratio"))
        d["_chg_60d"] = fnum(r.get("chg_60d"))
        d["_mktcap"] = fnum(r.get("total_market_cap"))
    else:
        d["price"] = d["pe"] = d["pb"] = None

    # 2) FINANCE — 主源：新浪财报三表(quotes.sina.cn，稳定不封IP)；兜底：westock-data finance
    sina = fetch_sina_financials(code)
    if sina and sina.get("roe") is not None:
        d["roe"] = sina["roe"]
        d["roa"] = sina.get("roa")
        d["debt_ratio"] = sina.get("debt_ratio")
        d["fcf_positive"] = sina.get("fcf_positive", 0)
        if sina.get("op") is not None and d.get("_mktcap"):
            tl = sina.get("tl"); cash = sina.get("cash")
            ev = d["_mktcap"] + (tl or 0) - (cash or 0)
            d["ev_ebitda"] = round(ev / sina["op"], 1) if sina["op"] else None
    else:
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
            if op_ttm and d.get("_mktcap"):
                ev = d["_mktcap"] + (tl or 0) - (cash or 0)
                d["ev_ebitda"] = round(ev / op_ttm, 1)
        d["fcf_positive"] = 0  # 默认 0；兜底路径现金流表为空则保持 0
        if xjll:
            fcf = fnum(xjll[0].get("NetOperateCashFlowTTM"))
            if fcf is not None and fcf > 0:
                d["fcf_positive"] = 1
        if "roe" not in d:
            d["roe"] = d["roa"] = d["debt_ratio"] = None
    if "ev_ebitda" not in d:
        d["ev_ebitda"] = None

    # 3) FUND FLOW（主力长期趋势 = 20日主力净流入）
    fl = first_table_with(run(["fund", "flow", code]), "MainNetFlow")
    if fl:
        r = fl[0]
        main = fnum(r.get("MainNetFlow"))
        main20 = fnum(r.get("MainNetFlow20D"))
        main10 = fnum(r.get("MainNetFlow10D"))
        if main20 is not None:
            d["main_force_trend"] = "流入" if main20 > 0 else ("流出" if main20 < 0 else "持平")
        else:
            d["main_force_trend"] = "持平"
        if main is not None:
            d["main_fund_flow"] = "净流入" if main > 0 else ("净流出" if main < 0 else "持平")
        else:
            d["main_fund_flow"] = "持平"
        if main10 is not None:
            d["institution_change"] = "增仓" if main10 > 0 else ("减仓" if main10 < 0 else "持平")
        else:
            d["institution_change"] = "持平"
    else:
        d["main_force_trend"] = "持平"
        d["main_fund_flow"] = "持平"
        d["institution_change"] = "持平"

    # 4) CONSENSUS
    cs = first_table_with(run(["consensus", code]), "netProfitYoy")
    if cs:
        yoys = [fnum(x.get("netProfitYoy")) for x in cs if fnum(x.get("netProfitYoy")) is not None]
        d["profit_forecast_3y"] = round(sum(yoys) / len(yoys), 1) if yoys else None
    else:
        d["profit_forecast_3y"] = None

    # 派生：peg / safety_margin / 增长年数 / pe_industry_avg
    pe = d.get("pe"); pf = d.get("profit_forecast_3y")
    d["peg"] = round(pe / pf, 2) if (pe and pf and pf > 0) else None
    d["safety_margin"] = round(clamp(100 * (1 - 0.03 * pe), 0, 40), 1) if pe else None
    d["pe_industry_avg"] = PE_REF.get(ai_category)
    if pf is not None:
        d["rev_growth_years"] = 3 if pf >= 15 else (2 if pf >= 8 else 1)
        d["netprofit_growth_years"] = d["rev_growth_years"]
    else:
        d["rev_growth_years"] = d["netprofit_growth_years"] = 1

    for k in list(d.keys()):
        if k.startswith("_"):
            del d[k]
    return d


def main():
    result = []
    for t in STOCKS:
        name = t[1]; code = t[0]
        print(f"抓取 {code} {name} ...", flush=True)
        try:
            d = build_one(t)
        except Exception as e:
            print(f"  ! {name} 出错: {e}", flush=True)
            d = dict(code=code, name=name, industry=t[2], sector_type=t[3],
                     rd_increase=t[4], mkt_share_growth=t[5], industry_space=t[6], moat=t[7],
                     market=t[8], board=t[9], ai_category=t[10], ai_driven=1,
                     research_signals=t[11])
        result.append(d)
        print(f"  -> price={d.get('price')} pe={d.get('pe')} roe={d.get('roe')} "
              f"debt={d.get('debt_ratio')} pf3y={d.get('profit_forecast_3y')} "
              f"mft={d.get('main_force_trend')} ai={d.get('ai_category')}", flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n完成：{len(result)} 只 -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
