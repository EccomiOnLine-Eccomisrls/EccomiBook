# apps/backend/app/settings.py
from __future__ import annotations
import os
from pydantic import BaseModel
from typing import List


class Settings(BaseModel):
    environment: str = os.getenv("ENV", "production")

    # ✅ abilita fallback pubblico senza API key (MVP)
    allow_public: bool = os.getenv("ALLOW_PUBLIC", "true").lower() in ("1", "true", "yes")

    # 🌍 CORS origins (lista di domini da cui accettare richieste)
    cors_allow_origins: List[str] = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Leggi da variabile ambiente CORS_ALLOW_ORIGINS
        origins = os.getenv("CORS_ALLOW_ORIGINS")
        if origins:
            # separa per virgole → "https://eccomibook.com,https://eccomibook-frontend.onrender.com"
            self.cors_allow_origins = [o.strip() for o in origins.split(",") if o.strip()]
        else:
            # fallback dev-friendly
            self.cors_allow_origins = ["*"]


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
