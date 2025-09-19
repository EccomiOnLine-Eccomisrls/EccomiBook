# apps/backend/app/deps.py
from __future__ import annotations
import os
from fastapi import Header, HTTPException
from .users import USERS_BY_KEY, User, seed_demo_users

# Interruttore: se = "1" la API accetta richieste senza x-api-key
ALLOW_OPEN_API = os.getenv("ALLOW_OPEN_API", "0") == "1"

def _demo_user() -> User:
    # assicurati che esista un utente demo in memoria
    if not USERS_BY_KEY:
        seed_demo_users()
    # prova owner demo
    u = USERS_BY_KEY.get("demo_key_owner")
    if u:
        return u
    # fallback minimale
    return User(
        user_id="u_open",
        email="open@eccomibook.local",
        api_key="open_mode",
        plan="OWNER_FULL",
        status="active",
        role="OWNER_FULL",
    )

def get_current_user(x_api_key: str | None = Header(default=None)) -> User:
    """
    - Se ALLOW_OPEN_API=1 e manca la chiave → ritorna un demo user (nessun errore).
    - Se ALLOW_OPEN_API=0 → richiede x-api-key valida.
    """
    if (not x_api_key) and ALLOW_OPEN_API:
        return _demo_user()

    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key mancante")

    user = USERS_BY_KEY.get(x_api_key)
    if not user:
        # Se in open mode accettiamo anche chiavi sconosciute come demo.
        if ALLOW_OPEN_API:
            return _demo_user()
        raise HTTPException(status_code=401, detail="API key non valida")

    if user.status not in ("active", "trialing"):
        raise HTTPException(status_code=403, detail=f"Utente non attivo: {user.status}")

    return user
