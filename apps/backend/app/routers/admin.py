# apps/backend/app/routers/admin.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict, List

from ..deps import get_owner_full     # protegge con ruolo OWNER_FULL
from ..users import load_users, save_users, list_users

router = APIRouter(prefix="/admin")


@router.get("/plans", summary="List Piani", description="Ritorna i piani disponibili.")
def get_plans(_: Dict[str, Any] = Depends(get_owner_full)) -> Dict[str, Any]:
    return {
        "items": [
            {"code": "START", "label": "Start"},
            {"code": "PRO", "label": "Pro"},
            {"code": "OWNER", "label": "Owner"},
        ]
    }


@router.get("/users", summary="List Users")
def admin_list_users(_: Dict[str, Any] = Depends(get_owner_full)) -> Dict[str, Any]:
    load_users()
    return {"items": list_users()}


@router.post("/users", summary="Create User")
def admin_create_user(payload: Dict[str, Any], _: Dict[str, Any] = Depends(get_owner_full)) -> Dict[str, Any]:
    """
    payload atteso:
    {
      "id": "id_unico",
      "name": "Nome",
      "role": "USER|OWNER_FULL",
      "plan": "START|PRO|OWNER",
      "status": "ACTIVE|SUSPENDED",
      "api_key": "chiave"
    }
    """
    required = ["id", "name", "role", "plan", "status", "api_key"]
    for k in required:
        if not payload.get(k):
            raise HTTPException(status_code=422, detail=f"Campo mancante: {k}")

    # Carica, verifica duplicati per id / api_key, salva
    from ..users import USERS, USERS_BY_KEY  # import locale per evitare cicli
    load_users()

    uid = str(payload["id"])
    if uid in USERS:
        raise HTTPException(status_code=409, detail="user id già esistente")

    if payload["api_key"] in USERS_BY_KEY:
        raise HTTPException(status_code=409, detail="api_key già esistente")

    USERS[uid] = {
        "id": uid,
        "name": payload["name"],
        "role": payload["role"],
        "plan": payload["plan"],
        "status": payload["status"],
        "api_key": payload["api_key"],
    }
    # ricostruisci indice e salva
    from ..users import _rebuild_indexes
    _rebuild_indexes()
    save_users()
    return {"ok": True, "user": USERS[uid]}


@router.put("/users/{user_id}/plan", summary="Change Plan")
def admin_change_plan(user_id: str, payload: Dict[str, Any], _: Dict[str, Any] = Depends(get_owner_full)) -> Dict[str, Any]:
    """
    payload: { "plan": "START|PRO|OWNER" }
    """
    from ..users import USERS
    load_users()
    u = USERS.get(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="user non trovato")
    new_plan = payload.get("plan")
    if not new_plan:
        raise HTTPException(status_code=422, detail="plan mancante")
    u["plan"] = new_plan
    save_users()
    return {"ok": True, "user": u}


@router.put("/users/{user_id}/status", summary="Change Status")
def admin_change_status(user_id: str, payload: Dict[str, Any], _: Dict[str, Any] = Depends(get_owner_full)) -> Dict[str, Any]:
    """
    payload: { "status": "ACTIVE|SUSPENDED" }
    """
    from ..users import USERS
    load_users()
    u = USERS.get(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="user non trovato")
    st = payload.get("status")
    if not st:
        raise HTTPException(status_code=422, detail="status mancante")
    u["status"] = st
    save_users()
    return {"ok": True, "user": u}
