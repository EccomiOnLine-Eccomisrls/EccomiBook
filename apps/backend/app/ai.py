import os
from datetime import date
from fastapi import Depends, Header, HTTPException
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from .models import Plan
from . import storage

# Definizione capacità per piano
PLAN_CAPS = {
    Plan.OWNER_FULL: dict(max_books=None, max_chapters_per_day=None, exports={"pdf": True, "epub": True, "docx": True}, priority="highest"),
    Plan.PRO:        dict(max_books=None, max_chapters_per_day=200, exports={"pdf": True, "epub": True, "docx": True}, priority="high"),
    Plan.GROWTH:     dict(max_books=5,   max_chapters_per_day=50,  exports={"pdf": True, "epub": True, "docx": False}, priority="high"),
    Plan.START:      dict(max_books=1,   max_chapters_per_day=10,  exports={"pdf": True, "epub": False, "docx": False}, priority="normal"),
}

@dataclass
class Caps:
    user_id: str
    plan: Plan
    max_books: Optional[int]
    max_chapters_per_day: Optional[int]
    exports: dict
    priority: str

def _caps_for_plan(user_id: str, plan: Plan) -> Caps:
    c = PLAN_CAPS[plan]
    return Caps(
        user_id=user_id,
        plan=plan,
        max_books=c["max_books"],
        max_chapters_per_day=c["max_chapters_per_day"],
        exports=c["exports"],
        priority=c["priority"],
    )

def current_caps(
    x_api_key: Optional[str] = Header(None, convert_underscores=False),
) -> Caps:
    """
    Se l'header X-API-Key coincide con OWNER_API_KEY => owner_full (nessun limite).
    Altrimenti, per ora *default* al piano GROWTH (puoi cambiare qui la policy
    o collegare in futuro Shopify).
    """
    owner_key = os.getenv("OWNER_API_KEY", "").strip()
    user_id = "guest"

    if owner_key and x_api_key and x_api_key.strip() == owner_key:
        return _caps_for_plan(user_id="owner", plan=Plan.OWNER_FULL)

    # TODO: integrare con Shopify (lookup piano utente dal tuo shop)
    return _caps_for_plan(user_id=user_id, plan=Plan.GROWTH)

# ---------- Guardie / ensure ----------

def ensure_can_create_book(caps: Caps):
    if caps.plan == Plan.OWNER_FULL or caps.max_books is None:
        return
    # conteggio libri del mese per user
    used = storage.get_usage_books_month(caps.user_id, month=date.today().strftime("%Y-%m"))
    if used >= caps.max_books:
        raise HTTPException(status_code=403, detail="Limite libri raggiunto per il tuo piano")

def ensure_can_add_chapter(caps: Caps):
    if caps.plan == Plan.OWNER_FULL or caps.max_chapters_per_day is None:
        return
    used = storage.get_usage_chapters_day(caps.user_id, day=date.today().isoformat())
    if used >= caps.max_chapters_per_day:
        raise HTTPException(status_code=403, detail="Limite capitoli/giorno raggiunto per il tuo piano")

def ensure_can_export(fmt: str, caps: Caps):
    if caps.plan == Plan.OWNER_FULL:
        return
    allowed = caps.exports.get(fmt.lower(), False)
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Export {fmt.upper()} non incluso nel tuo piano")
