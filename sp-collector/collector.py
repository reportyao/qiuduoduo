#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""竞彩 SP 采集器 v0.1 + 推送（本机版：家宽出口，服务器 567 被拒）"""
import json, sqlite3, time, urllib.request, os, sys, subprocess
from datetime import datetime, timezone, timedelta

API = "https://webapi.sporttery.cn/gateway/jc/football/getMatchCalculatorV1.qry?poolCode=hhad,had&channel=c"
HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": "https://www.sporttery.cn/"}
HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "sp_data.db")
REMOTE = "ubuntu@43.128.24.244:/home/ubuntu/jieqiu-sp/"
CN = timezone(timedelta(hours=8))

def now_cn(): return datetime.now(CN).strftime("%Y-%m-%dT%H:%M:%S+08:00")

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
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def parse(d):
    rows_m, rows_s = [], []
    ts = now_cn()
    for block in d.get("value", {}).get("matchInfoList", []):
        league = block.get("leagueAbbName", "")
        for m in block.get("subMatchList", []):
            mid = str(m.get("matchId") or f"{m.get('matchDate','')}{m.get('matchNumStr','')}")
            rows_m.append((m.get("matchNumStr",""), mid, league,
                           m.get("homeTeamAbbName",""), m.get("awayTeamAbbName",""),
                           f"{m.get('matchDate','')} {m.get('matchTime','')}",
                           1 if m.get("single") == 1 else 0))
            for pool in ("had", "hhad"):
                p = m.get(pool)
                if not p: continue
                try:
                    rows_s.append((mid, pool, str(p.get("goalLine","")),
                                   float(p.get("h",0)), float(p.get("d",0)), float(p.get("a",0)), ts))
                except (TypeError, ValueError): pass
    return rows_m, rows_s, ts

def push():
    try:
        import paramiko
        c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect("43.128.24.244", username="ubuntu", password="lingjiu123@", timeout=20)
        s = c.open_sftp()
        s.put(DB, "/home/ubuntu/jieqiu-sp/sp_data.db.tmp")  # 先写临时名
        s.close()
        _, o, e = c.exec_command("mv -f /home/ubuntu/jieqiu-sp/sp_data.db.tmp /home/ubuntu/jieqiu-sp/sp_data.db")
        o.channel.recv_exit_status()  # 原子改名后云端才见完整文件
        c.close()
        print(f"[{now_cn()}] 备份推送完成", flush=True)
    except Exception as e:
        print(f"[{now_cn()}] 推送失败（下轮重试）: {str(e)[:80]}", flush=True)

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
            print(f"[{ts}] 场次 {len(rows_m)} · 新快照 {len(rows_s)} · 累计 {total}", flush=True)
            if time.time() - last_push > 1800:
                push(); last_push = time.time()
        except Exception as e:
            fails += 1
            print(f"[{now_cn()}] 失败 x{fails}: {str(e)[:100]}", flush=True)
            if fails >= 20: print("连续失败，退出换路", flush=True); sys.exit(1)
        time.sleep(300)

if __name__ == "__main__":
    main()
