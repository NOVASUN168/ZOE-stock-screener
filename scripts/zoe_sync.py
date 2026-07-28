# -*- coding: utf-8 -*-
"""
stock-screener · 极简 git 同步工具（零依赖），供方案导出 / 拉取端点调用。
用法：
  python scripts/zoe_sync.py save "message"   # git add -A + commit
  python scripts/zoe_sync.py push              # git push
  python scripts/zoe_sync.py pull              # git pull
退出码非 0 表示失败（调用方据此返回 500）。
"""
import os
import sys
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(args):
    r = subprocess.run(["git"] + args, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip()
        sys.stderr.write(msg + "\n")
        sys.exit(1)
    out = r.stdout.strip()
    print(out)
    return out


def main():
    if len(sys.argv) < 2:
        print("usage: zoe_sync.py [save|push|pull] [message]")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "save":
        msg = sys.argv[2] if len(sys.argv) > 2 else "sync"
        _run(["add", "-A"])
        _run(["commit", "-m", msg])
    elif cmd == "push":
        _run(["push"])
    elif cmd == "pull":
        _run(["pull"])
    else:
        print("unknown cmd")
        sys.exit(1)


if __name__ == "__main__":
    main()
