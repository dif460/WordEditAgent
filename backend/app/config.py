"""应用配置。"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # PostgreSQL
    database_url: str = (
        "postgresql+psycopg2://wordagent:wordagent@localhost:5432/wordedit"
    )

    # 目录（相对于项目根目录）
    upload_dir: str = "uploads"
    output_dir: str = "outputs"
    template_dir: str = "templates"

    # 校验失败最大修复次数
    max_retry: int = 3

    # ---- 设备访问控制（MAC 白名单 + 设备凭证 Cookie） ----
    # mac = 严格白名单拦截；off = 关闭访问控制
    access_control_mode: str = "mac"
    # 设备凭证 Cookie 的 HMAC 签名密钥；为空时自动生成并保存到 backend/.device_cookie_secret
    device_cookie_secret: str = ""
    # 白名单文件（相对 backend/ 根目录）
    allowed_macs_file: str = "allowed_devices.json"
    # 设备凭证 Cookie 有效期（秒），默认 1 年
    device_cookie_max_age: int = 31536000

    @property
    def upload_path(self) -> Path:
        return self._ensure_dir(self.upload_dir)

    @property
    def output_path(self) -> Path:
        return self._ensure_dir(self.output_dir)

    @property
    def template_path(self) -> Path:
        return self._ensure_dir(self.template_dir)

    @property
    def allowed_macs_path(self) -> Path:
        return BASE_DIR / self.allowed_macs_file

    def _ensure_dir(self, name: str) -> Path:
        p = BASE_DIR / name
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
