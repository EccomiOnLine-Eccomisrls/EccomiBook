# apps/backend/deps.py
from fastapi import Header, HTTPException
from .users import USERS_BY_KEY, User
from .plans import ACTIVE_STATUSES  # come definito prima

def get_current_user(x_api_key: str | None = Header(default=None)) -> User:
    if not x_api_key or x_api_key not in USERS_BY_KEY:
        raise HTTPException(status_code=401, detail="API key non valida")
    user = USERS_BY_KEY[x_api_key]
    if user.status not in ACTIVE_STATUSES and user.role != "OWNER_FULL":
        # gli owner_full possono accedere al pannello anche se past_due (tu decidi)
        raise HTTPException(status_code=402, detail=f"Sottoscrizione non attiva: {user.status}")
    return user

def get_owner_full(x_api_key: str | None = Header(default=None)) -> User:
    """Accesso al pannello: solo OWNER_FULL."""
    if not x_api_key or x_api_key not in USERS_BY_KEY:
        raise HTTPException(status_code=401, detail="API key non valida")
    user = USERS_BY_KEY[x_api_key]
    if user.role != "OWNER_FULL":
        raise HTTPException(status_code=403, detail="Permesso negato (richiede OWNER_FULL)")
    return user
