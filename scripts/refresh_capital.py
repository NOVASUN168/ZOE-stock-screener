# -*- coding: utf-8 -*-
"""
refresh_capital.py —— 离线资金流数据刷新工具（非运行时依赖）

用途：
    为 stocks 表补全 5 个资金流 / 游资相关列的真实数据：
      - main_inflow_20d  近 20 交易日主力净流入总额（仅累加主力净流入为正的交易日），单位 万元
      - main_outflow_20d 近 20 交易日主力净流出总额（仅累加主力净流入为负的交易日之绝对值），单位 万元
      - net_capital_flow 近 20 交易日主力净流入合计（= 所有主力净流入求和，可正可负），单位 万元
      - hotmoney_ratio   近 20 日 超大单+大单 净流入 占 全口径净流入绝对值之和 的比例，存为百分比，范围约 [-100,100]（负值=被小/中单主导）
      - hotmoney_flag    近 30 日龙虎榜上榜次数 >= 3 则置 1（游资主导），否则 0

数据源（东财，已实测）：
    1) 个股资金流（120 日日级）：push2his.eastmoney.com/api/qt/stock/fflow/daykline/get
    2) 龙虎榜上榜记录（datacenter）：datacenter-web.eastmoney.com/api/data/v1/get

依赖：仅 Python 标准库（urllib.request / json / sqlite3 / time / math）。
      【运行需要联网】——本脚本属于离线数据刷新工具，与“零依赖运行时”不冲突：
      它不在 Web 服务请求路径上，只在需要补全数据时由人工/定时任务离线执行。

单位说明：东财返回字段单位为「元」，写回时统一换算为「万元」（÷1e4），
          以与 schema.sql / filter_catalog.py 中声明的「万元」单位保持一致。
          hotmoney_ratio 按任务公式直接存储为 [-1,1] 区间的比例（不作百分化）。
"""

import sqlite3
import json
import time
import math
import sys
import io

import urllib.request

import db  # scripts/db.py：提供 update(conn, sid, data) 与 DEFAULT_DB

# 强制 stdout/stderr 使用 UTF-8，避免重定向到文件时因控制台 cp1252 编码崩溃
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

# 东财接口请求头（Connection: close 避免复用被服务端 reset 的 keep-alive 连接）
_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://quote.eastmoney.com/",
    "Connection": "close",
}
_HEADERS_LHB = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://data.eastmoney.com/",
    "Connection": "close",
}

# 单只股票请求间隔（秒），避免触发东财限流封 IP
_REQ_INTERVAL = 1.2
# 网络超时（秒）——偏短，让被限流的请求快速失败进入重试/下一轮，避免长挂
_TIMEOUT = 8
# 资金流取最后 N 个交易日
_FLOW_WINDOW = 20
# 龙虎榜“近 N 天”窗口
_LHB_WINDOW_DAYS = 30
# 龙虎榜上榜次数阈值
_LHB_THRESHOLD = 3


def _http_get_json(url, headers=None):
    """发起 GET 请求并解析 JSON。失败抛异常，由调用方捕获。
    内置重试：东财对密集请求会 reset 连接（Remote end closed connection），
    单次失败不应判定整只股票失败，重试 3 次（指数退避）以提升离线刷新成功率。
    全部重试仍失败则抛异常，由调用方捕获并按“跳过该股票”处理。
    """
    hdrs = headers or _HEADERS
    last_err = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw)
        except Exception as e:
            last_err = e
            if attempt < 1:
                time.sleep(1.5 * (attempt + 1))  # 1.5s 退避
    raise last_err


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def _secid_of(code):
    """从带市场前缀的代码构造东财 secid。
    sh688981 -> 1.688981 ; sz300308 -> 0.300308 ；hk 开头返回 None（东财不支持）。
    """
    if code.startswith("sh"):
        return "1." + code[2:]
    if code.startswith("sz"):
        return "0." + code[2:]
    return None  # 港股等东财资金流接口不支持


def _numeric_part(code):
    """返回代码中的纯数字部分（用于龙虎榜 SECURITY_CODE 过滤）。"""
    return "".join(ch for ch in code if ch.isdigit())


