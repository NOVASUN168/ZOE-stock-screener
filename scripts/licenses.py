# -*- coding: utf-8 -*-
"""
stock-screener · 授权 / 订阅模块（零依赖，仅标准库）
- 本地校验 key 格式
- 若 system_config.cloud_validate_url 已配置（默认 None=离线），用 urllib 云端校验
- 离线模式：开发/测试 key 前缀 ZOE-PREMIUM- → tier='premium'
成功调用 db.set_license(conn, user_id, key, tier, expiry)。
"""
import datetime
import json
import sqlite3
import urllib.error
import urllib.request

import db


def _cloud_url(conn):
    row = conn.execute(
        "SELECT value FROM system_config WHERE key='cloud_validate_url'").fetchone()
    return row["value"] if row and row["value"] else None


def _plus_years(n: int) -> str:
    return (datetime.date.today() + datetime.timedelta(days=365 * n)).isoformat()


def activate(conn, user_id, key):
    """激活许可证。
    成功返回 {"ok": True, "tier", "expiry"}；
    失败返回 {"ok": False, "error": ...}（不抛异常，由上层转 HTTP 状态）。"""
    if not key or not str(key).strip():
        return {"ok": False, "error": "license_key_required"}
    key = str(key).strip()
    cloud = _cloud_url(conn)

    if cloud:
        try:
            req = urllib.request.Request(
                cloud,
                data=json.dumps({"license_key": key}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if not data.get("valid"):
                return {"ok": False, "error": "license_invalid"}
            tier = data.get("tier", "premium")
            expiry = data.get("expiry")
        except Exception as e:
            return {"ok": False, "error": f"cloud_validate_failed: {e}"}
    else:
        # 离线模式：仅接受开发/测试前缀 key
        if key.startswith("ZOE-PREMIUM-"):
            tier = "premium"
            expiry = _plus_years(1)
        else:
            return {"ok": False, "error": "license_invalid_offline"}

    db.set_license(conn, user_id, key, tier, expiry)
    return {"ok": True, "tier": tier, "expiry": expiry}


def get_status(conn, user_id):
    """返回用户订阅状态。"""
    u = db.get_user_by_id(conn, user_id) or {}
    return {
        "tier": u.get("sub_tier", "free"),
        "expiry": u.get("sub_expiry"),
        "cloud_configured": bool(_cloud_url(conn)),
    }
