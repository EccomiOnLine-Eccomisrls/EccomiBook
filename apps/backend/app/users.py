# apps/backend/app/users.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional, Dict
import json

from . import storage  # path persistenti (BASE_DIR / "admin" / "users.json")


@dataclass
class User:
    user_id: str
    email: str
    api_key: str
    plan: str                  # START | GROWTH | PRO | OWNER_FULL
    status: str                # active | trialing | past_due | canceled
    role: str = "USER"         # USER | OWNER_FULL
    current_period_end: Optional[str] = None
    quota_monthly_used: int = 0


# Archivio in memoria indicizzato per API key
USERS_BY_KEY: Dict[str, User] = {}

# File di persistenza su disco (Render Disk / data dir)
_USERS_FILE = storage.file_path("admin/users.json")


def _ensure_users_dir() -> None:
    _USERS_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_users() -> None:
    """Carica gli utenti dal JSON persistente in USERS_BY_KEY."""
    _ensure_users_dir()
    if _USERS_FILE.exists():
        data = json.loads(_USERS_FILE.read_text())
        USERS_BY_KEY.clear()
        for item in data:
            u = User(**item)
            USERS_BY_KEY[u.api_key] = u


def save_users() -> None:
    """Salva USERS_BY_KEY nel JSON persistente."""
    _ensure_users_dir()
    payload = [asdict(u) for u in USERS_BY_KEY.values()]
    _USERS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def seed_demo_users() -> None:
    """
    Solo per MVP/demo: se non ci sono utenti caricati, crea un admin OWNER_FULL
    e un utente START di esempio, poi salva su disco.
    """
    if USERS_BY_KEY:
        return

    # Admin OWNER_FULL (usa la tua chiave reale per il pannello owner)
    admin = User(
        user_id="u_owner",
        email="owner@eccomibook.com",
        api_key="Lillinoecommerce@1",  # 🔑 la tua chiave admin
        plan="OWNER_FULL",
        status="active",
        role="OWNER_FULL",
    )

    # Utente START demo
    demo_user = User(
        user_id="u_start",
        email="demo@eccomibook.com",
        api_key="demo_key_start",
        plan="START",
        status="active",
        role="USER",
    )

    USERS_BY_KEY[admin.api_key] = admin
    USERS_BY_KEY[demo_user.api_key] = demo_user
    save_users()
