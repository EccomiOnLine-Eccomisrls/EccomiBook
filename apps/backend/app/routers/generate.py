# apps/backend/app/routers/generate.py
from __future__ import annotations

import os, json, re
from datetime import datetime
from typing import Iterator, List, Dict

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
    topic: str | None = None        # ← usato anche per capire se è "Indice"
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
# Riconoscimento Outline + Prompt Builder
# ─────────────────────────────────────────────────────────
_INDEX_TOKENS = ("indice", "sommario", "table of contents", "index")

def _is_outline_request(topic: str | None, chapter_id: str | None) -> bool:
    """
    Heuristics:
    - topic o chapter_id contengono parole chiave per 'Indice/Sommario'
    - override opzionale via env: FORCE_OUTLINE=true
    """
    if os.getenv("FORCE_OUTLINE", "").strip().lower() in ("1", "true", "yes"):
        return True
    t = (topic or "").lower()
    cid = (chapter_id or "").lower()
    if any(tok in t for tok in _INDEX_TOKENS):
        return True
    if any(tok in cid for tok in _INDEX_TOKENS):
        return True
    return False

def _build_outline_messages(language: str, topic: str) -> List[Dict[str, str]]:
    lang = (language or "it").lower()
    instruction = (
        "Sei uno strumento che genera esclusivamente INDICI/SCALLETTE numerate.\n"
        "REGOLE OBBLIGATORIE:\n"
        "1) Nessuna spiegazione, nessun testo discorsivo, nessun markdown, nessun grassetto.\n"
        "2) Un solo elemento per riga.\n"
        "3) Numerazione multilivello: 1, 1.1, 1.1.1 (max 3 livelli).\n"
        "4) Max 5 sezioni principali, ognuna con max 3 sottosezioni e max 3 sotto-sottosezioni.\n"
        "5) Lingua: {lang}.\n"
        "6) Se possibile, restituisci JSON conforme all'esempio:\n"
        '   {\"outline\":[{\"n\":\"1\",\"title\":\"Introduzione\",\"children\":[{\"n\":\"1.1\",\"title\":\"Contesto\"}]}]}\n'
        "7) Altrimenti restituisci testo semplice, una riga per elemento, es.: '1 Introduzione', '1.1 Contesto'."
    ).format(lang=lang)
    user = f"Crea l'indice/sommario per questo libro.\nTopic: {topic or 'N/A'}"
    return [
        {"role": "system", "content": instruction},
        {"role": "user", "content": user}
    ]

def _build_chapter_messages(language: str, topic: str, words: int, style: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": (
            f"Sei un assistente editoriale che scrive capitoli in {language}. "
            f"Stile: {style}. Sii chiaro, strutturato, usa markdown (titoli, liste, paragrafi). "
            f"Evita preamboli inutili. Output solo testo Markdown."
        )},
        {"role": "user", "content": (
            f"Scrivi un capitolo sul tema: '{topic}'. "
            f"Lunghezza circa {words} parole. Includi un titolo H1 e 3–6 sottosezioni con esempi pratici."
        )},
    ]

