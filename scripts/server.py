# -*- coding: utf-8 -*-
"""
stock-screener · Web 服务（标准库，无外部依赖）
提供 JSON API（新增/修改/删除/筛选/重算/组合）+ 托管可视化 UI。
启动：python server.py [--port 8765] [--db 自定义.db] [--host 127.0.0.1]
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db
import scoring
import alerts
import portfolio
import review
import filters_api
import billing

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_PATH = os.path.join(HERE, "ui", "index.html")

# V2.1 新增 API 前缀（这些路径交由 filters_api.dispatch 处理）
# 注意：/api/billing/ 下的 checkout / status 走 dispatch；
#       /api/billing/webhook 因需原始字节验签，在 do_POST 中单独提前拦截（见下）。
NEW_API_PREFIXES = (
    "/api/auth/", "/api/license/", "/api/filter-catalog",
    "/api/schemes", "/api/screen", "/api/operation-logs", "/api/users",
    "/api/billing/",
)


def _rescore_and_persist(conn, row_id=None, data=None):
    """对单条（或已入库的）数据评分并写回计算字段。"""
    if data is not None:
        scored = scoring.score_stock(data)
    else:
        raw = db.get(conn, row_id)
        scored = scoring.score_stock(raw)
    # 仅回写计算产物字段
        computed = {k: scored.get(k) for k in [
            "total_score", "rating", "recommend_index", "risk_flags",
            "reasonable_valuation", "suggested_position", "expected_hold",
            "advantages", "risks_text", "recommend_reasons",
            "core_competence", "long_term_thesis"]}
    if row_id is not None:
        db.patch_computed(conn, row_id, computed)
    return scored


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj=None, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if obj is not None:
            self.wfile.write(json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def _serve_asset(self, path):
        """安全托管 /assets/* 下的静态文件（防目录穿越）。"""
        ASSET_ROOT = os.path.normpath(os.path.join(HERE, "ui", "assets"))
        rel = path[len("/assets/"):].replace("\\", "/")
        if ".." in rel or rel.startswith("/"):
            self._send(403, {"error": "forbidden"})
            return
        full = os.path.normpath(os.path.join(ASSET_ROOT, rel))
        if not full.startswith(ASSET_ROOT) or not os.path.isfile(full):
            self._send(404, {"error": "not found"})
            return
        mime = {
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".html": "text/html; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".ico": "image/x-icon",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".ttf": "font/ttf",
        }.get(os.path.splitext(full)[1].lower(), "application/octet-stream")
        try:
            with open(full, "rb") as f:
                data = f.read()
        except OSError:
            self._send(500, {"error": "read error"})
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=300")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        path = u.path
        q = parse_qs(u.query)
        conn = db.connect(self.server.db_path)
        try:
            # ---------- V2.1 新增路由 ----------
            if path.startswith(NEW_API_PREFIXES):
                code, obj = filters_api.dispatch(conn, "GET", path, {}, self)
                self._send(code, obj)
                return
            # --------------------------------
            if path == "/favicon.ico":
                self._send(204, None)
                return
            if path == "/" or path == "/index.html":
                if os.path.exists(UI_PATH):
                    with open(UI_PATH, "rb") as f:
                        self._send(200, None, "text/html; charset=utf-8")
                        self.wfile.write(f.read())
                else:
                    self._send(404, {"error": "UI 未找到"})
                return
            # ---------- 静态资源（CSS / JS / 图片 / 字体） ----------
            if path.startswith("/assets/"):
                self._serve_asset(path)
                return
            if path == "/api/stocks":
                style = q.get("style", [None])[0]
                industry = q.get("industry", [None])[0]
                min_score = q.get("min_score", [None])[0]
                ms = float(min_score) if min_score else None
                rows = db.list_all(conn, industry=industry, min_score=ms)
                if style:
                    rows = scoring.screen_by_style(rows, style)
                else:
                    rows = scoring.rescore_all(rows)
                self._send(200, rows)
                return
            if path == "/api/portfolios":
                rows = conn.execute("SELECT * FROM portfolios ORDER BY id DESC").fetchall()
                self._send(200, [dict(r) for r in rows])
                return
            if path.startswith("/api/stocks/"):
                sid = int(path.rsplit("/", 1)[-1])
                row = db.get(conn, sid)
                # 实时评分：让详情弹窗拿到五维雪花图数据（dim_* 字段）
                if row:
                    row = scoring.score_stock(row)
                self._send(200, row if row else {"error": "未找到"})
                return
            # ---------- 预警 / 风控提醒 ----------
            if path == "/api/alerts":
                self._send(200, alerts.evaluate_alerts(conn))
                return
            if path == "/api/risk-reminders":
                self._send(200, alerts.risk_reminders(conn))
                return
            if path == "/api/watch":
                self._send(200, alerts.watch_list(conn))
                return
            # ---------- 每日复盘 ----------
            if path == "/api/review":
                self._send(200, review.daily_review(conn))
                return
            # ---------- 组合推荐 ----------
            if path == "/api/portfolio":
                ptype = q.get("ptype", ["robust"])[0]
                self._send(200, portfolio.generate(conn, ptype))
                return
            # ---------- 系统配置 ----------
            if path == "/api/config":
                rows = conn.execute("SELECT key,value FROM system_config").fetchall()
                self._send(200, {r["key"]: r["value"] for r in rows})
                return
            # ---------- 定价方案（前端定价页数据来源） ----------
            if path == "/api/pricing":
                self._send(200, billing.get_pricing(conn))
                return
            self._send(404, {"error": "未知路径"})
        finally:
            conn.close()

    def do_POST(self):
        u = urlparse(self.path)
        path = u.path
        conn = db.connect(self.server.db_path)
        try:
            # ---------- 计费 Webhook（需原始字节验签，提前拦截，不经 dispatch 的 JSON body 解析） ----------
            # 说明：filters_api.dispatch 内部通过 self._body() 把 rfile 读成 dict，会消费掉原始 body，
            # 而 Stripe 验签必须用「原样字节」。因此这里在 dispatch 之前直接读取原始字节并调用 billing.handle_webhook。
            if path == "/api/billing/webhook":
                n = int(self.headers.get("Content-Length", 0) or 0)
                raw = self.rfile.read(n) if n else b""
                sig = self.headers.get("Stripe-Signature", "")
                obj = billing.handle_webhook(conn, raw, sig)
                self._send(200, obj)
                return
            # --------------------------------

            # ---------- V2.1 新增路由 ----------
            if path.startswith(NEW_API_PREFIXES):
                code, obj = filters_api.dispatch(conn, "POST", path, self._body(), self)
                self._send(code, obj)
                return
            # --------------------------------
            if path == "/api/stocks":
                data = self._body()
                sid = db.create(conn, data)
                scored = _rescore_and_persist(conn, row_id=sid)
                self._send(201, scored)
                return
            if path == "/api/rescore":
                rows = db.list_all(conn)
                for r in rows:
                    _rescore_and_persist(conn, row_id=r["id"])
                self._send(200, {"rescored": len(rows)})
                return
            if path == "/api/portfolios":
                d = self._body()
                db.save_portfolio(conn, d.get("ptype"), d.get("name"),
                                 d.get("stock_ids") or [], d.get("alloc") or {}, d.get("note", ""))
                self._send(201, {"ok": True})
                return
            # ---------- 预警规则 ----------
            if path == "/api/alerts":
                d = self._body()
                alerts.add_alert(conn, d.get("stock_id"), d.get("atype"),
                                 d.get("threshold"), d.get("note", ""))
                self._send(201, {"ok": True})
                return
            # ---------- 持仓监控 ----------
            if path == "/api/watch":
                d = self._body()
                alerts.watch_add(conn, d.get("stock_id"), d.get("note", ""))
                self._send(201, {"ok": True})
                return
            # ---------- 每日复盘（POST 强制重算） ----------
            if path == "/api/review":
                self._send(200, review.daily_review(conn))
                return
            # ---------- 组合保存 ----------
            if path == "/api/portfolio/save":
                d = self._body()
                portfolio.save(conn, d.get("ptype"), d.get("name"),
                               d.get("picks") or [], d.get("note", ""))
                self._send(201, {"ok": True})
                return
            # ---------- 系统配置写入（密钥走这里，绝不进代码） ----------
            if path == "/api/config":
                d = self._body()
                for k, v in d.items():
                    conn.execute(
                        "INSERT INTO system_config(key,value,updated_at) VALUES(?,?,datetime('now','localtime')) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now','localtime')",
                        (k, v))
                conn.commit()
                self._send(200, {"ok": True})
                return
            self._send(404, {"error": "未知路径"})
        finally:
            conn.close()

    def do_PUT(self):
        u = urlparse(self.path)
        path = u.path
        if path.startswith(NEW_API_PREFIXES):
            conn = db.connect(self.server.db_path)
            try:
                code, obj = filters_api.dispatch(conn, "PUT", path, self._body(), self)
                self._send(code, obj)
            finally:
                conn.close()
            return
        if path.startswith("/api/stocks/"):
            conn = db.connect(self.server.db_path)
            try:
                sid = int(path.rsplit("/", 1)[-1])
                data = self._body()
                db.update(conn, sid, data)
                scored = _rescore_and_persist(conn, row_id=sid)
                self._send(200, scored)
            finally:
                conn.close()
            return
        self._send(404, {"error": "未知路径"})

    def do_DELETE(self):
        u = urlparse(self.path)
        path = u.path
        if path.startswith(NEW_API_PREFIXES):
            conn = db.connect(self.server.db_path)
            try:
                code, obj = filters_api.dispatch(conn, "DELETE", path, self._body(), self)
                self._send(code, obj)
            finally:
                conn.close()
            return
        if path.startswith("/api/stocks/"):
            conn = db.connect(self.server.db_path)
            try:
                sid = int(path.rsplit("/", 1)[-1])
                db.delete(conn, sid)
                self._send(200, {"deleted": sid})
            finally:
                conn.close()
            return
        if path.startswith("/api/alerts/"):
            conn = db.connect(self.server.db_path)
            try:
                aid = int(path.rsplit("/", 1)[-1])
                alerts.delete_alert(conn, aid)
                self._send(200, {"deleted": aid})
            finally:
                conn.close()
            return
        if path.startswith("/api/watch/"):
            conn = db.connect(self.server.db_path)
            try:
                wid = int(path.rsplit("/", 1)[-1])
                alerts.watch_remove(conn, wid)
                self._send(200, {"deleted": wid})
            finally:
                conn.close()
            return
        self._send(404, {"error": "未知路径"})

    def log_message(self, *args):
        pass


def _autoseed_if_empty(db_path):
    """数据库为空（stocks 表 0 行）时自动灌入初始种子数据。
    用于 Render 等首次部署场景；本地已有股票数据的库不会触发，避免覆盖。"""
    try:
        import init_db
    except Exception as e:
        print(f"⚠️ 自动播种跳过：无法导入 init_db（{e}）")
        return
    conn = db.connect(db_path)
    try:
        n = conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
        if n and n > 0:
            print(f"数据库已有 {n} 只股票，跳过自动播种。")
            return
        print("检测到空数据库，自动播种初始数据（15 只 AI 股 + 筛选条件目录）...")
        init_db.seed(conn)
        init_db.seed_catalog_and_users(conn)
        init_db.init_config(conn)
        conn.commit()
        print("✅ 自动播种完成，手机端现在能看到初始数据。")
    except Exception as e:
        print(f"⚠️ 自动播种失败（不影响启动）：{e}")
    finally:
        conn.close()


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--db", default=None)
    a = p.parse_args()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    srv.db_path = a.db or db.DEFAULT_DB
    _autoseed_if_empty(srv.db_path)
    print(f"stock-screener 已启动 → http://{a.host}:{a.port}/")
    print(f"SQLite 数据库：{srv.db_path}")
    print("按 Ctrl+C 停止。")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
