# apps/backend/app/deps.py
from __future__ import annotations

from fastapi import Header, HTTPException, Depends
from .users import USERS_BY_KEY, User

ACTIVE_STATUSES = {"active", "trialing"}

def get_current_user(x_api_key: str | None = Header(default=None)) -> User:
    """
    Autenticazione semplice via x-api-key.
    - 401 se manca o non esiste
    - 403 se l'account non è attivo
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="x-api-key richiesta")

    u = USERS_BY_KEY.get(x_api_key)
    if not u:
        raise HTTPException(status_code=401, detail="API key non valida")

    if (u.status or "").lower() not in ACTIVE_STATUSES:
        raise HTTPException(status_code=403, detail="Account non attivo")

    return u

def get_owner_full(user: User = Depends(get_current_user)) -> User:
    """
    Consente l’accesso solo a chi ha ruolo/plan OWNER_FULL.
    Usato dagli endpoint admin.
    """
    role = (user.role or "").upper()
    plan = (user.plan or "").upper()
    if role == "OWNER_FULL" or plan == "OWNER_FULL":
        return user
    raise HTTPException(status_code=403, detail="Solo OWNER_FULL")
