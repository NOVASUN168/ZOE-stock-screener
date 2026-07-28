# -*- coding: utf-8 -*-
"""
stock-screener · V2.1 业务路由模块（零依赖，仅标准库）
集中实现：鉴权 / 许可证 / 筛选目录 / 方案(CRUD+版本+置顶+导出) /
应用筛选(付费墙) / 操作日志 / 用户管理。
server.py 只做路径分发，所有业务逻辑在此。每个函数返回 (code, obj)。
权限矩阵：
  viewer : 读方案 / 非付费筛选 / 看自己相关日志
  editor : + 方案增删改 / 置顶 / 快照 / 回滚 / 导出 / 拉取 / 筛选
  admin  : + 用户列表 / 创建
  owner  : + 改他人角色 / 全部
"""
import json
import os
import re
import sqlite3
import subprocess
import sys

import db
import auth
import licenses
import filter_catalog
import screen_engine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMES_DIR = os.path.join(ROOT, "schemes")

ROLE_RANK = {"viewer": 0, "editor": 1, "admin": 2, "owner": 3}

_SCHEME_ID_RE = re.compile(r"^/api/schemes/(\d+)$")
_SCHEME_SUB_RE = re.compile(r"^/api/schemes/(\d+)/(pin|snapshot|versions|rollback|export|pull)$")
_USER_ID_RE = re.compile(r"^/api/users/(\d+)$")


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------
def _role_ok(user, min_role):
    return bool(user) and ROLE_RANK.get(user.get("role"), 0) >= ROLE_RANK.get(min_role, 0)


def _public_user(u):
    return {
        "id": u.get("id"),
        "username": u.get("username"),
        "display_name": u.get("display_name"),
        "role": u.get("role"),
        "sub_tier": u.get("sub_tier"),
    }


def _slug(name):
    s = re.sub(r"[^\w一-鿿-]+", "-", str(name)).strip("-")
    return s.lower() or None


def _zoe_sync(args):
    """调用 scripts/zoe_sync.py（git 同步）。失败抛 RuntimeError。"""
    script = os.path.join(ROOT, "scripts", "zoe_sync.py")
    r = subprocess.run([sys.executable, script] + args, cwd=ROOT,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip())
    return r.stdout.strip()


def _set_conditions(conn, scheme_id, conds):
    """替换方案的全部条件（删除后按序重建）。"""
    conn.execute("DELETE FROM scheme_conditions WHERE scheme_id=?", [scheme_id])
    for i, c in enumerate(conds or []):
        key = c.get("catalog_key")
        if not key:
            continue
        entry = filter_catalog.get_entry(key) or {}
        op = c.get("operator") or entry.get("operator", "gt")
        db.add_condition(conn, scheme_id, key, op, c.get("value"), c.get("value2"),
                         sort_order=i, enabled=1 if c.get("enabled", True) else 0)
    conn.commit()


def _scheme_detail(conn, scheme_id):
    s = db.get_scheme(conn, scheme_id)
    if not s:
        return None
    s = dict(s)
    s["conditions"] = db.list_conditions(conn, scheme_id)
    owner = db.get_user_by_id(conn, s.get("owner_id")) or {}
    s["owner_username"] = owner.get("username")
    return s


# --------------------------------------------------------------------------
# 鉴权
# --------------------------------------------------------------------------
def auth_login(conn, body):
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    u = db.get_user(conn, username)
    if not u or not auth.verify_password(str(password), u.get("password_hash")):
        return 401, {"error": "invalid_credentials"}
    token = auth.issue_token(auth.get_secret(conn), username)
    return 200, {"token": token, "user": _public_user(u)}


# --------------------------------------------------------------------------
# 许可证
# --------------------------------------------------------------------------
def license_activate(conn, user, body):
    res = licenses.activate(conn, user["id"], body.get("key", ""))
    if not res.get("ok"):
        return 400, res
    return 200, res


