import os
from pydantic import BaseModel


class Settings(BaseModel):
    environment: str = os.getenv("ENVIRONMENT", "production")
    x_api_key: str | None = os.getenv("X_API_KEY", "Lillinoecommerce@1")
    storage_dir: str | None = os.getenv("STORAGE_DIR")  # facoltativa


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
