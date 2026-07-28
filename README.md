# 股票基金筛选系统 · Stock Screener

一套**科学、稳定、可解释**的股票/基金筛选系统。多因子量化评分 + SQLite 数据层 + 可视化 Web UI，**零外部依赖**（仅 Python 标准库）。

> ⚠️ 本系统为研究/教学/效率工具，所有评分与信号均基于**你录入的截面数据**与模型推断，**不构成投资建议**，更不承诺收益。实战请结合实时行情、宏观与人工判断。

---

## 一、快速开始

```bash
# 1) 建库并播种 15 只示例（含 1 只风险样本用于演示过滤）
python scripts/init_db.py --seed

# 2) 启动 Web 服务（默认 http://127.0.0.1:8765/）
python scripts/server.py
#   自定义：python scripts/server.py --port 9000 --host 0.0.0.0 --db my.db
```

浏览器打开 `http://127.0.0.1:8765/` 即可使用。五个标签页：

| 标签页 | 功能 |
|---|---|
| 📊 工作台 | 股票列表、综合评分、风险标记；**新增 / 修改 / 删除**；风格/行业/最低分筛选；导出 JSON；重算评分 |
| 🔔 预警·风控 | 风控提醒（自动汇总风险股）+ 预警规则（评分跌破/价格突破/出现风险）新增删除 |
| 💼 组合推荐 | 稳健 / 成长 / 激进 三类组合（资金分配、行业占比、风险等级、收益预期、最大回撤），可保存 |
| 📅 每日复盘 | 买点/卖点信号、风险警示、市场热点、行业轮动、明日重点 |
| 📖 新手术语 | ROE / PE / PEG / 护城河 / 质押 等小白必看解释 |

---

## 二、评分模型（综合 100 分）

| 因子 | 权重 | 关键指标 |
|---|---|---|
| 基本面 | 30% | ROE>15%、ROA>8%、营收/净利连续3年增长、自由现金流转正、资产负债率（制造<60%·科技<50%·金融单列） |
| 估值 | 20% | PE低于行业均值、PB合理、PEG<1.5、EV/EBITDA合理、安全边际>30% |
| 成长 | 20% | 研发/份额提升、行业空间、护城河、未来3年利润CAGR |
| 技术 | 15% | 均线、MACD、KDJ、RSI、成交量、波动率 |
| 资金 | 10% | 主力/北向资金、机构持仓变化 |
| 风险 | 5% | 财务/诉讼/质押/监管/商誉 |

等级：95+ ★★★★★强烈推荐｜90+ ★★★★☆推荐｜80+ ★★★★关注｜70+ ★★★一般｜<70 不建议。
硬过滤（一票否决）：ST / 退市 / 造假 / 连续亏损 / 重大诉讼 / 商誉>40% / 大股东减持 / 高质押。

---

## 三、数据库（SQLite）

- `schema.sql` 是建表的**单一事实来源**。任何改表结构都必须同步此文件，并用 `python scripts/init_db.py` 验证。
- 运行时数据库 `data/screener.db` 由程序自动生成，**已被 `.gitignore` 排除**，不会提交客户数据。
- 密钥/Webhook 配置走 `system_config` 表（或 `WECOM_CRM_WEBHOOK` 环境变量），**绝不写进代码或提交**。

主要表：`stocks`（标的基础库+计算产物）、`portfolios`、`alerts`（预警规则）、`watchlist`（持仓监控）、`system_config`。

---

## 四、REST API（供二次开发 / 接入）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/stocks?style=&industry=&min_score=` | 股票列表（可风格/行业/最低分筛选） |
| POST | `/api/stocks` | 新增股票（自动评分） |
| PUT | `/api/stocks/<id>` | 修改股票（自动重算） |
| DELETE | `/api/stocks/<id>` | 删除股票 |
| POST | `/api/rescore` | 重算全部评分 |
| GET | `/api/alerts` | 预警规则 + 触发状态 |
| POST | `/api/alerts` | 新增预警规则 |
| DELETE | `/api/alerts/<id>` | 删除预警规则 |
| GET | `/api/risk-reminders` | 风控提醒列表 |
| GET | `/api/portfolio?ptype=robust\|growth\|aggressive` | 组合推荐 |
| POST | `/api/portfolio/save` | 保存组合 |
| GET | `/api/review` | 每日复盘 |
| GET/POST | `/api/watch` | 持仓监控 增/查 |
| GET/POST | `/api/config` | 系统配置 查/写 |