def _normalize_outline(text: str) -> str:
    """
    Accetta JSON o testo libero e restituisce una scaletta normalizzata:
    righe tipo '1 Introduzione', '1.1 Contesto', '1.1.1 Obiettivi'.
    """
    s = (text or "").strip()

    # 1) JSON strutturato
    try:
        data = json.loads(s)
        if isinstance(data, dict) and "outline" in data:
            lines: List[str] = []

            def walk(nodes, prefix=""):
                for i, node in enumerate(nodes, start=1):
                    n = node.get("n")
                    if not n:
                        n = f"{prefix}{i}" if not prefix else f"{prefix}.{i}"
                    title = (node.get("title") or "").strip()
                    if title:
                        lines.append(f"{n} {title}")
                    children = node.get("children") or []
                    if children:
                        for j, ch in enumerate(children, start=1):
                            ch_n = ch.get("n") or f"{n}.{j}"
                            ch_t = (ch.get("title") or "").strip()
                            if ch_t:
                                lines.append(f"{ch_n} {ch_t}")
                            gchildren = ch.get("children") or []
                            if gchildren:
                                for k, g in enumerate(gchildren, start=1):
                                    g_n = g.get("n") or f"{ch_n}.{k}"
                                    g_t = (g.get("title") or "").strip()
                                    if g_t:
                                        lines.append(f"{g_n} {g_t}")

            walk(data["outline"], "")
            return "\n".join(lines).strip()
    except Exception:
        pass

    # 2) Testo libero → pulizia
    s = re.sub(r'(^|\s)#{1,6}\s*', r'\1', s)  # rimuovi # markdown
    s = s.replace("**", "")
    # Spezza prima dei pattern numerati: 1. , 1.1 , ecc.
    s = re.sub(r'\s(?=\d+\.\d+\.\d+)', '\n', s)
    s = re.sub(r'\s(?=\d+\.\d+)', '\n', s)
    s = re.sub(r'(?<!\.)\s(?=\d+\.)', '\n', s)
    # Linee pulite
    s = re.sub(r'\n{2,}', '\n', s).strip()

    # Se non ci sono numeri, crea almeno una lista 1..N stimando separatori
    if not re.search(r'^\d+(\.\d+)*\s', s, flags=re.M):
        # Prova a dividere per punti elenco comuni
        parts = re.split(r'(?:\n|\s[-•–]\s|\s—\s)', s)
        parts = [p.strip(" -•–—\t\r") for p in parts if p.strip()]
        if parts:
            numbered = [f"{i}. {p}" for i, p in enumerate(parts, start=1)]
            s = "\n".join(numbered)

    return s

def _chat(client, model: str, messages: List[Dict[str, str]], temperature: float, max_tokens: int, stream: bool = False):
    if stream:
        return client.chat.completions.create(
            model=model, messages=messages, temperature=temperature, max_tokens=max_tokens, stream=True, timeout=60,
        )
    else:
        return client.chat.completions.create(
            model=model, messages=messages, temperature=temperature, max_tokens=max_tokens, timeout=60,
        )

