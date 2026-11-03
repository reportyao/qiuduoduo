"""W2 部署脚本：本机 → 腾讯云 VPS（paramiko）。

步骤：打包上传 → venv + 依赖 → systemd 常驻 → 云端同步 cron → 冒烟验证。
用法：python deploy.py
"""
from __future__ import annotations

import io
import os
import shlex
import tarfile

import paramiko

HOST = os.environ.get("JQ_DEPLOY_HOST", "43.128.24.244")
USER = os.environ.get("JQ_DEPLOY_USER", "ubuntu")
PWD = os.environ.get("JQ_DEPLOY_PASSWORD", "")
CONSOLE_PASSWORD = os.environ.get("JQ_CONSOLE_PASSWORD", "")
ROOT = "/home/ubuntu/jieqiu-backend"
DATA = "/home/ubuntu/jieqiu-data"   # 数据与代码分离：部署清代码目录绝不清数据
APP_DIR = os.path.dirname(os.path.abspath(__file__))
# 默认仍是 SQLite 兼容旧部署；设置 JQ_PROD_DATABASE_URL 后切自建 Postgres。
PROD_DB_URL = os.environ.get("JQ_PROD_DATABASE_URL") or f"sqlite:///{DATA}/jieqiu.db"
# 兼容常见的 postgres:// 旧写法；SQLAlchemy 2 只认 postgresql://。
if PROD_DB_URL.startswith("postgres://"):
    PROD_DB_URL = "postgresql://" + PROD_DB_URL[len("postgres://"):]
DB_ENV = f"JQ_DATABASE_URL={shlex.quote(PROD_DB_URL)}"
ENV_FILE = "/etc/jieqiu-backend.env"


def _clean(value: str, label: str) -> str:
    """拒绝换行，避免把 systemd/cron 的一行配置注入成多行。"""
    if "\n" in value or "\r" in value:
        raise SystemExit(f"{label} 不能包含换行")
    return value


def _require(ok: bool, message: str) -> None:
    """部署失败必须真的停；不要用 assert（python -O 会把它编译掉）。"""
    if not ok:
        raise SystemExit(message)


def _env_line(key: str, value: str) -> str:
    """systemd EnvironmentFile 的双引号行；转义反斜杠和双引号，不做 shell 展开。"""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'{key}="{escaped}"\n'



def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str]:
    _, out, err = ssh.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", "replace")
    e = err.read().decode("utf-8", "replace")
    code = out.channel.recv_exit_status()
    return code, (o + ("\n[stderr] " + e if e.strip() else ""))


def run_sudo(ssh: paramiko.SSHClient, cmd: str, password: str,
             timeout: int = 600) -> tuple[int, str]:
    """把 sudo 密码从 stdin 送入，不把密码放进远端命令行（避免 ps 泄露）。"""
    stdin, out, err = ssh.exec_command(f"sudo -S {cmd}", timeout=timeout)
    stdin.write(password + "\n")
    stdin.flush()
    stdin.channel.shutdown_write()
    o = out.read().decode("utf-8", "replace")
    e = err.read().decode("utf-8", "replace")
    code = out.channel.recv_exit_status()
    return code, (o + ("\n[stderr] " + e if e.strip() else ""))



def make_tar() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel in ("app", "requirements.txt", "README.md", "alembic.ini", "migrations"):
            full = os.path.join(APP_DIR, rel)
            tar.add(full, arcname=f"jieqiu-backend/{rel}")
        # DC 模型底座（xG 历史数据）随包上传
        xg = os.path.abspath(os.path.join(APP_DIR, "..", "w1-validation", "xg_matches.csv"))
        if os.path.exists(xg):
            tar.add(xg, arcname="jieqiu-backend/xg_matches.csv")
    buf.seek(0)
    return buf.read()