---

## 五、行情接入（让预警/复盘变“实时”）

当前系统基于**录入快照**。要变成实时，把行情源（如腾讯财经/东方财富/聚源）的价格、资金流写入 `stocks.price` 等字段，再调用 `POST /api/rescore` 即可刷新评分；价格类预警会在下次 `GET /api/alerts` 时重新评估触发。
接入点已在 `scripts/` 各模块留出清晰函数边界，按 `schema.sql` 字段扩展即可。

---

## 六、目录结构

```
ZOE-stock-screener/
├── schema.sql
├── scripts/  (db / scoring / alerts / portfolio / review / init_db / server).py
├── ui/index.html
├── data/        # 运行时生成（已忽略）
├── LICENSE      # MIT 开源协议
├── README.md
└── .gitignore
```

---

## 七、免责声明

本系统为研究/教学/效率工具，评分基于录入指标与模型推断，**不构成投资建议**；投资有风险，决策需谨慎。

---

## 八、环境要求

- **Python 3.8+**（仅使用标准库，无需 `pip install`）
- 支持 Windows / macOS / Linux
- 无需额外数据库服务，SQLite 文件即开即用

## 九、开源协议

本项目基于 **MIT License** 开源，详见 [LICENSE](./LICENSE)。
你可以自由使用、修改、分发、二次开发，包括用于商业用途，只需保留版权声明与许可声明。

## 十、如何参与共建

欢迎朋友 fork 共建。修改前请先 `git pull --rebase`，提交前在本地打一个 checkpoint 标签再推送；
**切勿**对 `main` 强推、切勿提交 `*.db` / 客户 `*.xlsx` / 任何 API Key（密钥走 `system_config` 表或环境变量）。
详见配套技能《股票基金筛选 GitHub 拉取 / 推送 / 版本回滚 / 加协作者》中的 5 条铁律。

---

## 十一、ZOE 同步技能验收记录

- **2026-07-25**：经「ZOE 股票筛选系统」同步技能走真实验收流程，自动执行 `pull → checkpoint → commit → push` 闭环通过。
  - 锚点标签：`cp-verify-20260725`（指向改动前基线 `8270f3f`）
  - 提交前缀：`docs:`（更新本记录小节）
  - 验收时仓库状态：本机 `main` 与 `origin/main` 同步于 `8270f3f`，工作区干净
  - 三人协作仓库：`git@github.com:NOVASUN168/ZOE-stock-screener.git`（Nova / ROBIN / Sean）

---

## 十二、V2.1 重构说明（数据驱动筛选 + 多用户协作 + 商业化授权）

V2.1 在保留「零外部依赖、Python 标准库」内核的前提下，把原先写死的筛选逻辑升级为**数据驱动的可配置筛选引擎**，并补齐了**多用户协作**与**商业化授权**两大能力。

### 12.1 新增能力一览
- **综合筛选条件目录**：`filter_catalog` 表内置 47 条条件（财务/估值/资金/技术/题材/风险 六大分组），对齐一线选股器的多因子维度；其中 3 条标记为付费（`is_premium=1`）。
- **资金流入/流出 + 游资排除**：`stocks` 表新增 `main_inflow_20d` / `main_outflow_20d` / `net_capital_flow`（资金净流入核心指标）/ `hotmoney_ratio`（游资参与度）/ `hotmoney_flag`（游资主导标记）。筛选引擎支持按 `hotmoney_flag=0` 或 `hotmoney_ratio<X` 排除游资主导标的。
- **共享筛选方案库**：`filter_schemes` + `scheme_conditions`，Robin / Sean 可**新建、修改、删除、置顶（pin）、下拉刷新（git pull）**筛选条件。
- **方案版本化与回滚**：每次保存/修改自动快照（`scheme_versions`），可一键回滚到任意历史版本。
- **操作日志 + 权限管理**：所有写操作写入 `operation_logs`；角色分 `owner / admin / editor / viewer`，越权返回 403。
- **git 同步**：方案可「导出 git」（`scripts/zoe_sync.py` 提交 + 推送），也可「下拉刷新」拉取他人改动——App 内协作与 git 代码协作并存。
- **商业化授权（本地跑 + 云端校验）**：登录账户体系 + 授权码/订阅校验。免费用户使用付费条件时筛选接口返回 **402**；激活 `ZOE-PREMIUM-` 前缀授权码（或云端 `/validate`）后解锁。Stripe 等支付可后续接入云端校验服务。

