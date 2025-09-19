# apps/backend/app/deps.py
from __future__ import annotations

from fastapi import Header, HTTPException
from typing import Optional

from .users import get_user_by_api_key

# ------------------------------------------------------------
# get_current_user  (MVP: non richiede x-api-key)
# ------------------------------------------------------------
def get_current_user(x_api_key: Optional[str] = Header(default=None)):
    """
    Ritorna l'utente corrente.
    - Se viene passata una x-api-key valida, usa quell'utente.
    - Altrimenti torna un utente DEMO con piano START (MVP senza login).
    """
    if x_api_key:
        u = get_user_by_api_key(x_api_key.strip())
        if not u:
            raise HTTPException(status_code=401, detail="API key non valida")
        return u

    # Utente DEMO di default: permette di usare il prodotto senza chiave
    return {
        "id": "demo_user",
        "name": "Demo",
        "plan": "START",
        "role": "USER",
        "status": "ACTIVE",
    }


# ------------------------------------------------------------
# get_owner_full  (per pannello /admin/*)
# ------------------------------------------------------------
def get_owner_full(x_api_key: Optional[str] = Header(default=None)):
    """
    Consente l'accesso SOLO a chi ha ruolo OWNER_FULL.
    Necessaria per le rotte admin.
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="x-api-key richiesta")

    u = get_user_by_api_key(x_api_key.strip())
    if not u:
        raise HTTPException(status_code=401, detail="API key non valida")

    if str(u.get("role", "")).upper() != "OWNER_FULL":
        raise HTTPException(status_code=403, detail="Permessi insufficienti (OWNER_FULL richiesto)")

    return u
