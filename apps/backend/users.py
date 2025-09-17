# apps/backend/users.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List
from datetime import datetime
import json
from pathlib import Path

from . import storage

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

# archivio in memoria
USERS_BY_KEY: Dict[str, User] = {}

# file persistenza
_USERS_FILE = storage.file_path("admin/users.json")

def _ensure_users_dir():
    _USERS_FILE.parent.mkdir(parents=True, exist_ok=True)

def load_users() -> None:
    _ensure_users_dir()
    if _USERS_FILE.exists():
        data = json.loads(_USERS_FILE.read_text())
        USERS_BY_KEY.clear()
        for item in data:
            u = User(**item)
            USERS_BY_KEY[u.api_key] = u

def save_users() -> None:
    _ensure_users_dir()
    payload = [asdict(u) for u in USERS_BY_KEY.values()]
    _USERS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

def seed_demo_users() -> None:
    """Solo per MVP/demo; rimuovi in produzione."""
    if USERS_BY_KEY:
        return
    # un owner_full (admin)
    admin = User(
        user_id="u_admin",
        email="owner@example.com",
        api_key="demo_key_owner",
        plan="OWNER_FULL",
        status="active",
        role="OWNER_FULL",
    )
    # un utente START
    u1 = User(
        user_id="u_1",
        email="user@example.com",
        api_key="demo_key_user",
        plan="START",
        status="active",
        role="USER",
    )
    USERS_BY_KEY[admin.api_key] = admin
    USERS_BY_KEY[u1.api_key] = u1
    save_users()
