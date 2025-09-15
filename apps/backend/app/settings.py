# app/settings.py
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = Field(default="production")
    APP_NAME: str = Field(default="EccomiBook Backend")

    # Accesso owner (tutto sbloccato)
    OWNER_API_KEY: str = Field(default="", description="Chiave admin (X-API-Key)")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
