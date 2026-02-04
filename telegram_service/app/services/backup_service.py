from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shlex
import subprocess
import tempfile
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from sqlalchemy.engine.url import make_url

import fcntl
from aiogram import Bot
from aiogram.types import FSInputFile

from app.core.config import Settings, get_settings


logger = logging.getLogger(__name__)

MAX_BACKUP_SIZE_BYTES = 2 * 1024 * 1024 * 1024
DEFAULT_LOCK_PATH = Path("/tmp/backup.lock")
DEFAULT_METADATA_FILENAME = "last_backup.json"
DEFAULT_RESTORE_LOG = Path("/var/log/db_restore.log")
BACKUP_TIMEOUT_SECONDS = 10 * 60


class BackupError(RuntimeError):
    pass


class BackupOperationInProgress(BackupError):
    pass


class BackupNotFound(BackupError):
    pass


class BackupConfigError(BackupError):
    pass


@dataclass(slots=True)
class BackupMetadata:
    created_at: str
    filename: str
    path: str
    size_bytes: int
    sha256: str
    tg: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "created_at": self.created_at,
            "filename": self.filename,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }
        if self.tg is not None:
            payload["tg"] = self.tg
        return payload


def _format_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_backup_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        values[key] = value
    return values


class BackupOperationLock:
    def __init__(self, lock_path: Path = DEFAULT_LOCK_PATH) -> None:
        self._lock_path = lock_path
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self) -> Any:
        await self._lock.acquire()
        file_handle = None
        try:
            file_handle = self._lock_path.open("w")
            try:
                fcntl.flock(file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise BackupOperationInProgress("Операция уже выполняется.") from exc
            yield
        finally:
            if file_handle is not None:
                fcntl.flock(file_handle, fcntl.LOCK_UN)
                file_handle.close()
            self._lock.release()


class BackupService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if self._settings.backup_chat_id is None:
            raise BackupConfigError("BACKUP_CHAT_ID is required.")
        self._backup_dir = Path(self._settings.backup_dir)
        if not self._backup_dir.is_absolute():
            raise BackupConfigError("BACKUP_DIR должен быть абсолютным путём.")
        self._metadata_path = self._backup_dir / DEFAULT_METADATA_FILENAME
        self._lock = BackupOperationLock()

    def _get_backup_env(self) -> dict[str, str]:
        env_path = Path(self._settings.backup_env_path)
        return _parse_backup_env(env_path)

    def _resolve_db_config(self) -> tuple[str, str, str, str]:
        backup_env = self._get_backup_env()
        db_host = backup_env.get("DB_HOST") or "db"
        db_port = backup_env.get("DB_PORT") or "5432"
        db_name = self._settings.db_name or backup_env.get("DB_NAME")
        db_user = self._settings.db_user or backup_env.get("DB_USER")
        if not db_name or not db_user:
            raise BackupConfigError("DB_NAME/DB_USER должны быть заданы.")
        return db_host, db_port, db_name, db_user

    def _get_passphrase(self) -> str:
        if os.getenv("BACKUP_PASSPHRASE"):
            return os.environ["BACKUP_PASSPHRASE"]
        backup_env = self._get_backup_env()
        passphrase = backup_env.get("BACKUP_PASSPHRASE")
        if not passphrase:
            raise BackupConfigError("BACKUP_PASSPHRASE не задан.")
        return passphrase

    def _extract_db_password(self) -> str | None:
        database_url = self._settings.database_url or os.getenv("DATABASE_URL")
        if not database_url:
            return None
        try:
            return make_url(database_url).password
        except Exception:  # pragma: no cover - defensive in case of malformed URL
            return None

    def _load_metadata(self) -> dict[str, Any] | None:
        if not self._metadata_path.exists():
            return None
        try:
            return json.loads(self._metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Не удалось прочитать last_backup.json")
            return None

    def _normalize_metadata(self, data: dict[str, Any] | None) -> BackupMetadata | None:
        if not data:
            return None
        filename = data.get("filename")
        path = data.get("path")
        created_at = data.get("created_at")
        size_bytes = data.get("size_bytes")
        sha256 = data.get("sha256")
        tg = data.get("tg")

        if not filename and data.get("backup_file"):
            filename = data["backup_file"]
        if not path and filename:
            backup_dir = data.get("backup_dir") or str(self._backup_dir)
            path = str(Path(backup_dir) / filename)
        if not created_at and data.get("timestamp"):
            try:
                parsed = datetime.strptime(data["timestamp"], "%Y%m%d_%H%M%S")
                created_at = _format_iso(parsed.replace(tzinfo=timezone.utc))
            except ValueError:
                created_at = None

        if not filename or not path:
            return None
        file_path = Path(path)
        if not file_path.exists():
            return None

        if size_bytes is None:
            size_bytes = file_path.stat().st_size
        if not created_at:
            created_at = _format_iso(datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc))
        if not sha256:
            sha256 = self.compute_sha256(file_path)

        return BackupMetadata(
            created_at=created_at,
            filename=filename,
            path=str(file_path),
            size_bytes=int(size_bytes),
            sha256=str(sha256),
            tg=tg,
        )

    def _write_metadata(self, metadata: BackupMetadata) -> None:
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        self._metadata_path.write_text(
            json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_latest_backup_file(self) -> BackupMetadata:
        if not self._backup_dir.exists():
            raise BackupNotFound("Каталог бэкапов не найден.")
        backups = sorted(self._backup_dir.glob("*.dump.gpg"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not backups:
            raise BackupNotFound("Файлы бэкапов не найдены.")
        file_path = backups[0]
        created_at = _format_iso(datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc))
        metadata = BackupMetadata(
            created_at=created_at,
            filename=file_path.name,
            path=str(file_path),
            size_bytes=file_path.stat().st_size,
            sha256=self.compute_sha256(file_path),
        )
        return metadata

    def get_latest_metadata(self) -> BackupMetadata:
        metadata = self._normalize_metadata(self._load_metadata())
        if metadata:
            return metadata
        metadata = self.get_latest_backup_file()
        self._write_metadata(metadata)
        return metadata

    def compute_sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file_obj:
            for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    async def run_backup_script(self) -> BackupMetadata:
        async with self._lock.acquire():
            script_path = self._settings.backup_script_path
            env_path = self._settings.backup_env_path
            command = f"set -a && . {shlex.quote(env_path)} && set +a && {shlex.quote(script_path)}"
            process = await asyncio.create_subprocess_exec(
                "bash",
                "-lc",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=BACKUP_TIMEOUT_SECONDS)
            except asyncio.TimeoutError as exc:
                process.kill()
                raise BackupError("Время выполнения бэкапа превышено.") from exc
            if process.returncode != 0:
                logger.error("Backup script failed: %s", stderr.decode("utf-8", errors="ignore"))
                raise BackupError("Ошибка запуска скрипта бэкапа.")
            logger.info("Backup script output: %s", stdout.decode("utf-8", errors="ignore").strip())
            metadata = self.get_latest_backup_file()
            self._write_metadata(metadata)
            return metadata

    async def send_latest_to_backup_chat(self, bot: Bot) -> BackupMetadata:
        metadata = self.get_latest_metadata()
        if metadata.size_bytes > MAX_BACKUP_SIZE_BYTES:
            raise BackupError("Размер бэкапа превышает лимит отправки.")
        caption = (
            "📦 Резервная копия\n"
            f"Создан: {metadata.created_at}\n"
            f"Файл: {metadata.filename}\n"
            f"Размер: {metadata.size_bytes} байт\n"
            f"SHA256: {metadata.sha256}"
        )
        document = FSInputFile(metadata.path, filename=metadata.filename)
        message = await bot.send_document(
            chat_id=self._settings.backup_chat_id,
            document=document,
            caption=caption,
        )
        if message.document is None:
            raise BackupError("Не удалось отправить файл бэкапа.")
        metadata.tg = {
            "chat_id": message.chat.id,
            "message_id": message.message_id,
            "file_id": message.document.file_id if message.document else None,
        }
        self._write_metadata(metadata)
        return metadata

    async def download_backup_from_file_id(self, bot: Bot, file_id: str, dest_path: Path) -> None:
        if dest_path.exists():
            dest_path.unlink()
        tg_file = await bot.get_file(file_id)
        if not tg_file.file_path:
            raise BackupError("Не удалось скачать файл из Telegram, пришлите файл заново.")
        if tg_file.file_size and tg_file.file_size > MAX_BACKUP_SIZE_BYTES:
            raise BackupError("Размер файла превышает лимит.")
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        await bot.download_file(tg_file.file_path, destination=dest_path)

    def _resolve_latest_local_metadata(self) -> BackupMetadata:
        metadata = self._normalize_metadata(self._load_metadata())
        if metadata:
            return metadata
        if not self._backup_dir.exists():
            raise BackupError(f"Файлы бэкапов не найдены в {self._backup_dir}")
        backups = sorted(self._backup_dir.glob("*.dump.gpg"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not backups:
            raise BackupError(f"Файлы бэкапов не найдены в {self._backup_dir}")
        file_path = backups[0]
        created_at = _format_iso(datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc))
        return BackupMetadata(
            created_at=created_at,
            filename=file_path.name,
            path=str(file_path),
            size_bytes=file_path.stat().st_size,
            sha256=self.compute_sha256(file_path),
        )

    def _build_import_path(self, original_name: str | None) -> Path:
        imports_dir = self._backup_dir / "imports"
        imports_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(original_name or "backup.dump.gpg").name
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        return imports_dir / f"{timestamp}_{safe_name}"

    def build_import_path(self, original_name: str | None) -> Path:
        return self._build_import_path(original_name)

    async def restore_latest_local_backup(self) -> None:
        metadata = self._resolve_latest_local_metadata()
        await self.restore_from_backup_file(Path(metadata.path))

    async def restore_from_uploaded_tg_document(
        self, bot: Bot, file_id: str, original_name: str | None = None
    ) -> Path:
        dest_path = self._build_import_path(original_name)
        await self.download_backup_from_file_id(bot, file_id, dest_path)
        await self.restore_from_backup_file(dest_path)
        return dest_path

    async def restore_from_backup_file(self, path: Path) -> None:
        async with self._lock.acquire():
            db_host, db_port, db_name, db_user = self._resolve_db_config()
            passphrase = self._get_passphrase()
            db_password = self._extract_db_password()
            if not db_password:
                raise BackupConfigError(
                    "Пароль БД не найден. Укажите пароль в DATABASE_URL."
                )
            env = os.environ.copy()
            if db_password:
                env["PGPASSWORD"] = db_password
            restore_log = DEFAULT_RESTORE_LOG
            restore_log.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".dump") as temp_file:
                plain_path = Path(temp_file.name)

            try:
                with restore_log.open("ab") as log_file:
                    try:
                        gpg_proc = await asyncio.create_subprocess_exec(
                            "gpg",
                            "--batch",
                            "--yes",
                            "--pinentry-mode",
                            "loopback",
                            "--passphrase-fd",
                            "0",
                            "-o",
                            str(plain_path),
                            "-d",
                            str(path),
                            stdin=asyncio.subprocess.PIPE,
                            stdout=log_file,
                            stderr=log_file,
                        )
                    except FileNotFoundError as exc:
                        raise BackupError("gpg не найден.") from exc
                    await gpg_proc.communicate(passphrase.encode("utf-8"))
                    if gpg_proc.returncode != 0:
                        raise BackupError("Не удалось расшифровать бэкап.")

                    with plain_path.open("rb") as dump_file:
                        try:
                            await asyncio.to_thread(
                                subprocess.run,
                                [
                                    "psql",
                                    "-h",
                                    db_host,
                                    "-p",
                                    db_port,
                                    "-U",
                                    db_user,
                                    db_name,
                                ],
                                stdin=dump_file,
                                stdout=log_file,
                                stderr=subprocess.PIPE,
                                env=env,
                                check=True,
                            )
                        except FileNotFoundError as exc:
                            raise BackupError("psql не найден.") from exc
                        except subprocess.CalledProcessError as exc:
                            stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else ""
                            logger.error("psql restore failed: %s", stderr.strip())
                            raise BackupError(
                                "Ошибка восстановления базы данных (psql). Подробности в логах."
                            ) from exc
            finally:
                if plain_path.exists():
                    plain_path.unlink()
