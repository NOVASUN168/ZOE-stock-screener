# -*- coding: utf-8 -*-
"""
stock-screener · 鉴权模块（零依赖，仅标准库）
- 密码校验复用 db.verify_password（hashlib 加盐 sha256，"salt$hash" 格式）
- 带签名的无状态 token：HMAC-SHA256，secret 取自 system_config.auth_secret
  token = base64url(json{username,exp}) + "." + hmac_sha256(secret, payload)
"""
import base64
import hashlib
import hmac
import json
import os
import sqlite3
import time

import db

TOKEN_EXP_HOURS = 24


# --------------------------------------------------------------------------
# 密码校验（委托给 db，保持单一事实来源）
# --------------------------------------------------------------------------
verify_password = db.verify_password


# --------------------------------------------------------------------------
# 签名 secret（system_config.auth_secret，首次运行自动生成）
# --------------------------------------------------------------------------
def get_secret(conn) -> str:
    row = conn.execute(
        "SELECT value FROM system_config WHERE key='auth_secret'").fetchone()
    if row and row["value"]:
        return row["value"]
    secret = os.urandom(32).hex()
    conn.execute(
        "INSERT INTO system_config(key,value,updated_at) VALUES('auth_secret',?,datetime('now','localtime')) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now','localtime')",
        (secret,))
    conn.commit()
    return secret


# --------------------------------------------------------------------------
# base64url 工具
# --------------------------------------------------------------------------
def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


# --------------------------------------------------------------------------
# token 签发 / 校验
# --------------------------------------------------------------------------
def issue_token(secret: str, username: str, exp_hours: int = TOKEN_EXP_HOURS) -> str:
    payload = {"username": username, "exp": int(time.time()) + exp_hours * 3600}
    body = _b64url_encode(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    sig = _b64url_encode(
        hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def validate_token(secret: str, token: str):
    """成功返回 username，过期/伪造/格式错误返回 None。"""
    if not token or "." not in token:
        return None
    try:
        body, sig = token.rsplit(".", 1)
        expect = _b64url_encode(
            hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest())
        if not hmac.compare_digest(expect, sig):
            return None
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload.get("username")
    except Exception:
        return None


def current_user(conn, handler):
    """从 Authorization: Bearer <token> 解析当前用户（实时查库，角色/订阅变更即时生效）。
    返回用户 dict 或 None。"""
    secret = get_secret(conn)
    auth_header = handler.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[len("Bearer "):].strip()
    username = validate_token(secret, token)
    if not username:
        return None
    return db.get_user(conn, username)
