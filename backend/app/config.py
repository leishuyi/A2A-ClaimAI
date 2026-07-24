from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置，支持环境变量覆盖 (STARSHIELD_ 前缀)。

    参考 grid-qa 模式：
    - typed feature flags，默认 OFF 的需手动启用
    - @lru_cache 单例缓存
    - pydantic-settings 自动从 .env 加载
    """
    # ---- 基础 ----
    app_name: str = "A2A 智能理赔助手"
    debug: bool = True
    app_env: str = "development"  # development | staging | production
    database_url: str = "sqlite:///./starshield.db"

    # ---- Feature Flags（默认 OFF 表示 opt-in） ----
    feature_human_gate: bool = True    # 人工授权节点（核心功能，默认开启）
    feature_risk_control: bool = True  # 风控审查 Agent E
    feature_audit_log: bool = True     # 审计日志
    feature_agent_parallel: bool = False  # Agent 并行编排（进阶，默认关闭）
    feature_event_bus: bool = True     # 事件总线
    feature_rbac: bool = False         # RBAC 权限控制（默认关闭，开启需配置 STARSHIELD_API_KEY）

    # ---- 日志 ----
    log_level: str = "INFO"
    log_rotation: str = "500 MB"
    log_retention: str = "14 days"

        # ---- 安全 ----
    api_key: str = ""                  # API Key，为空则不鉴权
    pii_mask_enabled: bool = True      # PII 数据脱敏

    # ---- 文件存储 ----
    upload_dir: str = "data/uploads"         # 文件存储根目录
    max_file_size: int = 10 * 1024 * 1024    # 单文件上限 10MB
    allowed_extensions: str = ".jpg,.jpeg,.png,.bmp,.tiff,.pdf"

    # ---- API ----
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_prefix="STARSHIELD_",
    )


@lru_cache
def get_settings() -> Settings:
    """单例缓存，避免每次请求重复解析 .env"""
    return Settings()


settings = get_settings()
