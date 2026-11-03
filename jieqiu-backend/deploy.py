"""W2 部署脚本：本机 → 腾讯云 VPS（paramiko）。

步骤：打包上传 → venv + 依赖 → systemd 常驻 → 云端同步 cron → 冒烟验证。
用法：python deploy.py
"""
from __future__ import annotations

import io
import os
import tarfile
import time

import paramiko

HOST, USER, PWD = "43.128.24.244", "ubuntu", "lingjiu123@"
ROOT = "/home/ubuntu/jieqiu-backend"
DATA = "/home/ubuntu/jieqiu-data"   # 数据与代码分离：部署清代码目录绝不清数据
APP_DIR = os.path.dirname(os.path.abspath(__file__))


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str]:
    _, out, err = ssh.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", "replace")
    e = err.read().decode("utf-8", "replace")
    code = out.channel.recv_exit_status()
    return code, (o + ("\n[stderr] " + e if e.strip() else ""))


def make_tar() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel in ("app", "requirements.txt", "README.md"):
            full = os.path.join(APP_DIR, rel)
            tar.add(full, arcname=f"jieqiu-backend/{rel}")
        # DC 模型底座（xG 历史数据）随包上传
        xg = os.path.abspath(os.path.join(APP_DIR, "..", "w1-validation", "xg_matches.csv"))
        if os.path.exists(xg):
            tar.add(xg, arcname="jieqiu-backend/xg_matches.csv")
    buf.seek(0)
    return buf.read()


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    print("[1/6] connected")

    code, out = run(ssh, "python3 --version && python3 -m venv --help >/dev/null && echo venv-ok")
    print("[2/6] env:", out.strip()[:80])
    assert "venv-ok" in out, "服务器缺 python3-venv：sudo apt install -y python3-venv python3-pip"

    # 上传代码包（只清代码目录；DB/xG dumps 在 DATA，永不触碰）
    data = make_tar()
    sftp = ssh.open_sftp()
    with sftp.file("/tmp/jieqiu-backend.tar.gz", "wb") as f:
        f.write(data)
    code, out = run(ssh, f"mkdir -p {DATA}/xg_dumps && "
                         f"if [ -f {ROOT}/jieqiu.db ] && [ ! -f {DATA}/jieqiu.db ]; then "
                         f"mv {ROOT}/jieqiu.db {DATA}/jieqiu.db; echo migrated-old-db; fi; "
                         f"if [ -d {ROOT}/xg_dumps ] && [ ! -d {DATA}/xg_dumps_bak ]; then "
                         f"cp -r {ROOT}/xg_dumps {DATA}/xg_dumps_bak 2>/dev/null; fi; "
                         f"cd {ROOT}/.. && rm -rf jieqiu-backend && tar xzf /tmp/jieqiu-backend.tar.gz && echo deploy-ok")
    print("[3/6] code uploaded", len(data), "bytes |", out.strip().splitlines()[-1])

    code, out = run(ssh, f"cd {ROOT} && python3 -m venv venv && venv/bin/pip install -q -r requirements.txt 2>&1 | tail -2 && echo deps-ok")
    print("[4/6] deps:", out.strip().splitlines()[-1])
    assert "deps-ok" in out

    # JWT 密钥：首次部署生成并固定（幂等：已有 unit 中保留）
    import secrets as _secrets
    code, out = run(ssh, "grep -o 'JQ_JWT_SECRET=[a-f0-9]*' /etc/systemd/system/jieqiu-backend.service 2>/dev/null | head -1")
    jwt_secret = ""
    if "JQ_JWT_SECRET=" in out:
        jwt_secret = out.strip().split("JQ_JWT_SECRET=")[1]
    else:
        jwt_secret = _secrets.token_hex(32)
    print("[jwt] secret", "kept" if "JQ_JWT_SECRET=" in out else "generated")

    # systemd 单元
    unit = f"""[Unit]
Description=jieqiu backend (W2)
After=network.target

[Service]
WorkingDirectory={ROOT}
Environment=JQ_DATABASE_URL=sqlite:////{DATA}/jieqiu.db
Environment=JQ_ENV=prod
Environment=JQ_XG_DATA_PATH={ROOT}/xg_matches.csv
Environment=JQ_XG_EXTRA_DIR={DATA}/xg_dumps
Environment=JQ_FREEZE_BASELINE={DATA}/freeze_baseline.json
Environment=JQ_JWT_SECRET={jwt_secret}
Environment=JQ_CONSOLE_PASSWORD=Jq@Console#2026
Environment=JQ_CORS_EXTRA_ORIGINS=http://43[.]128[.]24[.]244:8899
ExecStart={ROOT}/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8100
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
    with sftp.file("/tmp/jieqiu-backend.service", "w") as f:
        f.write(unit)
    code, out = run(ssh, f"echo '{PWD}' | sudo -S mv /tmp/jieqiu-backend.service /etc/systemd/system/jieqiu-backend.service && echo unit-ok")
    assert "unit-ok" in out, out
    # 同步 cron：每 30 分钟读采集器 SFTP 推送来的 DB 并重建判决（env 与 systemd 一致；DB 在 DATA）
    envs = (f"JQ_DATABASE_URL=sqlite:////{DATA}/jieqiu.db "
            f"JQ_XG_DATA_PATH={ROOT}/xg_matches.csv JQ_XG_EXTRA_DIR={DATA}/xg_dumps")
    cron = (f"*/30 * * * * cd {ROOT} && {envs} "
            f"venv/bin/python -m app.seed /home/ubuntu/jieqiu-sp/sp_data.db >> {ROOT}/sync.log 2>&1\n"
            # 每周一 06:10 校准回测（校准数据周更，防腐烂）
            f"10 6 * * 1 cd {ROOT} && {envs} "
            f"venv/bin/python -m app.backtest_cli weekly >> {ROOT}/backtest.log 2>&1\n"
            # 每日 03:00 注销期满清除（7 天冷静期）
            f"0 3 * * * cd {ROOT} && {envs} "
            f"venv/bin/python -m app.purge_cli >> {ROOT}/purge.log 2>&1\n"
            # 助理 worker：每分钟事件/扇出/推送（Android JPush；未配置则 dry-run）
            f"* * * * * cd {ROOT} && {envs} JQ_DAILY_BRIEF_HOUR=19 "
            f"venv/bin/python -m app.features.assistant.worker --once >> {ROOT}/assistant.log 2>&1\n")
    run(ssh, f'echo "{cron.strip()}" > /tmp/jqcron && crontab -l 2>/dev/null | grep -v jieqiu-backend | cat - /tmp/jqcron | crontab - && echo cron-ok')

    # 上传当前采集器数据并跑一次种子
    sftp.put(os.path.join(APP_DIR, "..", "sp-collector", "sp_data.db"), "/tmp/sp_data.db")
    code, out = run(ssh, f"cd {ROOT} && JQ_DATABASE_URL=sqlite:////{DATA}/jieqiu.db "
                         f"JQ_XG_DATA_PATH={ROOT}/xg_matches.csv JQ_XG_EXTRA_DIR={DATA}/xg_dumps "
                         f"venv/bin/python -m app.seed /tmp/sp_data.db 2>&1 | tail -3")
    print("[5/6] seed on server:\n", out.strip())

    code, out = run(ssh, f"echo '{PWD}' | sudo -S systemctl daemon-reload 2>/dev/null && "
                         f"echo '{PWD}' | sudo -S systemctl enable jieqiu-backend 2>/dev/null && "
                         f"echo '{PWD}' | sudo -S systemctl restart jieqiu-backend 2>/dev/null && "
                         f"sleep 2 && systemctl is-active jieqiu-backend && curl -s http://127.0.0.1:8100/health")
    print("[6/6] service:\n", out.strip())
    sftp.close()
    ssh.close()
    print("DEPLOY DONE")


if __name__ == "__main__":
    main()