def main() -> None:
    if not PWD or not CONSOLE_PASSWORD:
        raise SystemExit("请设置 JQ_DEPLOY_PASSWORD 与 JQ_CONSOLE_PASSWORD（不要把密码写进代码）")
    _clean(PWD, "JQ_DEPLOY_PASSWORD")
    _clean(CONSOLE_PASSWORD, "JQ_CONSOLE_PASSWORD")
    _clean(PROD_DB_URL, "JQ_PROD_DATABASE_URL")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    print("[1/6] connected")

    code, out = run(ssh, "python3 --version && python3 -m venv --help >/dev/null && echo venv-ok")
    print("[2/6] env:", out.strip()[:80])
    _require("venv-ok" in out, "服务器缺 python3-venv：sudo apt install -y python3-venv python3-pip")

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
    print("[3/6] code uploaded", len(data), "bytes |",
          out.strip().splitlines()[-1] if out.strip() else "(no output)")
    _require(code == 0 and "deploy-ok" in out, f"代码上传/解包失败：{out[-800:]}")

    # 显式保留 pip 的退出码：`pip ... | tail` 在默认 shell 里返回的是 tail 的状态。
    code, out = run(ssh,
                    f"cd {ROOT} && python3 -m venv venv && "
                    f"venv/bin/pip install -q -r requirements.txt > /tmp/jq-pip.log 2>&1; "
                    f"rc=$?; tail -2 /tmp/jq-pip.log; exit $rc")
    print("[4/6] deps:", out.strip().splitlines()[-1] if out.strip() else "(no output)")
    _require(code == 0, f"依赖安装失败：{out[-1200:]}")

    # Postgres 使用 Alembic 管理 schema；SQLite 旧库继续走启动期 create_all 兼容。
    if PROD_DB_URL.startswith(("postgresql", "postgres")):
        code, out = run(ssh, f"cd {ROOT} && {DB_ENV} "
                             f"venv/bin/alembic upgrade head > /tmp/jq-alembic.log 2>&1; "
                             f"rc=$?; tail -4 /tmp/jq-alembic.log; exit $rc")
        print("[4b/6] alembic:", out.strip())
        _require(code == 0, f"Alembic 迁移失败，已停止部署：{out[-1200:]}")

    # JWT 密钥：首次部署生成并固定（幂等：优先读 EnvironmentFile，兼容旧 unit）
    import secrets as _secrets
    code, out = run_sudo(
        ssh,
        f"cat {ENV_FILE} 2>/dev/null; "
        "grep -o 'JQ_JWT_SECRET=[a-f0-9]*' /etc/systemd/system/jieqiu-backend.service "
        "2>/dev/null | head -1",
        PWD,
    )
    jwt_secret = ""
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("JQ_JWT_SECRET="):
            jwt_secret = line.split("=", 1)[1].strip().strip('"')
            break
    print("[jwt] secret", "kept" if jwt_secret else "generated")
    if not jwt_secret:
        jwt_secret = _secrets.token_hex(32)

    # 密钥放 0600 的 EnvironmentFile，不再写进 world-readable 的 unit 文件。
    env_text = "".join(_env_line(k, v) for k, v in (
        ("JQ_DATABASE_URL", PROD_DB_URL),
        ("JQ_ENV", "prod"),
        ("JQ_XG_DATA_PATH", f"{ROOT}/xg_matches.csv"),
        ("JQ_XG_EXTRA_DIR", f"{DATA}/xg_dumps"),
        ("JQ_FREEZE_BASELINE", f"{DATA}/freeze_baseline.json"),
        ("JQ_JWT_SECRET", jwt_secret),
        ("JQ_CONSOLE_PASSWORD", CONSOLE_PASSWORD),
        ("JQ_CORS_EXTRA_ORIGINS", "http://43[.]128[.]24[.]244:8899"),
    ))
    with sftp.file("/tmp/jieqiu-backend.env", "w") as f:
        f.write(env_text)

    # systemd 单元
    unit = f"""[Unit]
Description=jieqiu backend (W2)
After=network.target

[Service]
WorkingDirectory={ROOT}
User=ubuntu
Group=ubuntu
EnvironmentFile={ENV_FILE}
ExecStart={ROOT}/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8100
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
    with sftp.file("/tmp/jieqiu-backend.service", "w") as f:
        f.write(unit)
    code, out = run_sudo(ssh, f"install -m 600 -o root -g root "
                              f"/tmp/jieqiu-backend.env {ENV_FILE} && echo env-ok", PWD)
    _require(code == 0 and "env-ok" in out, f"写入 {ENV_FILE} 失败：{out[-800:]}")
    code, out = run_sudo(ssh, f"mv /tmp/jieqiu-backend.service "
                              f"/etc/systemd/system/jieqiu-backend.service && echo unit-ok", PWD)
    _require(code == 0 and "unit-ok" in out, f"写入 systemd unit 失败：{out[-800:]}")
    # 同步 cron：每 30 分钟读采集器 SFTP 推送来的 DB 并重建判决（env 与 systemd 一致；DB 在 DATA）
    envs = (f"{DB_ENV} JQ_DB_STATEMENT_TIMEOUT_MS=0 "
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
            f"venv/bin/python -m app.features.assistant.worker --once >> {ROOT}/assistant.log 2>&1\n"
            # 数据保留：每周日 04:10 清理可再生日志；判决/账本/SP 快照永不自动删除
            f"10 4 * * 0 cd {ROOT} && {envs} "
            f"venv/bin/python -m app.db_maint --apply --json >> {ROOT}/db_maint.log 2>&1\n")
    # 用 SFTP 写 cron 文件，避免 echo 双引号把数据库密码里的 $/反引号做 shell 展开。
    with sftp.file("/tmp/jqcron", "w") as f:
        f.write(cron)
    code, out = run(ssh, "crontab -l 2>/dev/null | grep -v jieqiu-backend | cat - /tmp/jqcron | "
                         "crontab - && echo cron-ok")
    _require("cron-ok" in out, f"写入 crontab 失败：{out[-800:]}")

    # 上传当前采集器数据并跑一次种子；同样不能用管道吞掉 seed 的退出码。
    sftp.put(os.path.join(APP_DIR, "..", "sp-collector", "sp_data.db"), "/tmp/sp_data.db")
    code, out = run(ssh, f"cd {ROOT} && {DB_ENV} JQ_DB_STATEMENT_TIMEOUT_MS=0 "
                         f"JQ_XG_DATA_PATH={ROOT}/xg_matches.csv JQ_XG_EXTRA_DIR={DATA}/xg_dumps "
                         f"venv/bin/python -m app.seed /tmp/sp_data.db > /tmp/jq-seed.log 2>&1; "
                         f"rc=$?; tail -3 /tmp/jq-seed.log; exit $rc")
    print("[5/6] seed on server:\n", out.strip())
    _require(code == 0, f"种子导入失败：{out[-1200:]}")

    code, out = run_sudo(
        ssh,
        "systemctl daemon-reload && systemctl enable jieqiu-backend && "
        "systemctl restart jieqiu-backend",
        PWD,
    )
    _require(code == 0, f"systemctl 重启失败：{out[-1200:]}")
    code, out = run(ssh, "sleep 2 && systemctl is-active jieqiu-backend && "
                         "curl -fsS http://127.0.0.1:8100/health")
    print("[6/6] service:\n", out.strip())
    _require(code == 0 and '"status":"ok"' in out, f"服务/健康检查失败：{out[-1200:]}")
    sftp.close()
    ssh.close()
    print("DEPLOY DONE")


if __name__ == "__main__":
    main()
