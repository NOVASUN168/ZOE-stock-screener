# -*- coding: utf-8 -*-
"""
stock-screener · Stripe 订阅 / 在线付费墙（零依赖，仅标准库）

所有 Stripe 调用均使用 urllib.request 直接访问 REST API：
  - Basic Auth：username = sk-...（stripe_secret_key），password = ""（标准库方式）
  - Webhook 验签：复用 hmac / hashlib（HMAC-SHA256，常量时间比较）

密钥全部从 system_config 表读取，绝不写进代码（沿用 /api/config 写入机制）：
  stripe_secret_key     : sk_test_... / sk_live_...
  stripe_webhook_secret : whsec_...
  stripe_price_id       : price_...（订阅价格）
  stripe_mode           : test / live

本模块不依赖 stripe SDK 或任何第三方库。
"""
import base64
import datetime
import hashlib
import hmac
import json
import urllib.error
import urllib.parse
import urllib.request

import db


# system_config 中计费相关键
_CFG_KEYS = ("stripe_secret_key", "stripe_webhook_secret", "stripe_price_id", "stripe_mode")
_STRIPE_API = "https://api.stripe.com/v1"

# checkout 成功 / 取消回调占位 URL —— 正式部署务必改成你的域名
_SUCCESS_URL = "http://127.0.0.1:8765/?sub=ok"
_CANCEL_URL = "http://127.0.0.1:8765/?sub=cancel"


def _plus_years(n: int) -> str:
    return (datetime.date.today() + datetime.timedelta(days=365 * n)).isoformat()


# --------------------------------------------------------------------------
# 配置读取
# --------------------------------------------------------------------------
def _cfg(conn) -> dict:
    """从 system_config 读取计费配置。

    返回 dict 含全部 4 个键（缺失则为 None），并附加 'configured' 布尔：
    当且仅当 secret / webhook_secret / price_id 三者都存在时才算「已配置」
    （stripe_mode 缺失时退化为 'test'，不阻断配置）。
    """
    rows = conn.execute(
        "SELECT key,value FROM system_config WHERE key IN (%s)"
        % ",".join("?" * len(_CFG_KEYS)),
        _CFG_KEYS).fetchall()
    cfg = {r["key"]: r["value"] for r in rows}
    for k in _CFG_KEYS:
        cfg.setdefault(k, None)
    if not cfg.get("stripe_mode"):
        cfg["stripe_mode"] = "test"
    cfg["configured"] = all(
        cfg.get(k) for k in ("stripe_secret_key", "stripe_webhook_secret", "stripe_price_id"))
    return cfg


# --------------------------------------------------------------------------
# 创建 Checkout 会话
# --------------------------------------------------------------------------
def create_checkout(conn, user_id, plan="premium_monthly") -> dict:
    """创建 Stripe Checkout 会话，返回可跳转的 checkout_url。

    未配置密钥 → {"ok": False, "error": "billing_not_configured"}
    失败       → {"ok": False, "error": "stripe_error", "detail": ...}
    成功       → {"ok": True, "checkout_url": url}
    """
    cfg = _cfg(conn)
    if not cfg["configured"]:
        return {"ok": False, "error": "billing_not_configured"}

    secret = cfg["stripe_secret_key"]
    price_id = cfg["stripe_price_id"]
    # 订阅模式更贴近「订阅」语义（与一次性 payment 区分）
    mode = "subscription"
    params = {
        "mode": mode,
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "success_url": _SUCCESS_URL,
        "cancel_url": _CANCEL_URL,
        "client_reference_id": str(user_id),
    }
    # Basic Auth：username = secret, password 留空（标准库方式）
    basic = base64.b64encode(f"{secret}:".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(
        f"{_STRIPE_API}/checkout/sessions",
        data=urllib.parse.urlencode(params).encode("utf-8"),
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        return {"ok": False, "error": "stripe_error", "detail": detail}
    except Exception as e:  # 网络不可达 / 超时等
        return {"ok": False, "error": "stripe_error", "detail": str(e)}

    url = data.get("url")
    if not url:
        return {"ok": False, "error": "stripe_error", "detail": "no checkout url in response"}
    return {"ok": True, "checkout_url": url, "plan": plan}


# --------------------------------------------------------------------------
# Webhook 验签
# --------------------------------------------------------------------------
def verify_webhook(body_bytes: bytes, sig_header: str, secret: str) -> bool:
    """校验 Stripe 签名：t=时间戳, v1=十六进制HMAC。

    签名原文 = timestamp + "." + body_bytes，使用 webhook_secret 做 HMAC-SHA256。
    与 v1 做常量时间比较，防时序攻击。
    """
    if not sig_header or not secret:
        return False
    try:
        parts = {}
        for kv in sig_header.split(","):
            if "=" in kv:
                k, v = kv.split("=", 1)
                parts[k.strip()] = v.strip()
    except Exception:
        return False
    ts = parts.get("t")
    sig = parts.get("v1")
    if not ts or not sig:
        return False
    signed_payload = ts.encode("utf-8") + b"." + body_bytes
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


# --------------------------------------------------------------------------
# Webhook 处理
# --------------------------------------------------------------------------
def handle_webhook(conn, body, sig_header: str) -> dict:
    """处理 Stripe Webhook（body 为原始字节）。

    验签失败 → {"ok": False, "error": "bad_signature"} 且不修改任何数据。
    验签通过 → 解析事件：
      checkout.session.completed → 给用户激活 premium 订阅（记 operation_log）。
      其它事件类型 → {"ok": True, "event": type, "ignored": True}
    """
    cfg = _cfg(conn)
    secret = cfg.get("stripe_webhook_secret") or ""
    if not verify_webhook(body if isinstance(body, (bytes, bytearray)) else body.encode("utf-8"),
                          sig_header, secret):
        return {"ok": False, "error": "bad_signature"}

    try:
        if isinstance(body, (bytes, bytearray)):
            event = json.loads(body.decode("utf-8"))
        else:
            event = json.loads(body)
    except Exception:
        return {"ok": False, "error": "bad_json"}

    etype = event.get("type")
    if etype == "checkout.session.completed":
        obj = (event.get("data") or {}).get("object") or {}
        user_id = obj.get("client_reference_id")
        sub_id = obj.get("subscription") or obj.get("customer")
        if not user_id:
            return {"ok": False, "error": "no_user_in_event"}
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            return {"ok": False, "error": "bad_user_id"}
        # 订阅激活：给一年期 premium（stripe 会持续按周期续费；到期由后续事件/定时任务判断）
        expiry = _plus_years(1)
        db.set_license(conn, uid, f"stripe-{sub_id}", "premium", expiry)
        if hasattr(db, "log_operation"):
            db.log_operation(conn, uid, "billing", "subscription", str(sub_id),
                             f"Stripe 订阅激活: {sub_id}（plan={obj.get('mode','subscription')}）")
        return {"ok": True, "event": "session_completed", "user_id": uid}

    return {"ok": True, "event": etype, "ignored": True}


# --------------------------------------------------------------------------
# 状态查询
# --------------------------------------------------------------------------
def get_status(conn, user_id) -> dict:
    """返回计费墙状态（供前端优雅降级）。"""
    cfg = _cfg(conn)
    u = db.get_user_by_id(conn, user_id) or {}
    return {
        "enabled": bool(cfg.get("stripe_secret_key")),
        "mode": cfg.get("stripe_mode"),
        "tier": u.get("sub_tier", "free"),
        "expiry": u.get("sub_expiry"),
    }
