# apps/backend/app/routers/generate.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from datetime import datetime
import os
import math

# SDK OpenAI (>= 1.x)
try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # gestito sotto

router = APIRouter()

# ─────────────────────────────────────────────────────────
# Input
# ─────────────────────────────────────────────────────────
class GenIn(BaseModel):
    book_id: str
    chapter_id: str
    topic: str | None = None
    language: str | None = "it"
    style: str | None = "manuale/guida chiara"
    words: int | None = 700

# ─────────────────────────────────────────────────────────
# Utils
# ─────────────────────────────────────────────────────────
def _settings():
    """Legge ENV con default sensati."""
    return {
        "api_key": os.getenv("OPENAI_API_KEY", "").strip(),
        "model": (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip(),
        "temperature": float(os.getenv("AI_TEMPERATURE", "0.7")),
        # max_tokens è un limite “duro”; per sicurezza convertiamo ~parole→tokens
        "max_tokens": int(os.getenv("AI_MAX_TOKENS", "1200")),
        "allow_open_api": os.getenv("ALLOW_OPEN_API", "1").strip() not in ("0", "false", "False"),
    }

def _client_or_none(api_key: str):
    if not api_key or OpenAI is None:
        return None
    return OpenAI(api_key=api_key)

def _fallback(payload: GenIn) -> dict:
    content = (
        "# Bozza automatica\n\n"
        "⚠️ OPENAI disabilitata o chiave mancante. Testo di esempio.\n\n"
        f"- book_id: {payload.book_id}\n"
        f"- chapter_id: {payload.chapter_id}\n"
        f"- topic: {payload.topic or '—'}\n"
    )
    return {
        "ok": True,
        "model": "fallback",
        "content": content,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

# ─────────────────────────────────────────────────────────
# Endpoint
# ─────────────────────────────────────────────────────────
@router.post("/generate/chapter", tags=["generate"])
def generate_chapter(payload: GenIn = Body(...)):
    """
    Genera il contenuto del capitolo. **Non** salva su disco: il frontend fa
    subito dopo PUT /books/{book_id}/chapters/{chapter_id} per la persistenza.
    """
    cfg = _settings()

    if not cfg["allow_open_api"]:
        return _fallback(payload)

    client = _client_or_none(cfg["api_key"])
    if client is None:
        return _fallback(payload)

    topic = (payload.topic or "Introduzione").strip()
    language = (payload.language or "it").strip().lower()
    words = int(payload.words or 700)
    words = max(150, min(words, 2000))  # guardrail
    # stima molto grossolana: 1 parola ≈ 1.3 token
    max_tokens = max(256, min(cfg["max_tokens"], math.ceil(words * 1.3)))

    system_msg = (
        f"Sei un assistente editoriale che scrive capitoli in {language}. "
        f"Stile: {payload.style or 'manuale/guida chiara'}. "
        "Usa un tono pratico e chiaro. "
        "Struttura in markdown: titolo H1, 3–6 sottosezioni con H2/H3, "
        "liste puntate dove utile, esempi. Non includere disclaimer."
    )
    user_msg = (
        f"Scrivi un capitolo sul tema: «{topic}».\n"
        f"Lunghezza ~{words} parole. Markdown puro (niente HTML)."
    )

    try:
        resp = client.chat.completions.create(
            model=cfg["model"],
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=cfg["temperature"],
            max_tokens=max_tokens,
        )
        content = (resp.choices[0].message.content or "").strip()
        if not content:
            raise RuntimeError("Risposta vuota dal modello")

        return {
            "ok": True,
            "model": resp.model,
            "content": content,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "meta": {"temperature": cfg["temperature"], "max_tokens": max_tokens},
        }
    except Exception as e:
        # in caso di errore rete/modello, diamo fallback “gentile”
        raise HTTPException(status_code=502, detail=f"Errore AI: {e}")
