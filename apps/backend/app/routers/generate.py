# apps/backend/app/routers/generate.py
from __future__ import annotations
from fastapi import APIRouter, Body
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class GenIn(BaseModel):
    book_id: str
    chapter_id: str
    topic: str | None = None
    language: str = "it"

def generate_chapter_text(topic: str | None, language: str) -> str:
    # 🔧 Stub: genera un testo plausibile senza LLM
    t = topic.strip() if topic else "Capitolo"
    now = datetime.utcnow().isoformat() + "Z"
    if (language or "it").lower().startswith("it"):
        return (
            f"# {t}\n\n"
            f"Questo è un testo generato automaticamente ({now}).\n\n"
            f"1. Introduzione al tema\n"
            f"2. Sviluppo dei punti principali\n"
            f"3. Esempi pratici\n"
            f"4. Conclusione\n"
        )
    else:
        return (
            f"# {t}\n\n"
            f"This is an automatically generated chapter ({now}).\n\n"
            f"1. Introduction\n"
            f"2. Main topics\n"
            f"3. Practical examples\n"
            f"4. Conclusion\n"
        )

@router.post("/generate/chapter", tags=["generate"])
def generate_chapter(payload: GenIn = Body(...)):
    content = generate_chapter_text(payload.topic, payload.language)
    return {
        "ok": True,
        "book_id": payload.book_id,
        "chapter_id": payload.chapter_id,
        "content": content
    }
