# app/settings.py
import os
from pydantic import BaseModel

class Settings(BaseModel):
    APP_NAME: str = os.getenv("APP_NAME", "EccomiBook Backend")
    APP_ENV: str = os.getenv("APP_ENV", "production")
    OWNER_API_KEY: str = os.getenv("OWNER_API_KEY", "dev_owner_key")  # X-API-Key

settings = Settings()
