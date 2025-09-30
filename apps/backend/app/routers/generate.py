# apps/backend/app/routers/generate.py
from __future__ import annotations

import os
from datetime import datetime
from typing import Iterator

from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# SDK OpenAI (>= 1.0)
try:
    from openai import OpenAI
except Exception:  # libreria non presente o non importabile
    OpenAI = None

router = APIRouter()


# ─────────────────────────────────────────────────────────
# Modello input
# ─────────────────────────────────────────────────────────
class GenIn(BaseModel):
    book_id: str
    chapter_id: str
    topic: str | None = None
    language: str | None = "it"
    style: str | None = "manuale/guida chiara"
    words: int | None = 700


# ─────────────────────────────────────────────────────────
# Util env
# ─────────────────────────────────────────────────────────
def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "").strip() or default)
    except Exception:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except Exception:
        return default


def _client():
    """
    Ritorna (client, api_key, model, temperature, max_tokens).
    Se la chiave manca o la libreria non è disponibile, client = None.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip() or "gpt-4o-mini"
    temperature = _env_float("AI_TEMPERATURE", 0.7)
    max_tokens = _env_int("AI_MAX_TOKENS", 1200)

    if not api_key or OpenAI is None:
        return None, api_key, model, temperature, max_tokens
    return OpenAI(api_key=api_key), api_key, model, temperature, max_tokens


# ─────────────────────────────────────────────────────────
# Endpoint NON-STREAM (compatibilità)
# ─────────────────────────────────────────────────────────
@router.post("/generate/chapter", tags=["generate"])
def generate_chapter(payload: GenIn = Body(...)):
    """
    Genera il contenuto di un capitolo con OpenAI **senza** salvarlo su disco.
    Il frontend, dopo aver ricevuto `content`, effettua il PUT su:
      /books/{book_id}/chapters/{chapter_id}
    """
    client, key, model, temperature, max_tokens = _client()

    # Fallback se chiave mancante o SDK indisponibile
    if not key:
        content = (
            "# Bozza automatica\n\n"
            "⚠️ OPENAI_API_KEY non configurata. Questo è un testo di esempio.\n\n"
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
    if client is None:
        raise HTTPException(status_code=500, detail="SDK OpenAI non disponibile nel runtime")

    # Prompt
    topic = (payload.topic or "Introduzione").strip()
    language = (payload.language or "it").strip().lower()
    words = payload.words or 700
    style = (payload.style or "manuale/guida chiara").strip()

    system_msg = (
        f"Sei un assistente editoriale che scrive capitoli in {language}. "
        f"Stile: {style}. Sii chiaro, strutturato, usa markdown (titoli, liste, paragrafi). "
        f"Evita preamboli inutili. Output **solo** testo Markdown."
    )
    user_msg = (
        f"Scrivi un capitolo sul tema: '{topic}'. "
        f"Lunghezza circa {words} parole. Includi un titolo H1 e 3–6 sottosezioni con esempi pratici."
    )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=temperature,
            max_tokens=max_tokens,  # limite di uscita
            timeout=60,             # evita call appese
        )

        # Estrai contenuto
        content = (resp.choices[0].message.content or "").strip()
        if not content:
            raise RuntimeError("Risposta vuota dal modello")

        return {
            "ok": True,
            "model": getattr(resp, "model", model),
            "content": content,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Errore AI: {e}")


# ─────────────────────────────────────────────────────────
# Endpoint STREAMING (effetto “ChatGPT”)
# ─────────────────────────────────────────────────────────
@router.post("/generate/chapter/stream", tags=["generate"])
def generate_chapter_stream(payload: GenIn = Body(...)):
    """
    Restituisce il capitolo in streaming testuale (text/plain), chunk per chunk.
    """
    client, key, model, temperature, max_tokens = _client()

    # Fallback streaming se manca la chiave (manteniamo la UX coerente)
    if not key:
        def fb() -> Iterator[bytes]:
            txt = (
                "# Bozza automatica\n\n"
                "⚠️ OPENAI_API_KEY non configurata. Questo è un testo di esempio.\n\n"
                f"- book_id: {payload.book_id}\n"
                f"- chapter_id: {payload.chapter_id}\n"
                f"- topic: {payload.topic or '—'}\n"
            )
            yield txt.encode("utf-8")
        return StreamingResponse(
    fb(),
    media_type="text/plain; charset=utf-8",
    headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    },
)

    if client is None:
        raise HTTPException(status_code=500, detail="SDK OpenAI non disponibile nel runtime")

    # Prompt
    topic = (payload.topic or "Introduzione").strip()
    language = (payload.language or "it").strip().lower()
    words = payload.words or 700
    style = (payload.style or "manuale/guida chiara").strip()

    system_msg = (
        f"Sei un assistente editoriale che scrive capitoli in {language}. "
        f"Stile: {style}. Sii chiaro, strutturato, usa markdown (titoli, liste, paragrafi). "
        f"Evita preamboli inutili. Output **solo** testo Markdown."
    )
    user_msg = (
        f"Scrivi un capitolo sul tema: '{topic}'. "
        f"Lunghezza circa {words} parole. Includi un titolo H1 e 3–6 sottosezioni con esempi pratici."
    )

    def gen() -> Iterator[bytes]:
        try:
            stream = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,   # ⬅️ attiva streaming OpenAI
                timeout=60,
            )
            for chunk in stream:
                part = chunk.choices[0].delta.content or ""
                if part:
                    yield part.encode("utf-8")
        except Exception as e:
            # scrivo l’errore dentro lo stream per mostrarlo in textarea
            yield f"\n\n**[Errore AI: {e}]**".encode("utf-8")

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")
