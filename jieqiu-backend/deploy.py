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
ADMIN_PASSWORD = (os.environ.get("JQ_ADMIN_PASSWORD")
                  or os.environ.get("JQ_CONSOLE_PASSWORD", ""))
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
# 可选功能密钥：只从部署者显式导出的环境变量写入，不从仓库文件读取；
# 未设置的项不会出现在 EnvironmentFile，功能按自身降级路径运行。
OPTIONAL_ENV_KEYS = (
    "JQ_ADMIN_COOKIE_SECURE",
    "JQ_ADMIN_PASSWORD",
    "JQ_LLM_FAST_PROVIDER", "JQ_LLM_FAST_BASE_URL", "JQ_LLM_FAST_MODEL",
    "JQ_LLM_FAST_API_KEY", "JQ_LLM_DEEP_PROVIDER", "JQ_LLM_DEEP_BASE_URL",
    "JQ_LLM_DEEP_MODEL", "JQ_LLM_DEEP_API_KEY", "JQ_LLM_DAILY_BUDGET_CNY",
    "JQ_LLM_TASK_BUDGET_CNY", "JQ_LLM_USER_DAILY_CALLS", "JQ_LLM_REVIEW_MAX_TOKENS",
    "JQ_PERSONA_LLM_BASE_URL", "JQ_PERSONA_LLM_API_KEY", "JQ_PERSONA_LLM_ENC_KEY",
    "JQ_PERSONA_LLM_MAX_TOKENS", "JQ_PERSONA_LLM_TEMPERATURE",
    "JQ_API_FOOTBALL_KEY", "JQ_API_FOOTBALL_BASE_URL",
    "JQ_API_FOOTBALL_PROVIDER", "JQ_API_FOOTBALL_RAPIDAPI_HOST",
    "JQ_API_FOOTBALL_DAILY_LIMIT", "JQ_API_FOOTBALL_LINEUP_HOURS",
    "JQ_API_FOOTBALL_MAX_REQUESTS_PER_RUN", "JQ_ODDS_API_KEY",
    "JQ_ODDS_SYNC_MIN_INTERVAL_HOURS", "JQ_ODDS_SPORTS",
    "JQ_SMS_PROVIDER", "JQ_EMAIL_PROVIDER", "JQ_RESEND_API_KEY",
    "JQ_WECHAT_APP_ID", "JQ_WECHAT_APP_SECRET", "JQ_GOOGLE_CLIENT_ID",
    "JQ_APPLE_CLIENT_ID",
)


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


def _shell_env_line(key: str, value: str) -> str:
    """cron.env 用 shell 单引号行；避免 source 时 $/反引号被展开。"""
    return f"{key}={shlex.quote(str(value))}\n"



def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str]:
    _, out, err = ssh.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", "replace")
    e = err.read().decode("utf-8", "replace")
    code = out.channel.recv_exit_status()
    return code, (o + ("\n[stderr] " + e if e.strip() else ""))


def run_sudo(ssh: paramiko.SSHClient, cmd: str, password: str,
             timeout: int = 600) -> tuple[int, str]:
    """把 sudo 密码从 stdin 送入，不把密码放进远端命令行（避免 ps 泄露）。"""
    stdin, out, err = ssh.exec_command(f"sudo -S -p '' sh -c {shlex.quote(cmd)}", timeout=timeout)
    stdin.write(password + "\n")
    stdin.flush()
    stdin.channel.shutdown_write()
    o = out.read().decode("utf-8", "replace")
    e = err.read().decode("utf-8", "replace")
    code = out.channel.recv_exit_status()
    return code, (o + ("\n[stderr] " + e if e.strip() else ""))



def make_tar() -> bytes:
    def _skip_cache(info: tarfile.TarInfo):
        if "__pycache__" in info.name or info.name.endswith(".pyc"):
            return None
        return info

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel in ("app", "requirements.txt", "README.md", "alembic.ini", "migrations"):
            full = os.path.join(APP_DIR, rel)
            tar.add(full, arcname=f"jieqiu-backend/{rel}", filter=_skip_cache)
        # DC 模型底座（xG 历史数据）随包上传
        xg = os.path.abspath(os.path.join(APP_DIR, "..", "w1-validation", "xg_matches.csv"))
        if os.path.exists(xg):
            tar.add(xg, arcname="jieqiu-backend/xg_matches.csv")
    buf.seek(0)
    return buf.read()


