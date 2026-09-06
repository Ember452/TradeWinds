"""应用配置:pydantic-settings 读取 TRADEWINDS_ 前缀环境变量,缺必填项启动即失败。"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置单例。字段与 .env.example 一一对应,新增配置必须同步该文件。"""

    model_config = SettingsConfigDict(env_prefix="TRADEWINDS_", env_file=".env", extra="ignore")

    # --- 数据库 / Redis ---
    database_url: str = Field(description="PostgreSQL 连接串(SQLAlchemy async 格式)")
    redis_url: str = Field(description="Redis 连接串(队列/缓存/限流)")

    # --- 认证 ---
    jwt_secret: str = Field(description="JWT 签名密钥,生产环境必须为强随机值")
    jwt_expire_minutes: int = Field(default=1440, description="JWT 有效期(分钟)")

    # --- LLM(OpenAI-compatible;型号字符串只出现在配置,不进代码) ---
    llm_api_base: str = Field(description="LLM API base URL")
    llm_api_key: str = Field(description="LLM API 密钥")
    model_low: str = Field(description="低价位模型(Planner/Retriever/Analyst)")
    model_mid: str = Field(description="中档位模型(Editor/对话)")
    github_token: str | None = Field(
        default=None, description="GitHub 搜索 API token,可选,提升限流额度"
    )

    # --- 业务限额 ---
    quota_topics_max: int = Field(default=5, description="每用户最大主题数")
    auth_rate_limit_max: int = Field(default=10, description="注册/登录按 IP 限流:窗口内最大次数")
    auth_rate_limit_window_seconds: int = Field(
        default=3600, description="注册/登录按 IP 限流:窗口秒数"
    )

    # --- Agent 工具循环 ---
    loop_max_iterations: int = Field(default=10, description="工具循环最大迭代轮数")
    loop_total_timeout_seconds: float = Field(default=120.0, description="工具循环总超时(秒)")
    loop_max_context_chars: int = Field(default=24000, description="工具循环上下文截断阈值(字符)")

    # --- 管道 ---
    pipeline_score_threshold: float = Field(
        default=6.0, description="进 Editor 的评分下限,低于此值条目置 rejected(暂定值)"
    )

    # --- 即时推送 ---
    push_immediate_threshold: float = Field(
        default=8.0, description="单条评分达到该值即触发即时邮件推送"
    )
    push_cluster_suppress_hours: int = Field(
        default=24, description="同一聚类的即时推送抑制窗口(小时)"
    )

    # --- RAG 已读检索 ---
    embedding_model: str | None = Field(
        default=None,
        description="嵌入模型(OpenAI-compatible /embeddings);未配置则已读检索功能关闭",
    )

    # --- 对话 Agent ---
    chat_concurrency_limit: int = Field(default=3, description="每用户并发对话数上限")

    # --- 错误上报 / 运维 ---
    sentry_dsn: str | None = Field(default=None, description="Sentry DSN,未配置则不启用错误上报")
    sentry_environment: str = Field(default="production", description="Sentry 环境标识")
    ops_token: str | None = Field(
        default=None, description="运维指标接口(/ops/summary)的 X-Ops-Token;未配置则接口关闭"
    )

    # --- 邮件推送 ---
    app_base_url: str = Field(
        default="http://localhost:8000", description="对外 base URL(退订链接用)"
    )
    # --- 前端静态托管 ---
    static_dir: str = Field(
        default="",
        description="前端构建产物目录(含 index.html);为空不托管 SPA(本地开发走 vite dev)",
    )
    smtp_host: str = Field(default="", description="SMTP 主机;为空视为未配置")
    smtp_port: int = Field(default=587, description="SMTP 端口")
    smtp_user: str = Field(default="", description="SMTP 用户名")
    smtp_password: str = Field(default="", description="SMTP 密码")
    smtp_from: str = Field(default="", description="发件人地址")
    smtp_start_tls: bool = Field(default=True, description="是否使用 STARTTLS")

    # --- 可观测 ---
    log_level: str = Field(default="INFO", description="日志级别")


@lru_cache
def get_settings() -> Settings:
    """返回全局配置单例;缺必填环境变量时抛 ValidationError 并列出缺失项。"""
    return Settings()
