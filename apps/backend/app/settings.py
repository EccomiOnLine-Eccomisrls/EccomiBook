# apps/backend/app/settings.py
from __future__ import annotations
import os
from pydantic import BaseModel


class Settings(BaseModel):
    environment: str = os.getenv("ENV", "production")
    # ✅ abilita fallback pubblico senza API key (MVP)
    allow_public: bool = os.getenv("ALLOW_PUBLIC", "true").lower() in ("1", "true", "yes")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
