# apps/backend/app/routers/admin.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Body, Path
from typing import Optional

from ..deps import get_owner_full
from ..users import USERS_BY_KEY, save_users, load_users, User
from ..plans import PLANS, ACTIVE_STATUSES, normalize_plan

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/plans")
def list_plans(_: User = Depends(get_owner_full)):
    """Restituisce l’elenco dei piani disponibili."""
    return {"plans": list(PLANS.keys())}


@router.get("/users")
def list_users(_: User = Depends(get_owner_full)):
    """Lista utenti con dettagli completi."""
    load_users()
    return {
        "count": len(USERS_BY_KEY),
        "users": [vars(u) for u in USERS_BY_KEY.values()],
    }


@router.post("/users")
def create_user(
    email: str = Body(..., embed=True),
    api_key: str = Body(..., embed=True),
    plan: str = Body("START", embed=True),
    status: str = Body("active", embed=True),
    role: str = Body("USER", embed=True),
    _: User = Depends(get_owner_full),
):
    """Crea un nuovo utente con piano e stato."""
    load_users()
    if api_key in USERS_BY_KEY:
        raise HTTPException(status_code=400, detail="API key già esistente")

    plan_norm = normalize_plan(plan)
    if plan_norm not in PLANS:
        raise HTTPException(status_code=400, detail=f"Piano non valido: {plan}")

    allowed_status = {"active", "trialing", "past_due", "canceled"}
    if status not in allowed_status:
        raise HTTPException(status_code=400, detail=f"Status non valido: {status}")

    u = User(
        user_id=f"u_{len(USERS_BY_KEY)+1}",
        email=email,
        api_key=api_key,
        plan=plan_norm,
        status=status,
        role=role,
    )
    USERS_BY_KEY[api_key] = u
    save_users()
    return {"ok": True, "user": vars(u)}


@router.put("/users/{user_id}/plan")
def change_plan(
    user_id: str = Path(...),
    plan: str = Body(..., embed=True),
    _: User = Depends(get_owner_full),
):
    """Aggiorna il piano di un utente esistente."""
    load_users()
    target = next((u for u in USERS_BY_KEY.values() if u.user_id == user_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    plan_norm = normalize_plan(plan)
    if plan_norm not in PLANS:
        raise HTTPException(status_code=400, detail=f"Piano non valido: {plan}")
    target.plan = plan_norm
    save_users()
    return {"ok": True, "user": vars(target)}


@router.put("/users/{user_id}/status")
def change_status(
    user_id: str = Path(...),
    status: str = Body(..., embed=True),
    _: User = Depends(get_owner_full),
):
    """Aggiorna lo stato di sottoscrizione di un utente."""
    load_users()
    target = next((u for u in USERS_BY_KEY.values() if u.user_id == user_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    allowed = {"active", "trialing", "past_due", "canceled"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail=f"Status non valido: {status}")
    target.status = status
    save_users()
    return {"ok": True, "user": vars(target)}
