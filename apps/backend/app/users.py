# apps/backend/app/users.py
from __future__ import annotations
from typing import Optional
from . import storage

# Utente demo usato quando non c'è API key (MVP)
DEMO_USER = {
    "id": "demo_user",
    "email": None,
    "plan": "START",
    "role": "USER",
    "api_key": None,
}

# Semplice “DB” utenti salvato su file (opzionale in MVP)
_USR_FILE = storage.file_path("admin/users.json")
_USERS_CACHE: dict[str, dict] = {}


def load_users() -> None:
    global _USERS_CACHE
    try:
        if _USR_FILE.exists():
            _USERS_CACHE = storage.read_json(_USR_FILE) or {}
        else:
            _USERS_CACHE = {}
    except Exception:
        _USERS_CACHE = {}


def seed_demo_users() -> None:
    """
    Per MVP puoi lasciare vuoto o creare un owner con api_key nota.
    Non è necessario per funzionare in pubblico.
    """
    pass


def get_user_by_api_key(api_key: str) -> Optional[dict]:
    # Cerca tra gli utenti caricati (se presenti)
    for u in _UsersIterable():
        if u.get("api_key") == api_key:
            return u
    return None


def _UsersIterable():
    if not _USERS_CACHE:
        load_users()
    return _USERS_CACHE.values()
