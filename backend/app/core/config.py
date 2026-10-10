"""应用配置：全部从环境变量读取（pydantic-settings）。

铁律（SPEC §10）：密钥只从环境变量读，不入库、不进 git。
本模块绝不因为缺少环境变量而抛错——否则容器起不来时用户看不到任何线索。
缺省值仅用于本地开发，生产必须通过 .env / 容器环境覆盖。
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# 内容 Schema 版本（SPEC §5 SystemInfo；schemas.md §2）
SCHEMA_VERSIONS: dict[str, str] = {
    "card": "1.0",
    "worldbook": "1.0",
    "preset": "1.0",
    "session": "1.0",
}

DEFAULT_PASSWORD_SENTINELS = {"", "change-me-now", "changeme", "password"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- 应用 ----
    app_name: str = "提线 (Marionette)"
    app_version: str = "0.1.0"
    app_env: str = "development"
    log_level: str = "INFO"
    default_owner_id: str = "local"

    # ---- 部署 / 入口 ----
    domain: str = ":80"

    # ---- 访问控制（AC-02 / AC-03）----
    access_password: str = ""
    secret_key: str = "dev-insecure-secret-change-me"
    session_cookie_name: str = "marionette_session"
    session_cookie_secure: bool = True
    session_ttl_seconds: int = 7 * 24 * 3600
    access_max_failed: int = 5
    access_lock_window_seconds: int = 900

    # ---- 数据库 ----
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/marionette"
    db_echo: bool = False

    # ---- CORS ----
    cors_origins: str = ""

    # ---- LLM 后端（BYOK，自研 OpenAI 兼容薄层）----
    llm_provider: str = "openai_compatible"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_seconds: float = 30.0
    llm_test_timeout_seconds: float = 3.0

    # ---- 图像生成后端（BYOK，云端图像 API）----
    image_provider: str = "cloud"
    image_base_url: str = ""
    image_api_key: str = ""
    image_model: str = ""

    # ---- 存储 / 静态 ----
    assets_dir: str = "./data/assets"
    config_dir: str = "./data/config"
    static_dir: str = "./static"

    # ---------------- 派生属性 ----------------

    @property
    def cors_origin_list(self) -> list[str]:
        """允许的跨域来源。留空时默认放行 Vite 开发服务器。"""
        raw = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        if raw:
            return raw
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_model)

    @property
    def image_configured(self) -> bool:
        return bool(self.image_base_url and self.image_api_key)

    def security_warnings(self) -> list[str]:
        """启动时打印的安全告警（不阻断启动，但必须显眼）。"""
        warnings: list[str] = []
        if self.access_password.strip().lower() in DEFAULT_PASSWORD_SENTINELS:
            warnings.append(
                "ACCESS_PASSWORD 仍为默认值或为空：任何知道该值的人都能访问你的实例。"
                "请立即在 .env 中设置为 12 位以上随机串。"
            )
        if self.secret_key == "dev-insecure-secret-change-me":
            warnings.append(
                "SECRET_KEY 仍为默认值：会话令牌可被伪造。请用 "
                "`openssl rand -hex 32` 生成随机串并写入 .env。"
            )
        if not self.access_password.strip():
            warnings.append("ACCESS_PASSWORD 为空：登录功能将永远失败，实例实际不可用。")
        if not self.session_cookie_secure and self.domain not in (":80", "localhost"):
            warnings.append(
                "SESSION_COOKIE_SECURE=false 且已配置域名：会话 Cookie 会以明文经网传输。"
                "生产环境请改为 true 并确保走 HTTPS。"
            )
        return warnings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """进程内单例。"""
    return Settings()
