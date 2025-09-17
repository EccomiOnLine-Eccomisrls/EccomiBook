# apps/backend/app/routers/admin.py
from __future__ import annotations
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field

# siamo in app/routers → per risalire a backend usiamo "..."
from ...deps import get_owner_full
from ...users import USERS_BY_KEY, User, save_users
from ...plans import ALL_PLANS, ACTIVE_STATUSES, normalize_plan

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------
# Helpers locali
# ---------------------------
def _get_user_by_id(user_id: str) -> User | None:
    for u in USERS_BY_KEY.values():
        if u.user_id == user_id:
            return u
    return None


# ---------------------------
# Schemi Pydantic (request)
# ---------------------------
class UserCreateIn(BaseModel):
    user_id: str = Field(..., example="u_002")
    email: str = Field(..., example="newuser@example.com")
    api_key: str = Field(..., example="new_user_key_abc")
    plan: str = Field(..., example="START", description="START | GROWTH | PRO | OWNER_FULL")
    status: str = Field("active", example="active", description="active | trialing | past_due | canceled")
    role: str = Field("USER", example="USER", description="USER | OWNER_FULL")


class UserPatchIn(BaseModel):
    email: Optional[str] = Field(None, example="newmail@example.com")
    plan: Optional[str] = Field(None, example="PRO")
    status: Optional[str] = Field(None, example="trialing")
    role: Optional[str] = Field(None, example="OWNER_FULL")
    quota_monthly_used: Optional[int] = Field(None, example=0)


class PlanChangeIn(BaseModel):
    plan: str = Field(..., example="GROWTH")


# ---------------------------
# Endpoints (solo OWNER_FULL)
# ---------------------------

@router.get("/users", summary="Lista utenti (solo OWNER_FULL)")
def list_users(_: User = Depends(get_owner_full)):
    """Ritorna elenco utenti con API key, piano, status e quota."""
    data = []
    for u in USERS_BY_KEY.values():
        data.append({
            "user_id": u.user_id,
            "email": u.email,
            "api_key": u.api_key,
            "plan": u.plan,
            "status": u.status,
            "role": u.role,
            "quota_monthly_used": u.quota_monthly_used,
        })
    return {"count": len(data), "items": data}


@router.post("/users", summary="Crea utente (solo OWNER_FULL)")
def create_user(payload: UserCreateIn, _: User = Depends(get_owner_full)):
    # api_key deve essere unica
    if payload.api_key in USERS_BY_KEY:
        raise HTTPException(status_code=400, detail="api_key già presente")

    plan = normalize_plan(payload.plan)
    if plan not in ALL_PLANS:
        raise HTTPException(status_code=400, detail=f"Piano non valido: {payload.plan}")

    if payload.status not in ACTIVE_STATUSES | {"canceled", "trialing", "past_due"}:
        raise HTTPException(status_code=400, detail=f"Status non valido: {payload.status}")

    u = User(
        user_id=payload.user_id,
        email=payload.email,
        api_key=payload.api_key,
        plan=plan,
        status=payload.status,
        role=payload.role,
    )
    USERS_BY_KEY[u.api_key] = u
    save_users()
    return {"ok": True, "user": u.__dict__}


@router.get("/users/{user_id}", summary="Dettaglio utente (solo OWNER_FULL)")
def get_user(user_id: str, _: User = Depends(get_owner_full)):
    u = _get_user_by_id(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    return u.__dict__


@router.patch("/users/{user_id}", summary="Aggiorna utente (solo OWNER_FULL)")
def patch_user(user_id: str, payload: UserPatchIn, _: User = Depends(get_owner_full)):
    u = _get_user_by_id(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    if payload.email is not None:
        u.email = payload.email

    if payload.plan is not None:
        plan = normalize_plan(payload.plan)
        if plan not in ALL_PLANS:
            raise HTTPException(status_code=400, detail=f"Piano non valido: {payload.plan}")
        u.plan = plan

    if payload.status is not None:
        if payload.status not in ACTIVE_STATUSES | {"canceled", "trialing", "past_due"}:
            raise HTTPException(status_code=400, detail=f"Status non valido: {payload.status}")
        u.status = payload.status

    if payload.role is not None:
        if payload.role not in {"USER", "OWNER_FULL"}:
            raise HTTPException(status_code=400, detail="Ruolo non valido")
        u.role = payload.role

    if payload.quota_monthly_used is not None:
        u.quota_monthly_used = max(0, int(payload.quota_monthly_used))

    save_users()
    return {"ok": True, "user": u.__dict__}


@router.post("/users/{user_id}/plan", summary="Cambia piano (solo OWNER_FULL)")
def change_plan(user_id: str, payload: PlanChangeIn, _: User = Depends(get_owner_full)):
    u = _get_user_by_id(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    plan = normalize_plan(payload.plan)
    if plan not in ALL_PLANS:
        raise HTTPException(status_code=400, detail=f"Piano non valido: {payload.plan}")

    u.plan = plan
    save_users()
    return {"ok": True, "user": u.__dict__}


@router.post("/users/{user_id}/quota/reset", summary="Reset quota mensile (solo OWNER_FULL)")
def reset_quota(user_id: str, _: User = Depends(get_owner_full)):
    u = _get_user_by_id(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    u.quota_monthly_used = 0
    save_users()
    return {"ok": True, "user": u.__dict__}


@router.delete("/users/{user_id}", summary="Elimina utente (solo OWNER_FULL)")
def delete_user(user_id: str, _: User = Depends(get_owner_full)):
    # cancelliamo per api_key (la nostra mappa è per chiave)
    target_key = None
    for k, u in USERS_BY_KEY.items():
        if u.user_id == user_id:
            target_key = k
            break
    if not target_key:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    USERS_BY_KEY.pop(target_key, None)
    save_users()
    return {"ok": True, "deleted_user_id": user_id}


@router.get("/stats", summary="Statistiche semplici (solo OWNER_FULL)")
def stats(_: User = Depends(get_owner_full)):
    total = len(USERS_BY_KEY)
    by_plan = {}
    for u in USERS_BY_KEY.values():
        by_plan[u.plan] = by_plan.get(u.plan, 0) + 1
    return {"users_total": total, "by_plan": by_plan}
