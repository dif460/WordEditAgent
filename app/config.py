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

    @property
    def upload_path(self) -> Path:
        return self._ensure_dir(self.upload_dir)

    @property
    def output_path(self) -> Path:
        return self._ensure_dir(self.output_dir)

    @property
    def template_path(self) -> Path:
        return self._ensure_dir(self.template_dir)

    def _ensure_dir(self, name: str) -> Path:
        p = BASE_DIR / name
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
