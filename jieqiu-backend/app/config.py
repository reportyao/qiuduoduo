"""应用配置：全部可被环境变量覆盖（12-factor）。"""
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # sqlite:///./jieqiu.db（开发/当前）或 postgresql+psycopg://user:pass@host/db（腾讯云 PG 生产，方案 B）
    database_url: str = "sqlite:///./jieqiu.db"
    # 时区：竞彩全部按中国标准时间
    tz_offset_hours: int = 8
    # 流里避雷展示条数
    avoid_top_n: int = 3
    # 环境标签
    env: str = "dev"
    warmup: bool = True              # 启动时后台预热模型/缓存

    # ---- W3 三道闸 ----
    # 价闸：动态阈值 = 当日候选场抽水中位数 + pad，夹在 clamp 区间
    rake_pad: float = 0.03
    rake_clamp_lo: float = 0.10
    rake_clamp_hi: float = 0.13
    # 市闸：多源（去水后）逐结果最大离散度阈值
    market_div_threshold: float = 0.05
    # 模闸：收缩后最优方向置信门槛（可推线）
    model_conf_threshold: float = 0.53
    # DC 模型（与 W1 回测同参：halflife 180d / 窗口 540d / rho=-0.06）
    xg_data_path: str = "../w1-validation/xg_matches.csv"
    # 增量 dump 目录（understat_sync 落档处；与主 csv 合并后拟合）
    xg_extra_dir: str = ""
    dc_halflife_days: int = 180
    dc_window_days: int = 540
    dc_rho: float = -0.06
    dc_min_matches: int = 3
    # 市闸国际盘源：the-odds-api（免费 500 次/月）。未配置 key → 市闸诚实 pending_data
    odds_api_key: str = ""
    odds_sports: str = "soccer_epl,soccer_spain_la_liga,soccer_germany_bundesliga,soccer_italy_serie_a,soccer_france_ligue_one,soccer_uefa_champs_league"
    odds_sync_min_interval_hours: float = 6.0

    # ---- W5 认证（方案 B：自建 JWT + 验证码 + 第三方 OAuth）----
    jwt_secret: str = ""              # 生产必填（未配置则认证端点 fail-closed）
    jwt_access_minutes: int = 15
    refresh_days: int = 30
    code_ttl_seconds: int = 300        # 验证码 5 分钟
    code_max_attempts: int = 5
    code_send_interval_seconds: int = 60   # 同目标 60 秒一次
    code_daily_limit: int = 10             # 同目标每日上限
    auth_stub: bool = True             # 非生产环境启用 stub（dev_code 回显 / 假 OAuth）
    allow_device_login: bool = True    # 旧版 App 的免登录态；上线新客户端后可关
    sms_provider: str = "stub"         # stub | tencent
    email_provider: str = "stub"       # stub | resend
    resend_api_key: str = ""
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    google_client_id: str = ""
    apple_client_id: str = ""

    model_config = {"env_prefix": "JQ_", "env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
