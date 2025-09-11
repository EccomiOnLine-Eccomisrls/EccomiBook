from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    APP_NAME: str = "EccomiBook Backend"
    APP_ENV: str = os.getenv("APP_ENV", "local")
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))

    # Stripe
    STRIPE_PUBLIC_KEY: str = os.getenv("STRIPE_PUBLIC_KEY", "")
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_ID: str = os.getenv("STRIPE_PRICE_ID", "")  # <= NEW (opzionale)

    # Redirect
    SUCCESS_URL: str = os.getenv("SUCCESS_URL", "http://localhost:8000/success")
    CANCEL_URL: str = os.getenv("CANCEL_URL", "http://localhost:8000/cancel")

    # DB
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data.db")

settings = Settings()
