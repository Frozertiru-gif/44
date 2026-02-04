from __future__ import annotations

from functools import lru_cache
from typing import Set

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    bot_token: str
    database_url: str
    db_schema: str = Field(default="public", validation_alias=AliasChoices("DB_SCHEMA", "db_schema"))
    requests_chat_id: int
    events_chat_id: int = Field(validation_alias=AliasChoices("EVENTS_CHAT_ID", "AUDIT_CHAT_ID", "events_chat_id"))
    super_admin: int | None = Field(default=None, validation_alias=AliasChoices("SUPER_ADMIN", "super_admin"))
    sys_admin_ids: str = ""
    finance_export_chat_id: int | None = None
    backup_chat_id: int | None = Field(default=None, validation_alias=AliasChoices("BACKUP_CHAT_ID", "backup_chat_id"))
    backup_dir: str = Field(
        default="/opt/master_stack/app/telegram_service/backups",
        validation_alias=AliasChoices("BACKUP_DIR", "backup_dir"),
    )
    backup_script_path: str = Field(
        default="/opt/master_stack/app/telegram_service/scripts/backup_db.sh",
        validation_alias=AliasChoices("BACKUP_SCRIPT_PATH", "backup_script_path"),
    )
    backup_env_path: str = Field(
        default="/opt/master_stack/app/telegram_service/scripts/backup.env",
        validation_alias=AliasChoices("BACKUP_ENV_PATH", "backup_env_path"),
    )
    db_container: str | None = Field(default=None, validation_alias=AliasChoices("DB_CONTAINER", "db_container"))
    db_name: str | None = Field(default=None, validation_alias=AliasChoices("DB_NAME", "db_name"))
    db_user: str | None = Field(default=None, validation_alias=AliasChoices("DB_USER", "db_user"))

    webhook_secret: str | None = None
    webhook_port: int = Field(default=8000, validation_alias=AliasChoices("WEBHOOK_PORT", "webhook_port"))
    public_base_url: str | None = None

    def sys_admin_id_set(self) -> Set[int]:
        if not self.sys_admin_ids:
            return set()
        return {int(item.strip()) for item in self.sys_admin_ids.split(",") if item.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
