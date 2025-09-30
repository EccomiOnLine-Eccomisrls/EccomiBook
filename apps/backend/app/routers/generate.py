# apps/backend/app/routers/generate.py
from __future__ import annotations

import os
from datetime import datetime
from typing import Iterator

from fastapi import APIRouter, HTTPException, Body, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from time import sleep

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
    client, key, model, temperature, max_tokens = _client()

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
            max_tokens=max_tokens,
            timeout=60,
        )
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
# Endpoint STREAMING (text/plain)
# ─────────────────────────────────────────────────────────
@router.post("/generate/chapter/stream", tags=["generate"])
def generate_chapter_stream(payload: GenIn = Body(...)):
    client, key, model, temperature, max_tokens = _client()

    if not key:
        def fb() -> Iterator[bytes]:
            yield b""  # micro-chunk per sbloccare proxy/mobile
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
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    if client is None:
        raise HTTPException(status_code=500, detail="SDK OpenAI non disponibile nel runtime")

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
            yield b""  # micro-chunk iniziale
            stream = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                timeout=60,
            )
            for chunk in stream:
                part = chunk.choices[0].delta.content or ""
                if part:
                    yield part.encode("utf-8")
        except Exception as e:
            yield f"\n\n**[Errore AI: {e}]**".encode("utf-8")

    return StreamingResponse(
        gen(),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

# ─────────────────────────────────────────────────────────
# Endpoint SSE (Server-Sent Events) — stabile su Safari/iPad
# ─────────────────────────────────────────────────────────
@router.get("/generate/chapter/sse", tags=["generate"])
def generate_chapter_sse(
    book_id: str = Query(...),
    chapter_id: str = Query(...),
    topic: str = Query("Introduzione"),
    language: str = Query("it"),
    style: str = Query("manuale/guida chiara"),
    words: int = Query(700),
):
    client, key, model, temperature, max_tokens = _client()

    system_msg = (
        f"Sei un assistente editoriale che scrive capitoli in {language.strip().lower()}. "
        f"Stile: {style}. Sii chiaro, strutturato, usa markdown (titoli, liste, paragrafi). "
        f"Evita preamboli inutili. Output **solo** testo Markdown."
    )
    user_msg = (
        f"Scrivi un capitolo sul tema: '{(topic or 'Introduzione').strip()}'. "
        f"Lunghezza circa {words} parole. Includi un titolo H1 e 3–6 sottosezioni con esempi pratici."
    )

    def sse() -> Iterator[bytes]:
        # padding per sbloccare buffering (≈2KB)
        yield (":" + " " * 2048 + "\n").encode("utf-8")
        yield b":ok\n\n"

        if not key:
            demo = (
                "# Bozza automatica\n\n"
                "⚠️ OPENAI_API_KEY non configurata. Questo è un testo di esempio.\n\n"
                f"- book_id: {book_id}\n"
                f"- chapter_id: {chapter_id}\n"
                f"- topic: {topic or '—'}\n"
            )
            for chunk in demo.split():
                yield f"data: {chunk} ".encode("utf-8") + b"\n\n"
                sleep(0.01)
            yield b"event: done\ndata: 1\n\n"
            return

        if client is None:
            yield b"event: error\ndata: SDK OpenAI non disponibile\n\n"
            yield b"event: done\ndata: 1\n\n"
            return

        try:
            stream = client.chat_completions.create(  # se usi openai>=1.40: client.chat.completions.create
                model=model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                timeout=60,
            )
            yield b"data: \n\n"  # micro-chunk iniziale
            for chunk in stream:
                part = chunk.choices[0].delta.content or ""
                if part:
                    yield ("data: " + part.replace("\r", "") + "\n\n").encode("utf-8")
            yield b"event: done\ndata: 1\n\n"
        except Exception as e:
            yield ("event: error\ndata: " + str(e) + "\n\n").encode("utf-8")
            yield b"event: done\ndata: 1\n\n"

    return StreamingResponse(
        sse(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Content-Encoding": "identity",
        },
    )