# --------------------------------------------------------------------------
# 筛选目录
# --------------------------------------------------------------------------
def filter_catalog_list():
    return 200, filter_catalog.get_catalog()


# --------------------------------------------------------------------------
# 方案
# --------------------------------------------------------------------------
def schemes_list(conn, user):
    if _role_ok(user, "admin"):          # owner/admin 看全部
        rows = db.list_schemes(conn)
    else:                                 # editor/viewer 看自己 + 共享
        rows = db.list_schemes(conn, user["id"])
    out = []
    for s in rows:
        s = dict(s)
        s["conditions"] = db.list_conditions(conn, s["id"])
        out.append(s)
    return 200, out


def schemes_create(conn, user, body):
    name = (body.get("name") or "").strip()
    if not name:
        return 400, {"error": "name_required"}
    description = body.get("description", "") or ""
    is_shared = 1 if body.get("is_shared", True) else 0
    sid = db.create_scheme(conn, name, user["id"], description=description, is_shared=is_shared)
    _set_conditions(conn, sid, body.get("conditions"))
    db.snapshot_version(conn, sid, user["id"], note="v1 初始版本")
    db.log_operation(conn, user["id"], "create", "scheme", sid, f"创建方案 {name}")
    return 201, _scheme_detail(conn, sid)


def scheme_get(conn, sid):
    d = _scheme_detail(conn, sid)
    if d is None:
        return 404, {"error": "scheme_not_found"}
    return 200, d


def scheme_update(conn, user, sid, body):
    s = db.get_scheme(conn, sid)
    if not s:
        return 404, {"error": "scheme_not_found"}
    name = body.get("name", s["name"])
    description = body.get("description", s.get("description", ""))
    is_shared = body.get("is_shared", bool(s.get("is_shared")))
    db.update_scheme(conn, sid, name=name, description=description,
                     is_shared=1 if is_shared else 0)
    _set_conditions(conn, sid, body.get("conditions"))
    db.snapshot_version(conn, sid, user["id"], note="更新版本")
    db.log_operation(conn, user["id"], "update", "scheme", sid, f"更新方案 {name}")
    return 200, _scheme_detail(conn, sid)


def scheme_delete(conn, user, sid):
    s = db.get_scheme(conn, sid)
    if not s:
        return 404, {"error": "scheme_not_found"}
    if not (_role_ok(user, "admin") or s["owner_id"] == user["id"]):
        return 403, {"error": "forbidden"}
    db.delete_scheme(conn, sid)
    db.log_operation(conn, user["id"], "delete", "scheme", sid, f"删除方案 {s.get('name')}")
    return 200, {"ok": True, "deleted": sid}


def scheme_pin(conn, user, sid, body):
    if not db.get_scheme(conn, sid):
        return 404, {"error": "scheme_not_found"}
    pinned = 1 if body.get("pinned", True) else 0
    db.pin_scheme(conn, sid, pinned)
    db.log_operation(conn, user["id"], "pin", "scheme", sid, f"置顶={pinned}")
    return 200, {"ok": True, "is_pinned": pinned}


def scheme_snapshot(conn, user, sid, body):
    if not db.get_scheme(conn, sid):
        return 404, {"error": "scheme_not_found"}
    note = body.get("note", "")
    vid = db.snapshot_version(conn, sid, user["id"], note=note)
    db.log_operation(conn, user["id"], "snapshot", "scheme", sid, f"手动快照 v{vid}")
    return 200, {"ok": True, "version_id": vid}


def scheme_versions(conn, sid):
    if not db.get_scheme(conn, sid):
        return 404, {"error": "scheme_not_found"}
    return 200, db.list_versions(conn, sid)


