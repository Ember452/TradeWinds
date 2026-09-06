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

    # --- 业务限额 ---
    quota_topics_max: int = Field(default=5, description="每用户最大主题数")

    # --- 可观测 ---
    log_level: str = Field(default="INFO", description="日志级别")


@lru_cache
def get_settings() -> Settings:
    """返回全局配置单例;缺必填环境变量时抛 ValidationError 并列出缺失项。"""
    return Settings()
