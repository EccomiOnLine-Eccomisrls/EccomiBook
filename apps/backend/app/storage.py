# app/storage.py
from __future__ import annotations
from typing import Dict, Any, List
from datetime import datetime
import uuid

# ATTENZIONE: in-memory → si azzera a ogni deploy/restart.
DB: Dict[str, Any] = {
    "books": {},        # book_id -> book dict
    "chapters": {},     # chap_id -> chapter dict
    "limits": {},       # api_key -> contatori giornalieri
}


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def reset_daily_if_needed(counter: dict):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if counter.get("date") != today:
        counter["date"] = today
        counter["chapters_today"] = 0