def scheme_rollback(conn, user, sid, body):
    if not db.get_scheme(conn, sid):
        return 404, {"error": "scheme_not_found"}
    vid = body.get("version_id")
    if vid is None:
        return 400, {"error": "version_id_required"}
    ok = db.rollback_version(conn, sid, int(vid))
    if not ok:
        return 404, {"error": "version_not_found"}
    db.log_operation(conn, user["id"], "rollback", "scheme", sid, f"回滚到版本 {vid}")
    return 200, {"ok": True}


def scheme_export(conn, user, sid):
    s = db.get_scheme(conn, sid)
    if not s:
        return 404, {"error": "scheme_not_found"}
    os.makedirs(SCHEMES_DIR, exist_ok=True)
    slug = _slug(s["name"]) or f"scheme-{sid}"
    data = _scheme_detail(conn, sid)
    fname = f"{slug}.json"
    fpath = os.path.join(SCHEMES_DIR, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    try:
        _zoe_sync(["save", f"export scheme {s['name']}"])
        git_out = _zoe_sync(["push"])
    except Exception as e:
        return 500, {"ok": False, "file": fpath, "error": str(e)}
    return 200, {"ok": True, "file": fpath, "git": git_out}


def scheme_pull(conn, user, sid):
    if not db.get_scheme(conn, sid):
        return 404, {"error": "scheme_not_found"}
    try:
        out = _zoe_sync(["pull"])
    except Exception as e:
        return 500, {"ok": False, "error": str(e)}
    return 200, {"ok": True, "output": out}


# --------------------------------------------------------------------------
# 应用筛选（付费墙）
# --------------------------------------------------------------------------
def screen(conn, user, body):
    if body.get("scheme_id"):
        sid = int(body["scheme_id"])
        conds_db = db.list_conditions(conn, sid)
        for c in conds_db:
            entry = filter_catalog.get_entry(c["catalog_key"]) or {}
            if entry.get("is_premium") and user.get("sub_tier") != "premium":
                return 402, {"error": "premium_required", "condition": c["catalog_key"]}
        result = screen_engine.screen_by_scheme(conn, sid)
        return 200, {"results": result, "scheme_id": sid, "count": len(result)}
    elif "conditions" in body:
        for c in body["conditions"]:
            entry = filter_catalog.get_entry(c.get("catalog_key")) or {}
            if entry.get("is_premium") and user.get("sub_tier") != "premium":
                return 402, {"error": "premium_required", "condition": c.get("catalog_key")}
        norm = []
        for c in body["conditions"]:
            entry = filter_catalog.get_entry(c.get("catalog_key")) or {}
            norm.append({
                "catalog_key": c.get("catalog_key"),
                "field": entry.get("field") or c.get("catalog_key"),
                "ftype": entry.get("ftype", "numeric"),
                "operator": c.get("operator") or entry.get("operator", "gt"),
                "value": c.get("value"),
                "value2": c.get("value2"),
                "enabled": c.get("enabled", True),
            })
        result = screen_engine.screen_by_conditions(conn, norm)
        return 200, {"results": result, "count": len(result)}
    return 400, {"error": "scheme_id_or_conditions_required"}


# --------------------------------------------------------------------------
# 操作日志
# --------------------------------------------------------------------------
def operation_logs(conn, user):
    return 200, db.list_logs(conn, user["id"], user.get("role", "viewer"))


# --------------------------------------------------------------------------
# 用户管理
# --------------------------------------------------------------------------
def users_list(conn):
    out = []
    for u in db.list_users(conn):
        u = dict(u)
        u.pop("password_hash", None)
        out.append(u)
    return 200, out


def users_create(conn, user, body):
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not username or not password:
        return 400, {"error": "username_password_required"}
    if db.get_user(conn, username):
        return 409, {"error": "user_exists"}
    role = body.get("role", "viewer")
    if role not in ROLE_RANK:
        role = "viewer"
    uid = db.create_user(conn, username, password,
                          display_name=body.get("display_name") or username, role=role)
    db.log_operation(conn, user["id"], "create", "user", uid, f"创建用户 {username}/{role}")
    u = db.get_user_by_id(conn, uid)
    u.pop("password_hash", None)
    return 201, u


def users_update_role(conn, uid, body):
    role = body.get("role")
    if role not in ROLE_RANK:
        return 400, {"error": "invalid_role"}
    if not db.get_user_by_id(conn, uid):
        return 404, {"error": "user_not_found"}
    db.update_user_role(conn, uid, role)
    return 200, {"ok": True, "id": uid, "role": role}


# --------------------------------------------------------------------------
# 路由分发（server.py 调用）
# --------------------------------------------------------------------------
def dispatch(conn, method, path, body, handler):
    user = auth.current_user(conn, handler)   # None 表示未登录/无效 token

    # ---- 公开端点 ----
    if method == "POST" and path == "/api/auth/login":
        return auth_login(conn, body)
    if method == "POST" and path == "/api/auth/logout":
        return 200, {"ok": True}

    # ---- 以下均需有效 token ----
    if not user:
        return 401, {"error": "unauthorized"}

    if method == "GET" and path == "/api/auth/me":
        return 200, {"user": _public_user(user)}
    if method == "GET" and path == "/api/filter-catalog":
        return filter_catalog_list()
    if method == "POST" and path == "/api/license/activate":
        return license_activate(conn, user, body)
    if method == "GET" and path == "/api/license/status":
        return 200, licenses.get_status(conn, user["id"])
    if method == "GET" and path == "/api/schemes":
        return schemes_list(conn, user)
    if method == "POST" and path == "/api/schemes":
        if not _role_ok(user, "editor"):
            return 403, {"error": "forbidden", "need": "editor"}
        return schemes_create(conn, user, body)
    if method == "GET" and path == "/api/operation-logs":
        return operation_logs(conn, user)
    if method == "POST" and path == "/api/screen":
        return screen(conn, user, body)
    if method == "GET" and path == "/api/users":
        if not _role_ok(user, "admin"):
            return 403, {"error": "forbidden", "need": "admin"}
        return users_list(conn)
    if method == "POST" and path == "/api/users":
        if not _role_ok(user, "admin"):
            return 403, {"error": "forbidden", "need": "admin"}
        return users_create(conn, user, body)

    # /api/schemes/<id> 及子资源
    m = _SCHEME_ID_RE.match(path)
    if m:
        sid = int(m.group(1))
        if method == "GET":
            return scheme_get(conn, sid)
        if method == "PUT":
            if not _role_ok(user, "editor"):
                return 403, {"error": "forbidden", "need": "editor"}
            return scheme_update(conn, user, sid, body)
        if method == "DELETE":
            return scheme_delete(conn, user, sid)
        return 405, {"error": "method_not_allowed"}

    m = _SCHEME_SUB_RE.match(path)
    if m:
        sid = int(m.group(1))
        action = m.group(2)
        if action == "versions":
            if method != "GET":
                return 405, {"error": "method_not_allowed"}
            return scheme_versions(conn, sid)
        # pin/snapshot/rollback/export/pull 均需 editor 及以上
        if not _role_ok(user, "editor"):
            return 403, {"error": "forbidden", "need": "editor"}
        if method != "POST":
            return 405, {"error": "method_not_allowed"}
        if action == "pin":
            return scheme_pin(conn, user, sid, body)
        if action == "snapshot":
            return scheme_snapshot(conn, user, sid, body)
        if action == "rollback":
            return scheme_rollback(conn, user, sid, body)
        if action == "export":
            return scheme_export(conn, user, sid)
        if action == "pull":
            return scheme_pull(conn, user, sid)

    # /api/users/<id>
    m = _USER_ID_RE.match(path)
    if m:
        uid = int(m.group(1))
        if method == "PUT":
            if user.get("role") != "owner":
                return 403, {"error": "forbidden", "need": "owner"}
            return users_update_role(conn, uid, body)
        return 405, {"error": "method_not_allowed"}

    return 404, {"error": "unknown_path"}
