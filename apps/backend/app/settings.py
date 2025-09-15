from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "EccomiBook Backend"
    OWNER_API_KEY: str | None = None   # <- mettila su Render env
    # opzionale: prefisso per header utente (per i contatori)
    USER_HEADER: str = "X-User"        # es. email, id Shopify, ecc.

settings = Settings()
