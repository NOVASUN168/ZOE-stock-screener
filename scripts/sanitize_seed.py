# -*- coding: utf-8 -*-
"""sanitize_seed.py — 规整 seed_real.json 里的异常值，不重新抓接口。"""
import os, json, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import db

PATH = os.path.join(ROOT, "scripts", "seed_real.json")
with open(PATH, encoding="utf-8") as f:
    data = json.load(f)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

for d in data:
    name = d.get("name")
    # 1) 亏损股 PE<=0 → 视为未知（避免被算成"便宜"）
    pe = d.get("pe")
    if pe is not None and pe <= 0:
        print(f"  {name}: PE={pe} 为负，置为未知(None)")
        d["pe"] = None
    # 2) 一致预期增速异常（<=0 或 >60%，多为微利基数导致%）→ 置未知
    pf = d.get("profit_forecast_3y")
    if pf is not None and (pf <= 0 or pf > 60):
        print(f"  {name}: 三年利润增速={pf}% 异常，置为未知(None)")
        d["profit_forecast_3y"] = None
        d["rev_growth_years"] = 1
        d["netprofit_growth_years"] = 1
        d["peg"] = None
    # 3) 重算 peg / safety_margin（依赖清洗后的 pe / pf）
    pe = d.get("pe"); pf = d.get("profit_forecast_3y")
    d["peg"] = round(pe / pf, 2) if (pe and pf and pf > 0) else None
    d["safety_margin"] = round(clamp(100 * (1 - 0.03 * pe), 0, 40), 1) if pe else None
    # 4) 字段完整性：补齐缺失的 FIELDS 为 None
    for k in db.FIELDS:
        d.setdefault(k, None)

with open(PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"已规整并写回 {len(data)} 只 -> {PATH}")
# 抽查
for d in data[:3]:
    print(f"  {d['name']}: price={d['price']} pe={d['pe']} roe={d['roe']} debt={d['debt_ratio']} "
          f"pf3y={d['profit_forecast_3y']} peg={d['peg']} ma={d['ma_trend']} mf={d['main_fund_flow']}")
