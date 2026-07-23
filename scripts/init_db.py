# -*- coding: utf-8 -*-
"""
stock-screener · 规范建库脚本（init_db.py）
铁律#5：改表结构必须同步 schema.sql，并用本脚本做本地验证。
用法：
    python scripts/init_db.py                # 确保表结构存在（不覆盖已有数据）
    python scripts/init_db.py --seed         # 清空并重新播种示例数据
    python scripts/init_db.py --db my.db     # 指定数据库路径
    python scripts/init_db.py --force        # 删除旧库重建（危险，仅基线用）
依赖：仅 Python 标准库 + 同目录 db.py / scoring.py / schema.sql
"""
import os
import sys
import sqlite3
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import db
import scoring

SCHEMA = os.path.join(ROOT, "schema.sql")
DEFAULT_DB = os.path.join(ROOT, "data", "screener.db")

# ---------- 示例种子（仅原始输入字段；评分由 scoring 计算） ----------
SEED = [
    dict(code="sh600519", name="贵州茅台", industry="消费/白酒", price=1500, roe=30, roa=22,
         rev_growth_years=3, netprofit_growth_years=3, fcf_positive=1, debt_ratio=20, sector_type="制造业",
         pe=25, pe_industry_avg=30, pb=8, peg=1.2, ev_ebitda=18, safety_margin=25,
         rd_increase=1, mkt_share_growth=1, industry_space="大", moat="明显", profit_forecast_3y=15,
         ma_trend="多头", macd="金叉", kdj="金叉", rsi=55, volume="温和放大", volatility="低",
         main_fund_flow="净流入", northbound="增持", institution_change="增仓",
         financial_risk=0, litigation=0, pledge_ratio=0, regulatory_penalty=0, goodwill_ratio=2),
    dict(code="sz300750", name="宁德时代", industry="新能源/电池", price=180, roe=22, roa=10,
         rev_growth_years=3, netprofit_growth_years=3, fcf_positive=1, debt_ratio=55, sector_type="制造业",
         pe=28, pe_industry_avg=35, pb=5, peg=1.1, ev_ebitda=16, safety_margin=30,
         rd_increase=1, mkt_share_growth=1, industry_space="大", moat="强", profit_forecast_3y=25,
         ma_trend="多头", macd="金叉", kdj="金叉", rsi=58, volume="放量", volatility="中",
         main_fund_flow="净流入", northbound="增持", institution_change="增仓",
         financial_risk=0, litigation=0, pledge_ratio=0, regulatory_penalty=0, goodwill_ratio=3),
    dict(code="sz002594", name="比亚迪", industry="新能源/汽车", price=240, roe=18, roa=6,
         rev_growth_years=3, netprofit_growth_years=3, fcf_positive=1, debt_ratio=65, sector_type="制造业",
         pe=22, pe_industry_avg=28, pb=4, peg=1.0, ev_ebitda=14, safety_margin=28,
         rd_increase=1, mkt_share_growth=1, industry_space="大", moat="强", profit_forecast_3y=20,
         ma_trend="多头", macd="红柱", kdj="金叉", rsi=60, volume="放量", volatility="中",
         main_fund_flow="净流入", northbound="持平", institution_change="增仓",
         financial_risk=0, litigation=0, pledge_ratio=0, regulatory_penalty=0, goodwill_ratio=4),
    dict(code="sh600036", name="招商银行", industry="金融/银行", price=35, roe=16, roa=1.2,
         rev_growth_years=3, netprofit_growth_years=3, fcf_positive=1, debt_ratio=92, sector_type="金融",
         pe=6, pe_industry_avg=7, pb=0.9, peg=1.3, ev_ebitda=None, safety_margin=35,
         rd_increase=0, mkt_share_growth=0, industry_space="中", moat="强", profit_forecast_3y=8,
         ma_trend="多头", macd="金叉", kdj="持平", rsi=52, volume="持平", volatility="低",
         main_fund_flow="流入", northbound="增持", institution_change="持平",
         financial_risk=0, litigation=0, pledge_ratio=0, regulatory_penalty=0, goodwill_ratio=1),
    dict(code="sh600900", name="长江电力", industry="公用事业/电力", price=28, roe=15, roa=8,
         rev_growth_years=3, netprofit_growth_years=3, fcf_positive=1, debt_ratio=55, sector_type="制造业",
         pe=20, pe_industry_avg=22, pb=2.8, peg=1.2, ev_ebitda=12, safety_margin=30,
         rd_increase=0, mkt_share_growth=0, industry_space="中", moat="明显", profit_forecast_3y=6,
         ma_trend="多头", macd="红柱", kdj="持平", rsi=50, volume="持平", volatility="低",
         main_fund_flow="流入", northbound="增持", institution_change="增仓",
         financial_risk=0, litigation=0, pledge_ratio=0, regulatory_penalty=0, goodwill_ratio=1),
    dict(code="sh603259", name="药明康德", industry="医药/CRO", price=70, roe=20, roa=12,
         rev_growth_years=2, netprofit_growth_years=2, fcf_positive=1, debt_ratio=30, sector_type="科技",
         pe=25, pe_industry_avg=30, pb=4, peg=1.4, ev_ebitda=15, safety_margin=25,
         rd_increase=1, mkt_share_growth=1, industry_space="大", moat="中等", profit_forecast_3y=18,
         ma_trend="震荡", macd="死叉", kdj="死叉", rsi=45, volume="萎缩", volatility="高",
         main_fund_flow="净流出", northbound="减持", institution_change="减仓",
         financial_risk=0, litigation=0, pledge_ratio=0, regulatory_penalty=0, goodwill_ratio=5),
    dict(code="sz002475", name="立讯精密", industry="电子/消费电子", price=35, roe=20, roa=10,
         rev_growth_years=3, netprofit_growth_years=3, fcf_positive=1, debt_ratio=50, sector_type="科技",
         pe=22, pe_industry_avg=25, pb=4, peg=1.2, ev_ebitda=14, safety_margin=28,
         rd_increase=1, mkt_share_growth=1, industry_space="大", moat="强", profit_forecast_3y=20,
         ma_trend="多头", macd="金叉", kdj="金叉", rsi=55, volume="温和放大", volatility="中",
         main_fund_flow="净流入", northbound="增持", institution_change="增仓",
         financial_risk=0, litigation=0, pledge_ratio=0, regulatory_penalty=0, goodwill_ratio=3),
    dict(code="sh601012", name="隆基绿能", industry="新能源/光伏", price=20, roe=12, roa=5,
         rev_growth_years=1, netprofit_growth_years=1, fcf_positive=0, debt_ratio=60, sector_type="制造业",
         pe=18, pe_industry_avg=20, pb=2, peg=1.6, ev_ebitda=16, safety_margin=20,
         rd_increase=1, mkt_share_growth=0, industry_space="中", moat="中等", profit_forecast_3y=10,
         ma_trend="空头", macd="死叉", kdj="死叉", rsi=35, volume="萎缩", volatility="高",
         main_fund_flow="净流出", northbound="减持", institution_change="减仓",
         financial_risk=0, litigation=0, pledge_ratio=0, regulatory_penalty=0, goodwill_ratio=6),
    dict(code="sh688981", name="中芯国际", industry="半导体", price=55, roe=8, roa=4,
         rev_growth_years=3, netprofit_growth_years=2, fcf_positive=0, debt_ratio=40, sector_type="科技",
         pe=60, pe_industry_avg=55, pb=3, peg=1.5, ev_ebitda=25, safety_margin=15,
         rd_increase=1, mkt_share_growth=1, industry_space="大", moat="中等", profit_forecast_3y=25,
         ma_trend="震荡", macd="持平", kdj="金叉", rsi=50, volume="温和放大", volatility="高",
         main_fund_flow="流入", northbound="增持", institution_change="增仓",
         financial_risk=0, litigation=0, pledge_ratio=0, regulatory_penalty=0, goodwill_ratio=4),
    dict(code="sz002415", name="海康威视", industry="电子/安防", price=30, roe=22, roa=14,
         rev_growth_years=3, netprofit_growth_years=3, fcf_positive=1, debt_ratio=35, sector_type="科技",
         pe=20, pe_industry_avg=22, pb=4, peg=1.1, ev_ebitda=13, safety_margin=30,
         rd_increase=1, mkt_share_growth=1, industry_space="大", moat="强", profit_forecast_3y=15,
         ma_trend="多头", macd="金叉", kdj="金叉", rsi=55, volume="温和放大", volatility="中",
         main_fund_flow="净流入", northbound="增持", institution_change="增仓",
         financial_risk=0, litigation=0, pledge_ratio=0, regulatory_penalty=0, goodwill_ratio=2),
    dict(code="sz000333", name="美的集团", industry="家电", price=65, roe=22, roa=8,
         rev_growth_years=3, netprofit_growth_years=3, fcf_positive=1, debt_ratio=62, sector_type="制造业",
         pe=12, pe_industry_avg=14, pb=2.6, peg=1.0, ev_ebitda=10, safety_margin=32,
         rd_increase=1, mkt_share_growth=1, industry_space="中", moat="强", profit_forecast_3y=12,
         ma_trend="多头", macd="金叉", kdj="持平", rsi=53, volume="持平", volatility="低",
         main_fund_flow="流入", northbound="增持", institution_change="增仓",
         financial_risk=0, litigation=0, pledge_ratio=0, regulatory_penalty=0, goodwill_ratio=3),
    dict(code="sh601766", name="中国中车", industry="高端制造/轨交", price=7, roe=10, roa=5,
         rev_growth_years=3, netprofit_growth_years=3, fcf_positive=1, debt_ratio=58, sector_type="制造业",
         pe=14, pe_industry_avg=15, pb=1.2, peg=1.2, ev_ebitda=9, safety_margin=30,
         rd_increase=0, mkt_share_growth=0, industry_space="中", moat="明显", profit_forecast_3y=8,
         ma_trend="多头", macd="红柱", kdj="持平", rsi=50, volume="持平", volatility="低",
         main_fund_flow="流入", northbound="持平", institution_change="增仓",
         financial_risk=0, litigation=0, pledge_ratio=0, regulatory_penalty=0, goodwill_ratio=2),
    dict(code="sz300124", name="汇川技术", industry="高端制造/工控", price=60, roe=23, roa=14,
         rev_growth_years=3, netprofit_growth_years=3, fcf_positive=1, debt_ratio=45, sector_type="制造业",
         pe=30, pe_industry_avg=32, pb=6, peg=1.1, ev_ebitda=15, safety_margin=25,
         rd_increase=1, mkt_share_growth=1, industry_space="大", moat="强", profit_forecast_3y=22,
         ma_trend="多头", macd="金叉", kdj="金叉", rsi=57, volume="温和放大", volatility="中",
         main_fund_flow="净流入", northbound="增持", institution_change="增仓",
         financial_risk=0, litigation=0, pledge_ratio=0, regulatory_penalty=0, goodwill_ratio=3),
    dict(code="sh600031", name="三一重工", industry="高端制造/工程机械", price=17, roe=16, roa=8,
         rev_growth_years=2, netprofit_growth_years=2, fcf_positive=1, debt_ratio=50, sector_type="制造业",
         pe=16, pe_industry_avg=18, pb=1.8, peg=1.2, ev_ebitda=11, safety_margin=28,
         rd_increase=1, mkt_share_growth=1, industry_space="中", moat="中等", profit_forecast_3y=12,
         ma_trend="震荡", macd="红柱", kdj="金叉", rsi=48, volume="温和放大", volatility="中",
         main_fund_flow="流入", northbound="持平", institution_change="增仓",
         financial_risk=0, litigation=0, pledge_ratio=0, regulatory_penalty=0, goodwill_ratio=4),
    # ---- 风险样本：演示一票否决 + 风控提醒 ----
    dict(code="sh600999", name="ST某某(风险样本)", industry="其它", price=5, roe=-5, roa=-3,
         rev_growth_years=0, netprofit_growth_years=0, fcf_positive=0, debt_ratio=85, sector_type="制造业",
         pe=None, pe_industry_avg=None, pb=3, peg=None, ev_ebitda=None, safety_margin=None,
         rd_increase=0, mkt_share_growth=0, industry_space="小", moat="无", profit_forecast_3y=None,
         ma_trend="空头", macd="死叉", kdj="死叉", rsi=20, volume="萎缩", volatility="高",
         main_fund_flow="净流出", northbound="减持", institution_change="减仓",
         financial_risk=1, litigation=1, pledge_ratio=60, regulatory_penalty=1, goodwill_ratio=45,
         st_flag=1, delisting_risk=1, fraud_flag=0, consecutive_loss=1, major_holder_reduction=1, high_pledge=1),
]


