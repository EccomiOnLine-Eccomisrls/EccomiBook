# apps/backend/app/users.py
from __future__ import annotations

from typing import Dict, Any, Optional, List
import json

from . import storage

# In-memory “DB”
USERS: Dict[str, Dict[str, Any]] = {}         # key: user_id
USERS_BY_KEY: Dict[str, Dict[str, Any]] = {}  # key: api_key -> user

_USERS_PATH = storage.file_path("admin/users.json")


def _rebuild_indexes() -> None:
    """Ricostruisce USERS_BY_KEY a partire da USERS."""
    global USERS_BY_KEY
    USERS_BY_KEY = {}
    for u in USERS.values():
        k = (u.get("api_key") or "").strip()
        if k:
            USERS_BY_KEY[k] = u


def load_users() -> None:
    """Carica gli utenti da disco in USERS / USERS_BY_KEY."""
    global USERS
    try:
        path = _USERS_PATH
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
            if isinstance(data, dict):
                USERS = data
                _rebuild_indexes()
                return
    except Exception:
        pass
    USERS = {}
    _rebuild_indexes()


def save_users() -> None:
    """Salva USERS su disco (atomico)."""
    try:
        path = _USERS_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(USERS, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        print(f"⚠️  Impossibile salvare users.json: {e}")


def get_user_by_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    if not api_key:
        return None
    return USERS_BY_KEY.get(api_key.strip())


def list_users() -> List[Dict[str, Any]]:
    return list(USERS.values())


def _put_user(u: Dict[str, Any]) -> Dict[str, Any]:
    """Inserisce/Aggiorna utente nel DB in-memory e ricostruisce gli indici."""
    uid = u.get("id")
    if not uid:
        raise ValueError("user.id mancante")
    USERS[str(uid)] = u
    _rebuild_indexes()
    return u


def seed_demo_users() -> None:
    """
    Semina alcuni utenti di esempio.
    - OWNER_FULL: può usare /admin/*
    - USER: piano START
    """
    if USERS:
        return

    owner = {
        "id": "owner_full",
        "name": "Owner",
        "role": "OWNER_FULL",
        "plan": "OWNER",
        "status": "ACTIVE",
        "api_key": "demo_key_owner",
    }
    user = {
        "id": "demo_user_start",
        "name": "Demo Start",
        "role": "USER",
        "plan": "START",
        "status": "ACTIVE",
        "api_key": "demo_key_user",
    }
    _put_user(owner)
    _put_user(user)
    save_users()
