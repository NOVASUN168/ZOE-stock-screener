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
import json
import sqlite3
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import db
import scoring
import filter_catalog
import screen_engine

SCHEMA = os.path.join(ROOT, "schema.sql")
DEFAULT_DB = os.path.join(ROOT, "data", "screener.db")

# ---------- 真实种子（由 scripts/fetch_ai_data.py 抓取 westock-data 生成，V2.0 AI 股票池） ----------
_SEED_JSON = os.path.join(ROOT, "scripts", "seed_real_v2.json")
if os.path.exists(_SEED_JSON):
    with open(_SEED_JSON, encoding="utf-8") as _f:
        SEED = json.load(_f)
    print(f"  已加载 V2.0 真实 AI 种子 {len(SEED)} 只（来自 seed_real_v2.json，抓取日 2026-07-27）")
else:
    SEED = []
    print("  ⚠️ 未找到 seed_real_v2.json，请用 scripts/fetch_ai_data.py 生成")


def build_schema(conn):
    with open(SCHEMA, "r", encoding="utf-8") as f:
        sql = f.read()
    # sqlite3 支持一次执行多条语句
    conn.executescript(sql)
    conn.commit()
    db.migrate_stocks(conn)  # 向后兼容：补齐已存在 stocks 表的缺失列


def seed(conn):
    for d in SEED:
        sid = db.create(conn, d)
        scored = scoring.score_stock(d)
        db.patch_computed(conn, sid, {k: scored.get(k) for k in db.COMPUTED_KEYS})
    print(f"  播种 {len(SEED)} 只真实股票")


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


# ---------- V2.1：条件目录 / 默认用户 / 示例方案 播种 ----------
# ⚠️ 开发默认密码（仅本地/演示用，生产请改）：
#   nova  / owner   -> NovaLocal#2026
#   robin / editor  -> robin2026
#   sean  / editor  -> sean2026
DEV_USERS = [
    ("nova", "NovaLocal#2026", "Nova", "owner"),
    ("robin", "robin2026", "Robin", "editor"),
    ("sean", "sean2026", "Sean", "editor"),
]

def seed_catalog_and_users(conn):
    n = filter_catalog.seed_catalog(conn)
    print(f"  条件目录写入 {n} 条（共 {len(filter_catalog.CATALOG)} 条，已存在跳过）")

    for username, pw, disp, role in DEV_USERS:
        if db.get_user(conn, username):
            continue
        uid = db.create_user(conn, username, pw, display_name=disp, role=role)
        db.log_operation(conn, uid, "create", "user", uid, f"开发默认账户 {username}/{role}")
    print(f"  默认账户就绪：{', '.join(u[0] for u in DEV_USERS)}")

    # 示例共享方案（置顶，含 3-4 个条件），方便前端演示。
    # 注：真实种子 seed_real_v2.json 暂未填充资金流字段（net_capital_flow 等均为 NULL），
    # 故示例方案选用 seed 已具备的 ai_category / 风险排除类条件，确保演示有结果；
    # 资金流条件（net_capital_flow/hotmoney_*）待 fetch 脚本补全数据后即可生效。
    if not db.list_schemes(conn):
        nova = db.get_user(conn, "nova")
        sid = db.create_scheme(
            conn, "AI核心·低风险", owner_id=nova["id"],
            description="示例：AI核心基础分类 + 排除ST + 排除游资主导",
            is_pinned=1, is_shared=1)
        db.add_condition(conn, sid, "ai_category", "eq", "核心基础", sort_order=1)
        db.add_condition(conn, sid, "st_exclude", "eq", "0", sort_order=2)
        db.add_condition(conn, sid, "hotmoney_exclude", "eq", "0", sort_order=3)
        db.add_condition(conn, sid, "pe", "lt", "200", sort_order=4)
        db.snapshot_version(conn, sid, nova["id"], note="初始示例版本")
        db.log_operation(conn, nova["id"], "create", "scheme", sid, "示例共享方案")
        print(f"  示例方案已播种（id={sid}，4 个条件）")
    else:
        print("  已有方案，跳过示例方案播种")


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
    seed_catalog_and_users(conn)
    print("完成。总行数：", conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0])
    conn.close()


if __name__ == "__main__":
    main()
