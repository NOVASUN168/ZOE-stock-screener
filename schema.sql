-- =====================================================================
-- 股票基金筛选系统 · 规范建表脚本（schema.sql）— V2.0 AI产业聚焦版
-- 说明：本文件是 stocks 表的“单一事实来源”(single source of truth)。
--       任何改表结构都必须同步修改本文件，并用 scripts/init_db.py 验证。
--       字段顺序/类型与 scripts/db.py 的 FIELDS 保持一致。
-- V2.0 变化：
--   新增：market(市场)/board(板块)/ai_category(AI四分类)/ai_driven(是否AI驱动)
--         /research_signals(信息来源信号)/main_force_trend(主力长期趋势)
--   移除：target_price/buy_point/stop_loss/take_profit/expected_return（不承诺收益率）
--   技术面字段(ma_trend等)保留列但【不参与评分】，遵循“不做技术分析”
-- =====================================================================

-- ---------- 标的基础库（多因子原始输入 + 计算产物） ----------
CREATE TABLE IF NOT EXISTS stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at TEXT,

    -- 基础
    code TEXT,
    name TEXT,
    industry TEXT,
    price REAL,

    -- 基本面 35%
    roe REAL,
    roa REAL,
    rev_growth_years REAL,
    netprofit_growth_years REAL,
    fcf_positive INTEGER DEFAULT 0,
    debt_ratio REAL,
    sector_type TEXT,

    -- 估值 20%
    pe REAL,
    pe_industry_avg REAL,
    pb REAL,
    peg REAL,
    ev_ebitda REAL,
    safety_margin REAL,

    -- 成长 25%（含护城河核心逻辑）
    rd_increase INTEGER DEFAULT 0,
    mkt_share_growth INTEGER DEFAULT 0,
    industry_space TEXT,
    moat TEXT,
    profit_forecast_3y REAL,

    -- 技术（V2.0 保留字段但【不参与评分】，遵循“不做技术分析”）
    ma_trend TEXT,
    macd TEXT,
    kdj TEXT,
    rsi REAL,
    volume TEXT,
    volatility TEXT,            -- 低/中/高（分类，必须 TEXT）

    -- 资金（V2.0 聚焦主力长期趋势，过滤散户/短期游资）
    main_fund_flow TEXT,        -- 短期主力净流入（仅供参考展示）
    northbound TEXT,            -- 北向（长期机构信号）
    institution_change TEXT,    -- 机构动向（长期机构信号）
    main_force_trend TEXT,      -- 主力长期趋势：流入/流出/持平（由20日主力净流入判定）

    -- 范围与 AI 分类（V2.0 新增）
    market TEXT,                -- A股 / 港股 / A+H
    board TEXT,                 -- 主板/创业板/科创板/北交所/H股/红筹/民营港股
    ai_category TEXT,           -- 核心基础/模型平台/AI革命/AI医药
    ai_driven INTEGER DEFAULT 1,-- 1=AI驱动 0=非AI（0则硬排除）
    research_signals TEXT,      -- 信息来源信号：公告;产品进展;技术突破;客户采用;产业变化;监管动态

    -- 软风险 5%（软因子，参与评分扣分）
    financial_risk INTEGER DEFAULT 0,
    litigation INTEGER DEFAULT 0,
    pledge_ratio REAL,
    regulatory_penalty INTEGER DEFAULT 0,
    goodwill_ratio REAL,

    -- 硬过滤（一票否决）
    st_flag INTEGER DEFAULT 0,
    delisting_risk INTEGER DEFAULT 0,
    fraud_flag INTEGER DEFAULT 0,
    consecutive_loss INTEGER DEFAULT 0,
    major_holder_reduction INTEGER DEFAULT 0,
    high_pledge INTEGER DEFAULT 0,

    -- 计算产物（由 scoring.score_stock 回写）
    total_score REAL,
    rating TEXT,
    recommend_index TEXT,
    risk_flags TEXT,
    reasonable_valuation TEXT,  -- 估值看法（定性，非目标价）
    suggested_position TEXT,    -- 配置视图：核心配置/卫星配置/观察/回避
    expected_hold TEXT,         -- 持有期（长期，无短线）
    advantages TEXT,
    risks_text TEXT,
    recommend_reasons TEXT,
    core_competence TEXT,       -- 核心竞争力/护城河摘要
    long_term_thesis TEXT       -- 长期研究逻辑
);

-- ---------- 组合表（稳健 / 成长 / 激进） ----------
CREATE TABLE IF NOT EXISTS portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ptype TEXT,            -- robust / growth / aggressive
    name TEXT,
    stock_ids TEXT,        -- JSON list of stock id
    alloc TEXT,            -- JSON dict id->pct
    note TEXT,
    created_at TEXT
);

-- ---------- 预警规则表（用户自建提醒） ----------
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER,
    atype TEXT,            -- score_drop / price_up / price_down / risk_trigger
    threshold REAL,        -- 数值阈值（score_drop=评分; price_up/down=价格）
    note TEXT,
    active INTEGER DEFAULT 1,
    triggered INTEGER DEFAULT 0,
    triggered_at TEXT,
    created_at TEXT
);

-- ---------- 持仓监控表（自选 / 观察池） ----------
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER,
    note TEXT,
    created_at TEXT
);

-- ---------- 系统配置表（密钥/Webhook 走这里，绝不入库外文件） ----------
-- 铁律#4：API Key·Webhook 密钥走 WECOM_CRM_WEBHOOK 环境变量或本表，禁止写进代码/提交。
CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_stocks_score ON stocks(total_score);
CREATE INDEX IF NOT EXISTS idx_alerts_stock ON alerts(stock_id);
CREATE INDEX IF NOT EXISTS idx_watch_stock ON watchlist(stock_id);
