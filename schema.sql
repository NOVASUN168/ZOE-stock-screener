-- =====================================================================
-- 股票基金筛选系统 · 规范建表脚本（schema.sql）
-- 说明：本文件是 stocks 表的“单一事实来源”(single source of truth)。
--       任何改表结构都必须同步修改本文件，并用 scripts/init_db.py 验证。
--       字段顺序/类型与 scripts/db.py 的 FIELDS 保持一致。
-- 注意：volatility 在业务里是“低/中/高”分类值，必须是 TEXT，不能是 REAL。
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

    -- 基本面 30%
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

    -- 成长 20%
    rd_increase INTEGER DEFAULT 0,
    mkt_share_growth INTEGER DEFAULT 0,
    industry_space TEXT,
    moat TEXT,
    profit_forecast_3y REAL,

    -- 技术 15%
    ma_trend TEXT,
    macd TEXT,
    kdj TEXT,
    rsi REAL,
    volume TEXT,
    volatility TEXT,            -- 低/中/高（分类，必须 TEXT）

    -- 资金 10%
    main_fund_flow TEXT,
    northbound TEXT,
    institution_change TEXT,

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
    target_price REAL,
    reasonable_valuation TEXT,
    buy_point TEXT,
    stop_loss REAL,
    take_profit REAL,
    suggested_position TEXT,
    expected_return TEXT,
    expected_hold TEXT,
    advantages TEXT,
    risks_text TEXT,
    recommend_reasons TEXT
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
