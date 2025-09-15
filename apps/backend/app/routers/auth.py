from fastapi import APIRouter, Header
from ..settings import get_settings

router = APIRouter()


@router.get("/health", include_in_schema=False)
def _health_alias():
    return {"ok": True}


@router.get("/root", include_in_schema=False)
def _root_alias():
    return {"ok": True}


@router.get("/_whoami", summary="Test Page")
def whoami(x_api_key: str | None = Header(default=None)):
    return {"x_api_key": x_api_key, "expected": get_settings().x_api_key}
