from pydantic import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    APP_ENV: str = "production"
    APP_NAME: str = "EccomiBook Backend"
    OWNER_API_KEY: str = ""                 # ← imposta su Render (X-API-Key)
    DATA_DIR: str = str(Path("./data"))     # dove salviamo i file (books.json, export)

settings = Settings()
