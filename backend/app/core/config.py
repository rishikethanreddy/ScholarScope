"""Application settings, read once from environment variables (and backend/.env)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    app_env: str = field(default_factory=lambda: os.environ.get("APP_ENV", "development"))
    database_url: str = field(
        default_factory=lambda: os.environ.get(
            "DATABASE_URL", f"sqlite:///{(BACKEND_DIR / 'scholarscope.db').as_posix()}"
        )
    )
    secret_key: str = field(default_factory=lambda: os.environ.get("SECRET_KEY", ""))
    token_ttl_minutes: int = field(default_factory=lambda: _int("TOKEN_TTL_MINUTES", 60 * 12))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip()
            for o in os.environ.get(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
            if o.strip()
        )
    )

    # Crawler
    crawler_user_agent: str = field(
        default_factory=lambda: os.environ.get(
            "CRAWLER_USER_AGENT",
            "ScholarScopeBot/1.0 (academic project; scholarship freshness monitor)",
        )
    )
    crawler_timeout_seconds: float = field(
        default_factory=lambda: float(os.environ.get("CRAWLER_TIMEOUT_SECONDS", "25"))
    )
    crawler_max_bytes: int = field(default_factory=lambda: _int("CRAWLER_MAX_BYTES", 15 * 1024 * 1024))
    crawler_max_redirects: int = field(default_factory=lambda: _int("CRAWLER_MAX_REDIRECTS", 5))
    crawler_max_retries: int = field(default_factory=lambda: _int("CRAWLER_MAX_RETRIES", 3))
    crawler_min_domain_interval_seconds: float = field(
        default_factory=lambda: float(os.environ.get("CRAWLER_MIN_DOMAIN_INTERVAL_SECONDS", "3"))
    )
    crawler_allow_private_hosts: bool = field(
        default_factory=lambda: _bool("CRAWLER_ALLOW_PRIVATE_HOSTS", False)
    )
    scheduler_enabled: bool = field(default_factory=lambda: _bool("SCHEDULER_ENABLED", True))
    scheduler_tick_seconds: int = field(default_factory=lambda: _int("SCHEDULER_TICK_SECONDS", 60))

    # LLM extraction (provider-agnostic). AI_API_KEY is accepted for backwards compatibility.
    llm_provider: str = field(default_factory=lambda: os.environ.get("LLM_PROVIDER", "gemini").lower())
    llm_api_key: str = field(
        default_factory=lambda: os.environ.get("LLM_API_KEY") or os.environ.get("AI_API_KEY", "")
    )
    llm_model: str = field(default_factory=lambda: os.environ.get("LLM_MODEL", ""))
    llm_timeout_seconds: float = field(
        default_factory=lambda: float(os.environ.get("LLM_TIMEOUT_SECONDS", "90"))
    )
    llm_max_input_chars: int = field(default_factory=lambda: _int("LLM_MAX_INPUT_CHARS", 60000))

    # Uploads
    max_upload_bytes: int = field(default_factory=lambda: _int("MAX_UPLOAD_BYTES", 10 * 1024 * 1024))

    demo_mode: bool = field(default_factory=lambda: _bool("DEMO_MODE", False))

    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("DATA_DIR") or BACKEND_DIR / "data"))
    config_dir: Path = BACKEND_DIR / "config"

    @property
    def snapshots_dir(self) -> Path:
        return self.data_dir / "snapshots"

    @property
    def fixtures_dir(self) -> Path:
        return self.data_dir / "fixtures"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def load_config_file(name: str) -> dict:
    """Load a JSON configuration file from backend/config (vocabulary, policies, weights)."""
    path = get_settings().config_dir / name
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
