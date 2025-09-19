# apps/backend/app/deps.py
from __future__ import annotations
from fastapi import Header, HTTPException
from pydantic import BaseModel

from .settings import get_settings
from .users import get_user_by_api_key, DEMO_USER


class CurrentUser(BaseModel):
    id: str
    email: str | None = None
    plan: str = "START"
    role: str = "USER"


def get_current_user(x_api_key: str | None = Header(default=None)) -> CurrentUser:
    """
    MVP: se c'è x-api-key valida -> utente reale.
         se NON c'è -> se allow_public=True allora utente DEMO,
                       altrimenti 401 'x-api-key richiesta'.
         se è presente ma NON valida -> 401 'API key non valida'.
    """
    settings = get_settings()

    # API key fornita: validiamo
    if x_api_key:
        user = get_user_by_api_key(x_api_key)
        if user:
            return CurrentUser(**user)
        raise HTTPException(status_code=401, detail="API key non valida")

    # Nessuna key: fallback pubblico se abilitato
    if settings.allow_public:
        return CurrentUser(**DEMO_USER)

    # Se non permesso, richiediamo la key
    raise HTTPException(status_code=401, detail="x-api-key richiesta")