### 12.2 默认账户（开发/演示）
| 用户名 | 密码 | 角色 |
|--------|------|------|
| nova | zoe2026 | owner（最高权限 + 用户管理） |
| robin | robin2026 | editor（可改筛选方案） |
| sean | sean2026 | editor（可改筛选方案） |

> ⚠️ 演示密码仅用于本地开发，部署前请务必改密或接入真实账户体系。

### 12.3 新增/改动文件
- 新增 `scripts/filter_catalog.py`（47 条条件目录）、`scripts/screen_engine.py`（数据驱动筛选引擎）
- 新增 `scripts/auth.py`（登录/签名 token）、`scripts/licenses.py`（授权/订阅校验）、`scripts/filters_api.py`（方案/目录/版本/日志/用户 API）、`scripts/zoe_sync.py`（极简 git 同步）
- 改动 `scripts/db.py`（新表 CRUD + 日志）、`scripts/scoring.py`（纳入 net_capital_flow、游资硬过滤）、`scripts/server.py`（路由分发）、`schema.sql`（新增 5 列 + 6 张表）、`ui/index.html`（新增「🔧 筛选方案」标签页 + 登录态 + 付费墙）

### 12.4 新增 API 速查
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/login` `/api/auth/logout` `/api/auth/me` | 登录态 |
| POST | `/api/license/activate` `GET /api/license/status` | 授权/订阅 |
| GET | `/api/filter-catalog` | 条件目录（47 条） |
| GET/POST | `/api/schemes` | 方案列表 / 新建 |
| GET/PUT/DELETE | `/api/schemes/<id>` | 方案详情 / 更新 / 删除 |
| POST | `/api/schemes/<id>/pin` `/snapshot` `/rollback` `/export` `/pull` `/versions` | 置顶 / 快照 / 回滚 / 导出git / 下拉刷新 / 版本列表 |
| POST | `/api/screen` | 应用筛选（{scheme_id} 或 {conditions}） |
| GET | `/api/operation-logs` | 操作日志 |
| GET/POST/PUT | `/api/users` `/api/users/<id>` | 用户管理（admin+ / owner） |

> 除登录/登出外，所有接口需带 `Authorization: Bearer <token>`。

### 12.5 运行与协作
```bash
# 建库（已含真实 A 股种子 + 目录 + 默认账户）
python scripts/init_db.py --seed
# 启动（默认 http://127.0.0.1:8765/）
python scripts/server.py
```
代码协作仍走「ZOE 同步技能」铁律（pull → checkpoint → commit → push）；筛选方案的协作走 App 内方案库 + 版本/日志，并可一键导出到 git。

### 12.6 已知待补全
- 真实种子 `seed_real_v2.json` 暂缺资金流数据（`net_capital_flow` 等全 NULL），含资金流条件的方案当前匹配为空，需用 `scripts/fetch_ai_data.py` / `fetch_real_data.py` 补全后再出结果。
- `computed:` 类字段（股息率/毛利率等）暂为占位，待补数据源或计算逻辑。
- 云端授权校验依赖 `system_config.cloud_validate_url`（默认 None = 离线），接入真实支付（Stripe/微信）时由云端 `/validate` 返回 `tier` 与 `expiry`。

---

## 十三、V2.2 说明（真实资金流数据接入 + Stripe 商业化订阅）

V2.2 把 V2.1「已知待补全」里的两块真正落地：**资金流字段不再为空**（接东财真实数据），**付费墙可以真正收款**（接 Stripe Checkout + Webhook，密钥全走 `system_config`，不进代码）。

### 13.1 真实资金流数据（scripts/refresh_capital.py）
- 纯标准库从东财 `push2his.eastmoney.com/api/qt/stock/fflow/daykline/get` 拉取 A 股近 120 日主力资金流，写入 `stocks` 表：
  - `main_inflow_20d` / `main_outflow_20d` / `net_capital_flow`（近 20 日，单位 **万元**）
  - `hotmoney_ratio`（游资参与度，单位 **%**，口径 = `(超大单+大单净流入) / (全口径净流入绝对值之和) × 100`，取值 0–100）
  - `hotmoney_flag`（游资主导标记：`hotmoney_flag=1` 表示近 30 日龙虎榜上榜 ≥ 3 次）
- 港股（`hk` 开头）跳过；请求间 `sleep 1.2s` 防限流；失败自动重试。
- 用法：`python scripts/refresh_capital.py`（读库内 `stocks` 列表，逐只刷新，可直接重跑补数）。

### 13.2 Stripe 商业化订阅（scripts/billing.py）
- 五个函数：`_cfg(conn)` / `create_checkout(...)` / `verify_webhook(...)` / `handle_webhook(...)` / `get_status(...)`。
- 流程：前端「前往订阅」→ `POST /api/billing/checkout` 创建 Stripe Checkout Session → 用户支付 → Stripe 回调 `POST /api/billing/webhook` → `checkout.session.completed` 事件中将用户 `tier` 升为 `premium` 并记录到期日（复用 `licenses.py` 的 `set_license`）。
- 安全：Webhook 用 **HMAC-SHA256 常量时间比对**（`hmac.compare_digest`）验签；`server.py` 对 `/api/billing/webhook` 用原始字节 `rfile.read(Content-Length)` 提前拦截，避免 body 被消费。
- 配置（全部写入 `system_config`，**绝不进代码**）：`stripe_secret_key` / `stripe_webhook_secret` / `stripe_price_id` / `stripe_mode`（test|live）。
- **优雅降级**：未配置 Stripe 时 `create_checkout` 返回 `{ok:false, error:"billing_not_configured"}`，`get_status` 返回 `{enabled:false, mode:"test", tier, expiry}`，前端「前往订阅」按钮自动禁用——系统离线激活码仍可正常用。

### 13.3 新增 / 改动文件
- 新增 `scripts/refresh_capital.py`（东财资金流拉取与入库）、`scripts/billing.py`（Stripe Checkout + Webhook 验签）
- 改动 `scripts/filters_api.py`（注册 `/api/billing/checkout`、`/api/billing/status`）、`scripts/server.py`（路由前缀 + Webhook 原始字节拦截）、`ui/index.html`（第 7 标签「💳 订阅 / 账户」+ 付费墙增强）

### 13.4 V2.2 新增 API 速查
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/billing/checkout` | 创建 Stripe Checkout Session（未配置则返回 `billing_not_configured`） |
| GET | `/api/billing/status` | 订阅状态（enabled / mode / tier / expiry） |
| POST | `/api/billing/webhook` | Stripe Webhook 回调（HMAC-SHA256 验签，坏签名返回 `bad_signature` 且不改数据） |

> 所有 billing 接口无需登录态（Checkout 用 `client_reference_id` 关联用户；Webhook 靠签名验真）。

### 13.5 V2.2 已知限制
- 种子资金流是**一次性快照**：`init_db.py --seed` 不自动拉资金流，需另跑 `scripts/refresh_capital.py` 填充；重跑即刷新。
- `hotmoney_flag` 当前全 0：龙虎榜口径依赖近 30 日真实上榜记录，初始种子无该历史，跑 `refresh_capital.py` 后若有上榜会标记；此前多为 0 属正常。
- Stripe 未做真实联调：需由 Nova 在 Stripe 后台拿到 **secret key / webhook secret / price id** 写入 `system_config` 并配置 Webhook 指向 `/api/billing/webhook` 后，才能真正收款与自动升级。
