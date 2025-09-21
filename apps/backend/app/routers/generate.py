from __future__ import annotations
from fastapi import APIRouter, Body
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/generate", tags=["generate"])

class GenIn(BaseModel):
    book_id: str
    chapter_id: str
    topic: str | None = None

@router.post("/chapter")
def generate_chapter(payload: GenIn = Body(...)):
    topic = payload.topic or "Capitolo"
    content = (
        f"# {topic}\n\n"
        f"Questo è un testo generato automaticamente ({datetime.utcnow().isoformat()}Z).\n\n"
        "1. Introduzione\n"
        "2. Sviluppo dei punti principali\n"
        "3. Esempi pratici\n"
        "4. Conclusione\n"
    )
    return {"ok": True, "content": content}
