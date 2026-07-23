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
