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

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_PATH = os.path.join(HERE, "ui", "index.html")


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
        "target_price", "reasonable_valuation", "buy_point", "stop_loss",
        "take_profit", "suggested_position", "expected_return", "expected_hold",
        "advantages", "risks_text", "recommend_reasons"]}
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

    def do_GET(self):
        u = urlparse(self.path)
        path = u.path
        q = parse_qs(u.query)
        conn = db.connect(self.server.db_path)
        try:
            if path == "/" or path == "/index.html":
                if os.path.exists(UI_PATH):
                    with open(UI_PATH, "rb") as f:
                        self._send(200, None, "text/html; charset=utf-8")
                        self.wfile.write(f.read())
                else:
                    self._send(404, {"error": "UI 未找到"})
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
            self._send(404, {"error": "未知路径"})
        finally:
            conn.close()

    def do_POST(self):
        u = urlparse(self.path)
        path = u.path
        conn = db.connect(self.server.db_path)
        try:
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


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--db", default=None)
    a = p.parse_args()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    srv.db_path = a.db or db.DEFAULT_DB
    print(f"stock-screener 已启动 → http://{a.host}:{a.port}/")
    print(f"SQLite 数据库：{srv.db_path}")
    print("按 Ctrl+C 停止。")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
