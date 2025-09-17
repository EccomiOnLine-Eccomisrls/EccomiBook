# apps/backend/routers/admin.py
from fastapi import APIRouter, Body
from typing import Optional
from ..deps import get_owner_full
from fastapi import Depends, HTTPException
from ..users import USERS_BY_KEY, User, save_users

router = APIRouter(prefix="/admin", tags=["owner_full"])

@router.get("/users", summary="Elenca utenti (pannello)")
def list_users(_: User = Depends(get_owner_full)):
    return [
        {
            "user_id": u.user_id,
            "email": u.email,
            "plan": u.plan,
            "status": u.status,
            "role": u.role,
            "quota_monthly_used": u.quota_monthly_used,
        }
        for u in USERS_BY_KEY.values()
    ]

@router.post("/users/set-plan", summary="Cambia piano utente")
def set_plan(
    api_key: str = Body(...),
    plan: str = Body(..., embed=True),
    _: User = Depends(get_owner_full),
):
    if api_key not in USERS_BY_KEY:
        raise HTTPException(status_code=404, detail="User non trovato")
    u = USERS_BY_KEY[api_key]
    u.plan = plan
    save_users()
    return {"ok": True, "user": {"email": u.email, "plan": u.plan}}

@router.post("/users/set-status", summary="Cambia stato sottoscrizione")
def set_status(
    api_key: str = Body(...),
    status: str = Body(..., embed=True),  # active | trialing | past_due | canceled
    _: User = Depends(get_owner_full),
):
    if api_key not in USERS_BY_KEY:
        raise HTTPException(status_code=404, detail="User non trovato")
    u = USERS_BY_KEY[api_key]
    u.status = status
    save_users()
    return {"ok": True, "user": {"email": u.email, "status": u.status}}

@router.post("/users/reset-quota", summary="Reset quota mensile")
def reset_quota(
    api_key: str = Body(...),
    _: User = Depends(get_owner_full),
):
    if api_key not in USERS_BY_KEY:
        raise HTTPException(status_code=404, detail="User non trovato")
    u = USERS_BY_KEY[api_key]
    u.quota_monthly_used = 0
    save_users()
    return {"ok": True, "user": {"email": u.email, "quota_monthly_used": u.quota_monthly_used}}
