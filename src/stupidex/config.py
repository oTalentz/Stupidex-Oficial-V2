from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    value = max(minimum, value)
    return min(value, maximum) if maximum is not None else value


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("STUPIDEX_HOST", "0.0.0.0")
    port: int = _int("PORT", _int("STUPIDEX_PORT", 5000, 1, 65535), 1, 65535)
    data_dir: Path = Path(os.getenv("STUPIDEX_DATA_DIR", "./data")).resolve()
    frontend_url: str = os.getenv("FRONTEND_URL", "").rstrip("/")
    cors_origins: tuple[str, ...] = tuple(
        item.strip().rstrip("/")
        for item in os.getenv("STUPIDEX_CORS", "").split(",")
        if item.strip()
    )
    cookie_secure: bool = _bool("STUPIDEX_COOKIE_SECURE", True)
    shell_enabled: bool = _bool("STUPIDEX_ENABLE_SHELL", True)
    shell_require_approval: bool = _bool("STUPIDEX_SHELL_REQUIRE_APPROVAL", True)
    shell_allow_network: bool = _bool("STUPIDEX_SHELL_ALLOW_NETWORK", False)
    shell_timeout: int = _int("STUPIDEX_SHELL_MAX_TIMEOUT", 120, 1, 300)
    shell_output_limit: int = _int("STUPIDEX_SHELL_MAX_OUTPUT_BYTES", 65536, 1024, 1_000_000)
    max_workspace_bytes: int = _int("MAX_WORKSPACE_BYTES", 200_000_000, 1_000_000)
    max_upload_bytes: int = _int("MAX_ARCHIVE_BYTES", 50_000_000, 1_000_000)
    session_days: int = _int("STUPIDEX_SESSION_DAYS", 30, 1, 365)
    default_provider: str = os.getenv("STUPIDEX_PROVIDER", "openai")
    default_model: str = os.getenv("STUPIDEX_MODEL", "gpt-5.4")
    default_base_url: str = os.getenv("STUPIDEX_BASE_URL", "")
    app_secret: str = os.getenv("STUPIDEX_SECRET", "")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "stupidex.db"

    @property
    def workspace_root(self) -> Path:
        return self.data_dir / "workspaces"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.workspace_root.mkdir(parents=True, exist_ok=True)