def _date_n_days_ago_str(n):
    """返回 n 天前的日期字符串 YYYY-MM-DD（仅用 time 标准库）。"""
    t = time.localtime(time.time() - n * 86400)
    return time.strftime("%Y-%m-%d", t)


# ---------------------------------------------------------------------------
# 数据源 1：个股资金流日线
# ---------------------------------------------------------------------------
def fetch_capital_flow(secid):
    """拉取个股资金流日线，返回最近 FLOW_WINDOW 个交易日的解析结果 dict，或 None。"""
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
        "?secid=" + secid +
        "&fields1=f1,f2,f3,f7"
        "&fields2=f51,f52,f53,f54,f55,f56,f57"
        "&lmt=120"
    )
    data = _http_get_json(url)
    if not data or not isinstance(data, dict):
        return None
    klines = (data.get("data") or {}).get("klines")
    if not klines:
        return None

    rows = []
    for line in klines:
        if not line:
            continue
        parts = line.split(",")
        if len(parts) < 6:
            continue
        try:
            day = parts[0]
            main_net = float(parts[1])    # 主力净流入（元，可为负）
            small_net = float(parts[2])   # 小单净流入
            mid_net = float(parts[3])     # 中单净流入
            large_net = float(parts[4])   # 大单净流入
            super_net = float(parts[5])   # 超大单净流入
        except (ValueError, IndexError):
            continue
        rows.append({
            "day": day, "main_net": main_net, "small_net": small_net,
            "mid_net": mid_net, "large_net": large_net, "super_net": super_net,
        })

    if not rows:
        return None
    # 取最后 FLOW_WINDOW 个有效交易日
    window = rows[-_FLOW_WINDOW:]
    return {"window": window}


def compute_capital_metrics(flow):
    """根据窗口内日级数据计算 5 列中的资金流 3 列（+ hotmoney_ratio）。
    返回 dict：main_inflow_20d / main_outflow_20d / net_capital_flow / hotmoney_ratio（单位：万元 / [-1,1]）。
    """
    window = flow["window"]
    inflow = 0.0     # 主力净流入为正的交易日累加（元）
    outflow = 0.0    # 主力净流入为负的交易日，绝对值累加（元）
    net = 0.0        # 所有主力净流入求和（元）

    num_large_super = 0.0   # Σ(超大单 + 大单)
    denom_full = 0.0        # Σ(|主力| + |大| + |中| + |小| + |超大|)

    for r in window:
        mn = r["main_net"]
        net += mn
        if mn > 0:
            inflow += mn
        elif mn < 0:
            outflow += abs(mn)

        ls = r["large_net"] + r["super_net"]
        num_large_super += ls
        denom_full += (abs(r["main_net"]) + abs(r["large_net"]) +
                       abs(r["mid_net"]) + abs(r["small_net"]) + abs(r["super_net"]))

    # 元 -> 万元
    main_inflow_20d = round(inflow / 1e4, 2)
    main_outflow_20d = round(outflow / 1e4, 2)
    net_capital_flow = round(net / 1e4, 2)

    # 游资参与度比例：按系统统一口径存为「百分比」(0-100)，范围约 [-100, 100]
    # 负值表示被小/中单主导（对 lt 排除语义无碍）。
    # 计算式 = (超大单+大单 净流入) / (全口径净流入绝对值之和)，再 ×100。
    if denom_full > 0:
        hotmoney_ratio = round(num_large_super / denom_full * 100.0, 2)
    else:
        hotmoney_ratio = 0.0

    return {
        "main_inflow_20d": main_inflow_20d,
        "main_outflow_20d": main_outflow_20d,
        "net_capital_flow": net_capital_flow,
        "hotmoney_ratio": hotmoney_ratio,
    }