# ─────────────────────────────────────────────────────────
# Endpoint NON-STREAM (compatibilità)
# ─────────────────────────────────────────────────────────
@router.post("/generate/chapter", tags=["generate"])
def generate_chapter(payload: GenIn = Body(...)):
    client, key, model, temperature, max_tokens = _client()

    topic = (payload.topic or "Introduzione").strip()
    language = (payload.language or "it").strip().lower()
    words = payload.words or 700
    style = (payload.style or "manuale/guida chiara").strip()

    is_outline = _is_outline_request(payload.topic, payload.chapter_id)

    if not key:
        # Fallback demo
        content = (
            ("1 Introduzione\n1.1 Contesto\n1.2 Obiettivi\n2 Capitolo di esempio\n")
            if is_outline else
            ("# Bozza automatica\n\n⚠️ OPENAI_API_KEY non configurata. Questo è un testo di esempio.\n\n"
             f"- book_id: {payload.book_id}\n- chapter_id: {payload.chapter_id}\n- topic: {topic}\n")
        )
        return {
            "ok": True,
            "model": "fallback",
            "content": content,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
    if client is None:
        raise HTTPException(status_code=500, detail="SDK OpenAI non disponibile nel runtime")

    try:
        if is_outline:
            messages = _build_outline_messages(language=language, topic=topic)
            resp = _chat(client, model, messages, temperature=0.1, max_tokens=max_tokens, stream=False)
            raw = (resp.choices[0].message.content or "").strip()
            content = _normalize_outline(raw)
        else:
            messages = _build_chapter_messages(language=language, topic=topic, words=words, style=style)
            resp = _chat(client, model, messages, temperature=temperature, max_tokens=max_tokens, stream=False)
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

    topic = (payload.topic or "Introduzione").strip()
    language = (payload.language or "it").strip().lower()
    words = payload.words or 700
    style = (payload.style or "manuale/guida chiara").strip()
    is_outline = _is_outline_request(payload.topic, payload.chapter_id)

    if not key:
        def fb() -> Iterator[bytes]:
            yield b""
            txt = ("1 Introduzione\n1.1 Contesto\n1.2 Obiettivi\n2 Sezione successiva\n"
                   if is_outline else
                   "# Bozza automatica\n\n⚠️ OPENAI_API_KEY non configurata. Questo è un testo di esempio.\n")
            yield txt.encode("utf-8")
        return StreamingResponse(
            fb(),
            media_type="text/plain; charset=utf-8",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    if client is None:
        raise HTTPException(status_code=500, detail="SDK OpenAI non disponibile nel runtime")

    def gen() -> Iterator[bytes]:
        try:
            yield b""
            if is_outline:
                messages = _build_outline_messages(language=language, topic=topic)
                stream = _chat(client, model, messages, temperature=0.1, max_tokens=max_tokens, stream=True)
                buffer = ""
                for chunk in stream:
                    part = chunk.choices[0].delta.content or ""
                    if part:
                        buffer += part
                        # Per lo stream, mandiamo linee “pulite” quando troviamo newline
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            yield (_normalize_outline(line) + "\n").encode("utf-8")
                if buffer.strip():
                    yield (_normalize_outline(buffer)).encode("utf-8")
            else:
                messages = _build_chapter_messages(language=language, topic=topic, words=words, style=style)
                stream = _chat(client, model, messages, temperature=temperature, max_tokens=max_tokens, stream=True)
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
    book_id: str = Query("", description="Facoltativo"),
    chapter_id: str = Query("", description="Facoltativo"),
    topic: str = Query("Introduzione"),
    language: str = Query("it"),
    style: str = Query("manuale/guida chiara"),
    words: int = Query(700),
):
    client, key, model, temperature, max_tokens = _client()
    is_outline = _is_outline_request(topic, chapter_id)

    def sse() -> Iterator[bytes]:
        # padding per sbloccare buffering (≈2KB)
        yield (":" + " " * 2048 + "\n").encode("utf-8")
        yield b":ok\n\n"

        # errori espliciti
        if not key:
            yield b"event: error\ndata: OPENAI_API_KEY mancante nel backend\n\n"
            yield b"event: done\ndata: 1\n\n"
            return
        if client is None:
            yield b"event: error\ndata: SDK OpenAI non disponibile nel runtime\n\n"
            yield b"event: done\ndata: 1\n\n"
            return

        try:
            if is_outline:
                messages = _build_outline_messages(language=language.strip().lower(),
                                                   topic=(topic or "Indice").strip())
                stream = _chat(client, model, messages, temperature=0.1,
                               max_tokens=max_tokens, stream=True)
            else:
                messages = _build_chapter_messages(language=language.strip().lower(),
                                                   topic=(topic or "Introduzione").strip(),
                                                   words=words, style=style)
                stream = _chat(client, model, messages, temperature=temperature,
                               max_tokens=max_tokens, stream=True)

            yield b"data: \n\n"  # micro-chunk iniziale
            buffer = ""
            for chunk in stream:
                part = chunk.choices[0].delta.content or ""
                if not part:
                    continue

                if is_outline:
                    buffer += part.replace("\r", "")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        clean = _normalize_outline(line)
                        if clean:
                            yield ("data: " + clean + "\n\n").encode("utf-8")
                else:
                    yield ("data: " + part.replace("\r", "") + "\n\n").encode("utf-8")

            if is_outline and buffer.strip():
                clean = _normalize_outline(buffer)
                if clean:
                    yield ("data: " + clean + "\n\n").encode("utf-8")

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
