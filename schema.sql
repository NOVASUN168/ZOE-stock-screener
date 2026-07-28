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

    -- 资金流/游资（V2.1 新增：20日主力净流入、游资参与度，供数据驱动筛选）
    main_inflow_20d REAL,      -- 20日主力资金净流入（万元，可负）
    main_outflow_20d REAL,     -- 20日主力资金净流出（万元）
    net_capital_flow REAL,     -- 净流入合计 = inflow - outflow（万元，可负；资金流入/流出核心指标）
    hotmoney_ratio REAL,        -- 游资参与度占比（%，0-100）
    hotmoney_flag INTEGER DEFAULT 0, -- 1=游资主导（需排除）

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

-- =====================================================================
-- V2.1 新增：协作 / 授权 / 数据驱动筛选
-- =====================================================================

-- ---------- 用户 / 授权 ----------
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT,          -- hashlib 加盐 sha256（salt$hash）
    display_name TEXT,
    role TEXT DEFAULT 'viewer',  -- owner / admin / editor / viewer
    status TEXT DEFAULT 'active',-- active / disabled
    license_key TEXT,            -- 授权码（云端校验写入）
    sub_tier TEXT DEFAULT 'free',-- free / pro / team ...
    sub_expiry TEXT,             -- 订阅到期日 ISO（YYYY-MM-DD）
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- ---------- 筛选条件目录（单一事实来源，绑定 stocks 列或 computed: 字段） ----------
CREATE TABLE IF NOT EXISTS filter_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,    -- 条件键（如 roe / net_capital_flow）
    name TEXT,                   -- 中文名
    grp TEXT,                    -- 财务/估值/资金/技术/题材/风险
    ftype TEXT,                  -- numeric / enum / bool / text
    operator TEXT,               -- gt/lt/between/eq/in/neq/like（默认推荐算子）
    unit TEXT,                   -- 单位（如 % / 万元 / 倍）
    description TEXT,
    is_premium INTEGER DEFAULT 0,-- 1=付费墙功能
    default_visible INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_filter_catalog_key ON filter_catalog(key);

-- ---------- 筛选方案 ----------
CREATE TABLE IF NOT EXISTS filter_schemes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    owner_id INTEGER,
    is_pinned INTEGER DEFAULT 0, -- 1=置顶
    is_shared INTEGER DEFAULT 1, -- 1=团队共享
    description TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_filter_schemes_owner ON filter_schemes(owner_id);

-- ---------- 方案条件 ----------
CREATE TABLE IF NOT EXISTS scheme_conditions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_id INTEGER,
    catalog_key TEXT,            -- 关联 filter_catalog.key
    operator TEXT,               -- 实际算子（可覆盖目录默认）
    value TEXT,                  -- 主值（数字/枚举/文本；enum-in 用 JSON 数组）
    value2 TEXT,                 -- between 的第二区间值
    sort_order INTEGER DEFAULT 0,
    enabled INTEGER DEFAULT 1    -- 0=临时禁用（不参与过滤）
);
CREATE INDEX IF NOT EXISTS idx_scheme_conditions_scheme ON scheme_conditions(scheme_id);

-- ---------- 方案版本（版本化 + 回滚） ----------
CREATE TABLE IF NOT EXISTS scheme_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_id INTEGER,
    version_no INTEGER,
    snapshot_json TEXT,          -- 方案 + 条件快照（JSON）
    created_by INTEGER,
    created_at TEXT,
    note TEXT
);
CREATE INDEX IF NOT EXISTS idx_scheme_versions_scheme ON scheme_versions(scheme_id);

-- ---------- 操作日志 ----------
CREATE TABLE IF NOT EXISTS operation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT,                 -- create/update/delete/login/pin/rollback ...
    target_type TEXT,            -- user/scheme/condition/version/log
    target_id INTEGER,
    detail TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_operation_logs_user ON operation_logs(user_id);