# ---------------------------------------------------------------------------
# 数据源 2：龙虎榜上榜记录 -> hotmoney_flag
# ---------------------------------------------------------------------------
def fetch_lhb_count(code):
    """统计近 LHB_WINDOW_DAYS 天龙虎榜上榜次数。返回次数（int）。
    若接口异常/无数据，返回 0（不视为错误，仅 WARN）。
    若返回数据拿不到日期字段，则退化为统计返回前 N 条近似（并打印 WARN 说明）。
    """
    sec_code = _numeric_part(code)
    # 过滤值含括号与双引号，需对双引号做百分号编码
    filter_val = '(SECURITY_CODE="%s")' % sec_code
    filter_enc = filter_val.replace('"', "%22")
    url = (
        "https://datacenter-web.eastmoney.com/api/data/v1/get"
        "?reportName=RPT_DAILYBILLBOARD_DETAILSNEW"
        "&columns=ALL"
        "&filter=" + filter_enc +
        "&pageSize=100"
        "&sortColumns=TRADE_DATE"
        "&sortTypes=-1"
        "&source=WEB"
        "&client=WEB"
    )
    try:
        data = _http_get_json(url, _HEADERS_LHB)
    except Exception as e:
        print("  [WARN] 龙虎榜接口请求失败(%s): %s" % (code, e))
        return 0

    if not data or not isinstance(data, dict):
        return 0
    # 兼容多种返回结构
    result = data.get("result")
    if isinstance(result, dict):
        items = result.get("data")
    elif isinstance(result, list):
        items = result
    else:
        items = data.get("data")
    if not items:
        return 0

    cutoff = _date_n_days_ago_str(_LHB_WINDOW_DAYS)

    dated = []
    no_date = 0
    for it in items:
        td = it.get("TRADE_DATE") if isinstance(it, dict) else None
        if not td:
            no_date += 1
            continue
        day_str = str(td)[:10]
        if day_str >= cutoff:   # 字符串日期比较（YYYY-MM-DD 字典序=时间序）
            dated.append(day_str)

    if no_date and not dated:
        # 拿不到日期字段：退化为统计返回的前 N 条近似（龙虎榜数据通常近因排序）
        print("  [WARN] %s 龙虎榜记录缺少日期字段，退化为统计返回前 %d 条近似。"
              % (code, len(items)))
        return len(items)

    return len(dated)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def refresh_one(conn, sid, code):
    """刷新单只股票的资金流 5 列。返回填充后的 dict（失败返回 None）。"""
    secid = _secid_of(code)
    if secid is None:
        # 港股（hk 开头）东财资金流接口不支持，跳过保持 NULL
        print("  [SKIP] %s 港股：东财资金流接口不支持，保持 NULL" % code)
        return None

    # ---- 资金流（请求间隔保护）----
    time.sleep(_REQ_INTERVAL)
    flow = None
    try:
        flow = fetch_capital_flow(secid)
    except Exception as e:
        print("  [WARN] %s 资金流拉取失败: %s" % (code, e))

    if flow is None:
        print("  [WARN] %s 无资金流数据，跳过该股票" % code)
        return None

    metrics = compute_capital_metrics(flow)

    # ---- 龙虎榜（请求间隔保护）----
    time.sleep(_REQ_INTERVAL)
    lhb_count = fetch_lhb_count(code)
    hotmoney_flag = 1 if lhb_count >= _LHB_THRESHOLD else 0
    metrics["hotmoney_flag"] = hotmoney_flag
    metrics["_lhb_count"] = lhb_count  # 仅用于打印摘要

    # ---- 写回 ----
    db.update(conn, sid, {
        "main_inflow_20d": metrics["main_inflow_20d"],
        "main_outflow_20d": metrics["main_outflow_20d"],
        "net_capital_flow": metrics["net_capital_flow"],
        "hotmoney_ratio": metrics["hotmoney_ratio"],
        "hotmoney_flag": hotmoney_flag,
    })
    return metrics


