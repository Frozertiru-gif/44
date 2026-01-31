from __future__ import annotations

from functools import lru_cache
from typing import Set

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    bot_token: str
    database_url: str
    requests_chat_id: int
    sys_admin_ids: str = ""

    webhook_secret: str | None = None
    public_base_url: str | None = None

    def sys_admin_id_set(self) -> Set[int]:
        if not self.sys_admin_ids:
            return set()
        return {int(item.strip()) for item in self.sys_admin_ids.split(",") if item.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
