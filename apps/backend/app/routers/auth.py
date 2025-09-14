# app/routers/auth.py
from fastapi import Depends, Header
from ..settings import settings
from ..models import Plan

class UserCtx:
    def __init__(self, plan: Plan):
        self.plan = plan

def get_current_user(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> UserCtx:
    if x_api_key and x_api_key == settings.OWNER_API_KEY:
        return UserCtx(plan=Plan.OWNER_FULL)
    return UserCtx(plan=Plan.START)