def build_schema(conn):
    with open(SCHEMA, "r", encoding="utf-8") as f:
        sql = f.read()
    # sqlite3 支持一次执行多条语句
    conn.executescript(sql)
    conn.commit()


def seed(conn):
    for d in SEED:
        sid = db.create(conn, d)
        scored = scoring.score_stock(d)
        db.patch_computed(conn, sid, {k: scored.get(k) for k in db.COMPUTED_KEYS})
    print(f"  播种 {len(SEED)} 只示例（含 1 只风险样本）")


def init_config(conn):
    defaults = {
        "risk_score_floor": "70",       # 评分预警默认阈值
        "max_drawdown_limit": "15",      # 组合最大回撤红线(%)
        "single_position_cap": "20",     # 单一标的仓位上限(%)
        "wecom_crm_webhook": "",         # 留空；运行时由环境变量或本表注入，绝不提交
    }
    for k, v in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO system_config(key, value, updated_at) VALUES(?,?,datetime('now','localtime'))",
            (k, v))
    conn.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--seed", action="store_true", help="清空并重新播种示例数据")
    ap.add_argument("--force", action="store_true", help="删除旧库重建（危险）")
    a = ap.parse_args()

    if a.force and os.path.exists(a.db):
        os.remove(a.db)
        print("  已删除旧库，重建中…")

    os.makedirs(os.path.dirname(a.db), exist_ok=True)
    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    print(f"建库/校验 schema：{a.db}")
    build_schema(conn)
    print("  schema OK（来自 schema.sql）")

    n = conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
    if a.seed or n == 0:
        if n > 0:
            conn.execute("DELETE FROM stocks")
            conn.commit()
        seed(conn)
    else:
        print(f"   已有 {n} 只股票，跳过播种（用 --seed 重置）")

    init_config(conn)
    print("  system_config 默认值已就绪")
    print("完成。总行数：", conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0])
    conn.close()


if __name__ == "__main__":
    main()
