from fastapi import Header, HTTPException
from typing import Optional
from app.settings import settings
from app.models import Plan, PLAN_CAPS
from app import storage

class Caps:
    def __init__(self, plan: Plan, caps: dict, user_id: str):
        self.plan = plan
        self.caps = caps
        self.user_id = user_id

async def current_caps(
    x_api_key: Optional[str] = Header(default=None),
    x_plan:    Optional[str] = Header(default=None),
    x_user:    Optional[str] = Header(default=None),
):
    # chi sei (per i contatori)? default = "anon"
    user_id = (x_user or "anon").strip()

    # owner illimitato
    if settings.OWNER_API_KEY and x_api_key == settings.OWNER_API_KEY:
        return Caps(Plan.OWNER_FULL, PLAN_CAPS[Plan.OWNER_FULL], user_id)

    # altrimenti piano dichiarato da header X-Plan (start/growth/pro)
    plan_map = {
        "start": Plan.START,
        "growth": Plan.GROWTH,
        "pro": Plan.PRO,
    }
    plan = plan_map.get((x_plan or "").lower(), Plan.START)  # default: Start
    return Caps(plan, PLAN_CAPS[plan], user_id)

def ensure_can_create_book(caps: Caps):
    limit = caps.caps["max_books_per_month"]
    if limit is None:
        return
    used = storage.get_books_this_month(caps.user_id)
    if used >= limit:
        raise HTTPException(status_code=403, detail="Limite libri al mese raggiunto per il tuo piano")

def ensure_can_add_chapter(caps: Caps):
    limit = caps.caps["max_chapters_per_day"]
    if limit is None:
        return
    used = storage.get_chapters_today(caps.user_id)
    if used >= limit:
        raise HTTPException(status_code=403, detail="Limite capitoli/giorno raggiunto per il tuo piano")

def ensure_can_export(format: str, caps: Caps):
    allowed = {
        "pdf":  caps.caps.get("export_pdf", False),
        "epub": caps.caps.get("export_epub", False),
        "docx": caps.caps.get("export_docx", False),
    }
    if not allowed.get(format.lower(), False):
        raise HTTPException(status_code=403, detail=f"Export {format.upper()} non incluso nel tuo piano")