def main() -> None:
    if not PWD:
        raise SystemExit("请设置 JQ_DEPLOY_PASSWORD（不要把密码写进代码）")
    _clean(PWD, "JQ_DEPLOY_PASSWORD")
    _clean(ADMIN_PASSWORD, "JQ_ADMIN_PASSWORD")
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
    remote_env: dict[str, str] = {}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("JQ_") and "=" in line:
            key, value = line.split("=", 1)
            remote_env[key] = value.strip().strip('"')
        if line.startswith("JQ_JWT_SECRET="):
            jwt_secret = line.split("=", 1)[1].strip().strip('"')
    # cron.env 以 ubuntu 身份保存，systemd EnvironmentFile 可能没有某些 key
    # （例如只给采集器/同步 cron 用的 API-Football key）。合并回来，避免一次
    # 未导出环境变量的部署把只在 cron.env 里的密钥清空。
    code, cron_out = run(ssh, f"cat {DATA}/cron.env 2>/dev/null")
    for line in cron_out.splitlines():
        line = line.strip()
        if not line.startswith("JQ_") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        try:
            parts = shlex.split(value)
        except ValueError:
            continue
        if len(parts) == 1:
            remote_env.setdefault(key.strip(), parts[0])
    print("[jwt] secret", "kept" if jwt_secret else "generated")
    if not jwt_secret:
        jwt_secret = _secrets.token_hex(32)
    admin_password = (ADMIN_PASSWORD or remote_env.get("JQ_ADMIN_PASSWORD", "")
                      or remote_env.get("JQ_CONSOLE_PASSWORD", ""))
    if not admin_password:
        raise SystemExit("远端无管理员密码且未设置 JQ_ADMIN_PASSWORD")

    # 密钥放 0600 的 EnvironmentFile，不再写进 world-readable 的 unit 文件。
    # 远端已有可选密钥默认保留，避免一次未导出 env 的部署把 LLM/API-Football 配置清空。
    env_text = "".join(_env_line(k, v) for k, v in (
        ("JQ_DATABASE_URL", PROD_DB_URL),
        ("JQ_ENV", "prod"),
        ("JQ_XG_DATA_PATH", f"{ROOT}/xg_matches.csv"),
        ("JQ_XG_EXTRA_DIR", f"{DATA}/xg_dumps"),
        ("JQ_FREEZE_BASELINE", f"{DATA}/freeze_baseline.json"),
        ("JQ_JWT_SECRET", jwt_secret),
        ("JQ_ADMIN_PASSWORD", admin_password),
        ("JQ_AUTH_STUB", "false"),
        ("JQ_CORS_EXTRA_ORIGINS", "http://43[.]128[.]24[.]244:8899"),
    ))
    for key in OPTIONAL_ENV_KEYS:
        if key == "JQ_ADMIN_PASSWORD":
            continue
        value = os.environ.get(key) or remote_env.get(key, "")
        if value:
            env_text += _env_line(key, value)
    with sftp.file("/tmp/jieqiu-backend.env", "w") as f:
        f.write(env_text)
    # 先收紧权限再 sudo install，避免 /tmp 上的短暂可读窗口。
    sftp.chmod("/tmp/jieqiu-backend.env", 0o600)

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

    # cron 以 ubuntu 运行，读不到 root:root 0600 的 systemd EnvironmentFile；
    # 单独写一份 0600 ubuntu 的 cron.env，让 seed/推荐/人设/worker 都能拿到可选密钥。
    cron_env = {
        "JQ_DATABASE_URL": PROD_DB_URL,
        "JQ_ENV": "prod",
        "JQ_XG_DATA_PATH": f"{ROOT}/xg_matches.csv",
        "JQ_XG_EXTRA_DIR": f"{DATA}/xg_dumps",
        "JQ_FREEZE_BASELINE": f"{DATA}/freeze_baseline.json",
        "JQ_DB_STATEMENT_TIMEOUT_MS": "0",
        "JQ_DAILY_BRIEF_HOUR": "19",
    }
    for key in OPTIONAL_ENV_KEYS:
        value = os.environ.get(key) or remote_env.get(key, "")
        if value and key != "JQ_ADMIN_PASSWORD":
            cron_env[key] = value
    cron_env_text = "".join(_shell_env_line(k, v) for k, v in cron_env.items())
    # 覆盖前留时间戳备份；只保留最近 5 份，避免无界增长。
    run(ssh, f"cp -p {DATA}/cron.env {DATA}/cron.env.bak-$(date +%Y%m%d%H%M%S) "
             f"2>/dev/null || true; ls -1t {DATA}/cron.env.bak-* 2>/dev/null | "
             f"tail -n +6 | xargs -r rm -f")
    with sftp.file(f"{DATA}/cron.env", "w") as f:
        f.write(cron_env_text)
    sftp.chmod(f"{DATA}/cron.env", 0o600)
    code, out = run_sudo(ssh, f"mv /tmp/jieqiu-backend.service "
                              f"/etc/systemd/system/jieqiu-backend.service && echo unit-ok", PWD)
    _require(code == 0 and "unit-ok" in out, f"写入 systemd unit 失败：{out[-800:]}")
    # 同步 cron：每 30 分钟读采集器 SFTP 推送来的 DB 并重建判决。
    # 统一 source cron.env，保证国际盘/LLM/人设/API-Football 的可选密钥对 cron 可见。
    cron_prefix = f"set -a; . {DATA}/cron.env; set +a; cd {ROOT} && "
    cron = (f"*/30 * * * * {cron_prefix}"
            f"venv/bin/python -m app.seed /home/ubuntu/jieqiu-sp/sp_data.db >> {ROOT}/sync.log 2>&1 && "
            fr"venv/bin/python -m app.recommendations_cli run >> {ROOT}/recommendations.log 2>&1" + "\n"
            # 每日 19:05 预生成三套人设文案；用户请求只读缓存
            f"5 19 * * * {cron_prefix}"
            fr"venv/bin/python -m app.persona_cli warm --date $(date +\%F) >> {ROOT}/persona.log 2>&1" + "\n"
            # 每周一 06:10 校准回测（校准数据周更，防腐烂）
            f"10 6 * * 1 {cron_prefix}"
            f"venv/bin/python -m app.backtest_cli weekly >> {ROOT}/backtest.log 2>&1\n"
            # 每日 03:00 注销期满清除（7 天冷静期）
            f"0 3 * * * {cron_prefix}"
            f"venv/bin/python -m app.purge_cli >> {ROOT}/purge.log 2>&1\n"
            # 助理 worker：每分钟事件/扇出/推送（Android JPush；未配置则 dry-run）
            f"* * * * * {cron_prefix}"
            f"venv/bin/python -m app.features.assistant.worker --once >> {ROOT}/assistant.log 2>&1\n"
            # 数据保留：每周日 04:10 清理可再生日志；判决/账本/SP 快照永不自动删除
            f"10 4 * * 0 {cron_prefix}"
            f"venv/bin/python -m app.db_maint --apply --json >> {ROOT}/db_maint.log 2>&1\n")
    if os.environ.get("JQ_API_FOOTBALL_KEY") or remote_env.get("JQ_API_FOOTBALL_KEY"):
        # 免费档每日一次 fixtures；未配 key 的部署不装这条，避免无意义失败日志。
        cron += (f"15 6 * * * {cron_prefix}"
                 rf"venv/bin/python -m app.api_football_cli sync --date $(date +\%F) --next-day >> {ROOT}/api_football.log 2>&1" + "\n")
        # 临场阵容/伤停：比赛日每小时只补 2 场阵容 + 1 场伤停；限流入口避免刷爆 100/日。
        cron += (f"0 0-4,10-23 * * * {cron_prefix}"
                 f"venv/bin/python -m app.api_football_cli sync-enrich --json >> {ROOT}/api_football.log 2>&1" + "\n")
    # 用 SFTP 写 cron 文件，避免 echo 双引号把数据库密码里的 $/反引号做 shell 展开。
    with sftp.file("/tmp/jqcron", "w") as f:
        f.write(cron)
    code, out = run(ssh, "crontab -l 2>/dev/null | grep -v jieqiu-backend | cat - /tmp/jqcron | "
                         "crontab - && echo cron-ok")
    _require("cron-ok" in out, f"写入 crontab 失败：{out[-800:]}")

    # 上传当前采集器数据并跑一次种子；同样不能用管道吞掉 seed 的退出码。
    sftp.put(os.path.join(APP_DIR, "..", "sp-collector", "sp_data.db"), "/tmp/sp_data.db")
    code, out = run(ssh, f"set -a; . {DATA}/cron.env; set +a; cd {ROOT} && "
                         f"venv/bin/python -m app.seed /tmp/sp_data.db > /tmp/jq-seed.log 2>&1; "
                         f"rc=$?; tail -3 /tmp/jq-seed.log; exit $rc")
    print("[5/6] seed on server:\n", out.strip())
    _require(code == 0, f"种子导入失败：{out[-1200:]}")

    # freeze_baseline 由服务进程写入；旧部署曾以 root 创建导致 /review/freeze/adopt 500。
    run_sudo(ssh, f"install -d -o ubuntu -g ubuntu {DATA} && "
                  f"touch {DATA}/freeze_baseline.json && "
                  f"chown ubuntu:ubuntu {DATA}/freeze_baseline.json", PWD)
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
