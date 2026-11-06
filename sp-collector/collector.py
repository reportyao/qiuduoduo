#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""竞彩 SP 采集器 v0.1 + 推送（本机版：家宽出口，服务器 567 被拒）"""
import json, socket, sqlite3, time, urllib.request, os, sys
from datetime import datetime, timezone, timedelta

API = "https://webapi.sporttery.cn/gateway/jc/football/getMatchCalculatorV1.qry?poolCode=hhad,had&channel=c"
HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": "https://www.sporttery.cn/"}
HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "sp_data.db")
REMOTE_HOST = os.environ.get("JQ_COLLECTOR_HOST", "43.128.24.244")
REMOTE_USER = os.environ.get("JQ_COLLECTOR_USER", "ubuntu")
REMOTE_PASSWORD = os.environ.get("JQ_COLLECTOR_PASSWORD", "")
REMOTE_DIR = "/home/ubuntu/jieqiu-sp"
# 服务器机房 IP 会被体彩 WAF 567；服务器模式必须走住宅代理。
PROXY = os.environ.get("JQ_COLLECTOR_PROXY", "").strip()
API_BASE = os.environ.get("JQ_COLLECTOR_API", "http://43.128.24.244:8100").rstrip("/")
TOKEN = os.environ.get("JQ_COLLECTOR_TOKEN", "").strip()
HOSTNAME = socket.gethostname()
STARTED_AT = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
STATE = {"last_success_at": None, "last_error": "", "cycle": 0,
         "matches": 0, "snapshots_total": 0, "last_push_at": None}
CN = timezone(timedelta(hours=8))

def now_cn(): return datetime.now(CN).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def heartbeat() -> bool:
    """上报状态；返回 True 表示服务器要求重启本进程。"""
    if not TOKEN:
        return False
    body = json.dumps({
        "host": HOSTNAME, "pid": str(os.getpid()), "version": "v0.2",
        "started_at": STARTED_AT,
        "last_success_at": STATE["last_success_at"],
        "last_error": STATE["last_error"],
        "cycle": STATE["cycle"], "matches": STATE["matches"],
        "snapshots_total": STATE["snapshots_total"],
        "last_push_at": STATE["last_push_at"],
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        API_BASE + "/collector/heartbeat", data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8") or "{}")
        return bool(data.get("restart"))
    except Exception as e:  # noqa: BLE001 - 心跳失败不能影响采集
        print(f"[{now_cn()}] 心跳失败: {str(e)[:90]}", flush=True)
        return False

def init_db():
    con = sqlite3.connect(DB)
    con.executescript("""
CREATE TABLE IF NOT EXISTS matches (match_no TEXT, match_id TEXT, league TEXT,
  home TEXT, away TEXT, kickoff TEXT, single_flag INTEGER, PRIMARY KEY (match_id));
CREATE TABLE IF NOT EXISTS sp_snapshots (match_id TEXT, pool TEXT, goal_line TEXT,
  sp_h REAL, sp_d REAL, sp_a REAL, captured_at TEXT,
  PRIMARY KEY (match_id, pool, captured_at));""")
    con.commit(); return con

def fetch():
    req = urllib.request.Request(API, headers=HDR)
    if PROXY:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
        with opener.open(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def parse(d):
    rows_m, rows_s = [], []
    ts = now_cn()
    for block in d.get("value", {}).get("matchInfoList", []):
        # 联赛名在 subMatch 上（顶层 block 只有 businessDate）；旧代码读 block 会全空。
        block_league = block.get("leagueAbbName", "")
        for m in block.get("subMatchList", []):
            league = m.get("leagueAbbName") or block_league
            mid = str(m.get("matchId") or f"{m.get('matchDate','')}{m.get('matchNumStr','')}")
            rows_m.append((m.get("matchNumStr",""), mid, league,
                           m.get("homeTeamAbbName",""), m.get("awayTeamAbbName",""),
                           f"{m.get('matchDate','')} {m.get('matchTime','')}",
                           1 if m.get("single") == 1 else 0))
            for pool in ("had", "hhad"):
                p = m.get(pool)
                if not p: continue
                try:
                    vals = (float(p.get("h", 0)), float(p.get("d", 0)), float(p.get("a", 0)))
                    if min(vals) <= 1.0:
                        continue  # 与后端契约一致：SP 必须 > 1
                    rows_s.append((mid, pool, str(p.get("goalLine", "")), *vals, ts))
                except (TypeError, ValueError): pass
    return rows_m, rows_s, ts

def push():
    try:
        import paramiko
        if not REMOTE_PASSWORD:
            raise RuntimeError("未设置 JQ_COLLECTOR_PASSWORD（不要把密码写进代码）")
        c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(REMOTE_HOST, username=REMOTE_USER, password=REMOTE_PASSWORD, timeout=20)
        s = c.open_sftp()
        s.put(DB, f"{REMOTE_DIR}/sp_data.db.tmp")  # 先写临时名
        s.close()
        _, o, e = c.exec_command(f"mv -f {REMOTE_DIR}/sp_data.db.tmp {REMOTE_DIR}/sp_data.db")
        o.channel.recv_exit_status()  # 原子改名后云端才见完整文件
        c.close()
        STATE["last_push_at"] = now_cn()
        print(f"[{now_cn()}] 备份推送完成", flush=True)
        return True
    except Exception as e:
        print(f"[{now_cn()}] 推送失败（下轮重试）: {str(e)[:80]}", flush=True)
        return False

def main():
    con = init_db()
    print(f"[{now_cn()}] 采集器 v0.1 启动（本机版）", flush=True)
    fails = 0; last_push = 0; cycle = 0
    while True:
        try:
            rows_m, rows_s, ts = parse(fetch())
            cur = con.cursor()
            cur.executemany("INSERT OR REPLACE INTO matches VALUES (?,?,?,?,?,?,?)", rows_m)
            cur.executemany("INSERT OR IGNORE INTO sp_snapshots VALUES (?,?,?,?,?,?,?)", rows_s)
            con.commit(); fails = 0; cycle += 1
            total = con.execute("SELECT COUNT(*) FROM sp_snapshots").fetchone()[0]
            STATE.update(last_success_at=now_cn(), last_error="", cycle=cycle,
                         matches=len(rows_m), snapshots_total=total)
            print(f"[{ts}] 场次 {len(rows_m)} · 新快照 {len(rows_s)} · 累计 {total}", flush=True)
            if time.time() - last_push > 1800:
                if push():
                    last_push = time.time()
        except Exception as e:
            fails += 1
            STATE["last_error"] = str(e)[:280]
            print(f"[{now_cn()}] 失败 x{fails}: {str(e)[:100]}", flush=True)
            if fails >= 20: print("连续失败，退出换路", flush=True); sys.exit(1)
        if heartbeat():
            print(f"[{now_cn()}] 服务器要求重启采集器", flush=True)
            sys.exit(75)
        time.sleep(300)

if __name__ == "__main__":
    main()