def refresh_all(conn):
    """遍历所有 A 股（code 以 sh/sz 开头），逐只刷新资金流。返回统计 dict。
    东财对密集请求会 reset 连接，单次跑可能部分失败；故首轮后对内网失败的 A 股
    再追加若干轮重试（轮间长暂停），单条调用幂等，直至全部成功或达到最大重试轮数。
    """
    MAX_RETRY_ROUNDS = 6          # 首轮之外的重试轮数
    RETRY_ROUND_PAUSE = 6.0       # 每轮重试之间的停顿（秒）

    rows = conn.execute("SELECT id, code, name FROM stocks").fetchall()
    filled, skipped_hk, failed = [], [], []
    hotmoney_on = []  # hotmoney_flag=1 的 code 列表
    summary = []

    # 首轮：区分 A 股与港股，港股直接跳过
    pending = []  # 待刷新的 A 股 (sid, code, name)
    for r in rows:
        sid, code, name = r["id"], r["code"], r["name"]
        print("[%s] %s (%s) ..." % (code, name, "A股" if (code[:2] in ("sh", "sz")) else "其它"))
        if code[:2] not in ("sh", "sz"):
            skipped_hk.append(code)
            print("  [SKIP] %s 非 A 股（港股/其它），跳过" % code)
            continue
        pending.append((sid, code, name))

    def _process(sid, code, name):
        """刷新单只 A 股；成功返回 metrics dict，失败/跳过返回 None。"""
        try:
            m = refresh_one(conn, sid, code)
        except Exception as e:
            print("  [WARN] %s 刷新异常: %s" % (code, e))
            return None
        if m is None:
            return None
        if m["hotmoney_flag"] == 1:
            hotmoney_on.append(code)
        summary.append({
            "code": code, "name": name,
            "main_inflow_20d": m["main_inflow_20d"],
            "main_outflow_20d": m["main_outflow_20d"],
            "net_capital_flow": m["net_capital_flow"],
            "hotmoney_ratio": m["hotmoney_ratio"],
            "hotmoney_flag": m["hotmoney_flag"],
            "lhb_count": m.get("_lhb_count"),
        })
        print("  [OK] net_capital_flow=%s 万元, hotmoney_ratio=%s, hotmoney_flag=%d (lhb=%s)"
              % (m["net_capital_flow"], m["hotmoney_ratio"], m["hotmoney_flag"], m.get("_lhb_count")))
        return m

    # 首轮
    still_pending = []
    for sid, code, name in pending:
        m = _process(sid, code, name)
        if m is None:
            still_pending.append((sid, code, name))
            failed.append(code)
        else:
            filled.append(code)

    # 重试轮：仅对失败的 A 股重试
    round_no = 0
    while still_pending and round_no < MAX_RETRY_ROUNDS:
        round_no += 1
        print("\n--- 重试轮 %d/%d：仍有 %d 只 A 股待填充，暂停 %.0fs 后重试 ---"
              % (round_no, MAX_RETRY_ROUNDS, len(still_pending), RETRY_ROUND_PAUSE))
        time.sleep(RETRY_ROUND_PAUSE)
        next_pending = []
        for sid, code, name in still_pending:
            m = _process(sid, code, name)
            if m is None:
                next_pending.append((sid, code, name))
            else:
                filled.append(code)
                # 从 failed 中移除已成功项
                if code in failed:
                    failed.remove(code)
        still_pending = next_pending

    if still_pending:
        print("\n[WARN] 达到最大重试轮数后仍失败 %d 只：%s" % (len(still_pending), [c for _, c, _ in still_pending]))

    return {
        "filled": filled,
        "skipped_hk": skipped_hk,
        "failed": failed,
        "hotmoney_on": hotmoney_on,
        "summary": summary,
    }


def main():
    conn = sqlite3.connect(db.DEFAULT_DB)
    conn.row_factory = sqlite3.Row
    try:
        print("=== ZOE 资金流刷新开始 | DB=%s ===" % db.DEFAULT_DB)
        stats = refresh_all(conn)
        print("\n=== 刷新完成 ===")
        print("填充 A 股数量   : %d" % len(stats["filled"]))
        print("跳过(非A股/港股): %d -> %s" % (len(stats["skipped_hk"]), stats["skipped_hk"]))
        print("失败/无数据     : %d -> %s" % (len(stats["failed"]), stats["failed"]))
        print("hotmoney_flag=1 : %s" % (stats["hotmoney_on"] or "无"))
        print("\n--- 逐只摘要 ---")
        for s in stats["summary"]:
            print("%(code)s %(name)s | net=%(net_capital_flow)s万 ratio=%(hotmoney_ratio)s flag=%(hotmoney_flag)d lhb=%(lhb_count)s" % s)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
