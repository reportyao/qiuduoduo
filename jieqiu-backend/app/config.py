"""应用配置：全部可被环境变量覆盖（12-factor）。"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # sqlite:///./jieqiu.db（开发/当前）或 postgresql+psycopg2://user:pass@host/db（自建 Postgres 生产）
    database_url: str = "sqlite:///./jieqiu.db"
    # 生产 Postgres 连接池/超时（SQLite 忽略这些参数）；加下界防止误配成 0/负数
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=200)
    db_pool_timeout_seconds: int = Field(default=30, ge=1, le=300)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60)
    db_statement_timeout_ms: int = Field(default=15000, ge=0)
    db_lock_timeout_ms: int = Field(default=5000, ge=0)
    # 数据保留（天）：CLI app.db_maint 默认 dry-run，--apply 才真正删除
    # 必须 >=1 天；防止负值把“创建时间 < 未来”当成全表删除。
    event_retention_days: int = Field(default=90, ge=1, le=3650)
    notification_retention_days: int = Field(default=180, ge=1, le=3650)
    model_run_retention_days: int = Field(default=365, ge=1, le=3650)
    user_event_retention_days: int = Field(default=180, ge=1, le=3650)
    interaction_retention_days: int = Field(default=180, ge=1, le=3650)
    llm_usage_retention_days: int = Field(default=180, ge=1, le=3650)
    persona_copy_retention_days: int = Field(default=30, ge=1, le=3650)
    verification_code_retention_days: int = Field(default=7, ge=1, le=3650)
    # 时区：竞彩全部按中国标准时间
    tz_offset_hours: int = 8
    # 流里避雷展示条数
    avoid_top_n: int = 3
    # 数据脉搏展示系数：只乘“数据点”，不乘场次/封存/准确率；营销口径可查
    pulse_display_factor: float = Field(default=3.0, ge=1.0, le=5.0)
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
    odds_sports: str = ("soccer_epl,soccer_spain_la_liga,soccer_germany_bundesliga,"
                        "soccer_italy_serie_a,soccer_france_ligue_one,"
                        "soccer_uefa_champs_league,soccer_uefa_europa_league,"
                        "soccer_uefa_europa_conference_league")
    odds_sync_min_interval_hours: float = 6.0
    # API-Football（免费档 100 请求/日；默认留 10 次给人工排查）
    api_football_key: str = ""
    # apisports = 官方直连（x-apisports-key）；rapidapi = RapidAPI 市场（x-rapidapi-key）
    api_football_provider: str = "apisports"
    api_football_base_url: str = "https://v3.football.api-sports.io"
    api_football_rapidapi_host: str = "api-football-v1.p.rapidapi.com"
    api_football_timeout_s: int = Field(default=20, ge=3, le=60)
    api_football_daily_limit: int = Field(default=90, ge=1, le=100)
    api_football_lineup_hours: int = Field(default=6, ge=1, le=24)
    api_football_max_requests_per_run: int = Field(default=20, ge=1, le=100)

    # ---- LLM Gateway（fast=免费/低成本；deep=DeepSeek；未配置 → 模板兜底）----
    llm_fast_provider: str = "glm"
    llm_fast_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_fast_model: str = "glm-4-flash"
    llm_fast_api_key: str = ""
    llm_fast_input_price_cny_per_m: float = Field(default=0.0, ge=0)
    llm_fast_output_price_cny_per_m: float = Field(default=0.0, ge=0)
    llm_deep_provider: str = "deepseek"
    llm_deep_base_url: str = "https://api.deepseek.com/v1"
    llm_deep_model: str = "deepseek-chat"
    llm_deep_api_key: str = ""
    llm_deep_input_price_cny_per_m: float = Field(default=2.0, ge=0)
    llm_deep_output_price_cny_per_m: float = Field(default=8.0, ge=0)
    llm_timeout_s: int = Field(default=20, ge=3, le=120)
    llm_max_retries: int = Field(default=1, ge=0, le=2)
    llm_daily_budget_cny: float = Field(default=50.0, ge=0)
    llm_task_budget_cny: float = Field(default=20.0, ge=0)
    llm_user_daily_calls: int = Field(default=50, ge=1, le=10000)
    llm_cache_ttl_seconds: int = Field(default=1800, ge=0, le=86400)
    # 推理模型（deepseek-v4.1-flash 等）reasoning tokens 会占用额度；
    # 复核 JSON 必须留足输出空间，否则 content 为空、被误判 degraded。
    llm_review_max_tokens: int = Field(default=1600, ge=256, le=4096)

    # 人设语气翻译专用模型池（OpenAI-compatible；后台可增删/排序）
    persona_llm_base_url: str = "https://tokenrhythm.studio/v1"
    persona_llm_api_key: str = ""
    persona_llm_enc_key: str = ""
    persona_llm_timeout_s: int = Field(default=20, ge=3, le=120)
    persona_llm_max_tokens: int = Field(default=800, ge=64, le=4096)
    persona_llm_temperature: float = Field(default=0.4, ge=0, le=1.5)
    persona_llm_cooldown_s: int = Field(default=120, ge=10, le=3600)

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
    # /admin 初始管理员密码（仅首次建号）；为空时回退旧 JQ_CONSOLE_PASSWORD
    admin_password: str = ""
    admin_cookie_secure: bool = False
    # 旧部署兼容：仅作为 admin_password 的回退读取，不再有独立登录入口
    console_password: str = ""

    model_config = {"env_prefix": "JQ_", "env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
