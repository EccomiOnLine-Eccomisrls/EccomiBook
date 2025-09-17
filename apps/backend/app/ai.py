from __future__ import annotations
from typing import Optional, Dict, Any

from .settings import get_settings                    # stesso package (app)
from .plans import PLANS, normalize_plan            

try:
    from openai import OpenAI  # openai>=1.0
except Exception:
    OpenAI = None  # libreria non installata: useremo fallback


SYSTEM_PROMPT_IT = (
    "Sei un autore professionista. Scrivi in italiano, tono chiaro e coinvolgente, "
    "con ritmo narrativo e coesione. Evita elenchi puntati, preferisci paragrafi. "
    "Usa transizioni naturali e dettagli sensoriali quando opportuno. "
    "Non fare meta-commenti (non dire che stai generando un testo)."
)

def _length_instruction(target_words: int) -> str:
    low = max(350, int(target_words * 0.8))
    high = int(target_words * 1.1)
    return (
        f"OBIETTIVO LUNGHEZZA: scrivi tra {low} e {high} parole, con inizio accattivante, "
        f"sviluppo coerente e piccolo gancio finale. Non inserire titoli nel corpo; no bullet point."
    )

def _build_user_prompt(title: str, prompt: str, outline: str, target_words: int) -> str:
    parts = [f"TITOLO CAPITOLO: {title}"]
    if prompt:
        parts.append(f"BRIEF: {prompt}")
    if outline:
        parts.append("OUTLINE (indice sintetico):\n" + outline)
    parts.append(_length_instruction(target_words))
    return "\n\n".join(parts)

def _profile_from_plan(plan: Optional[str]) -> Dict[str, Any]:
    """
    Profilo AI derivato dal piano (plans.py), con possibili override da settings:
    - model (override con OPENAI_MODEL)
    - max_tokens (override con AI_MAX_TOKENS)
    - temperature (override con AI_TEMPERATURE)
    - target_words (solo dal piano)
    """
    s = get_settings()
    canonical = normalize_plan(plan)
    rules = PLANS[canonical]
    profile = {
        "model": rules.model,
        "max_tokens": rules.max_tokens,
        "temperature": rules.temperature,
        "target_words": rules.target_words,
    }
    # override opzionali via ENV
    if getattr(s, "openai_model", None):
        profile["model"] = s.openai_model
    if getattr(s, "ai_max_tokens", None):
        profile["max_tokens"] = s.ai_max_tokens
    if getattr(s, "ai_temperature", None) is not None:
        profile["temperature"] = s.ai_temperature
    return profile

def generate_chapter_text(
    *,
    title: str,
    prompt: str = "",
    outline: str = "",
    plan: Optional[str] = None,
) -> str:
    """
    Genera testo narrativo del capitolo, agganciando automaticamente il MODELLO dal PIANO.
    Se OpenAI non è configurato o c’è un errore, usa un fallback dignitoso.
    """
    s = get_settings()
    profile = _profile_from_plan(plan)
    target_words = int(profile["target_words"])

    # Usa OpenAI se disponibile
    if OpenAI and s.openai_api_key:
        client = OpenAI(api_key=s.openai_api_key)
        user_prompt = _build_user_prompt(title, prompt, outline, target_words)
        try:
            resp = client.chat.completions.create(
                model=profile["model"],
                temperature=float(profile["temperature"]),
                max_tokens=int(profile["max_tokens"]),
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_IT},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=60,
            )
            content = (resp.choices[0].message.content or "").strip()
            if content:
                return content
        except Exception as e:
            print(f"[AI] OpenAI error: {e!r} — uso fallback (plan={normalize_plan(plan)})")

    # Fallback locale se manca la chiave o c’è un errore
    scaffold = (outline or prompt or "").strip() or "Il capitolo presenta il protagonista e l'inizio del suo viaggio."
    return (
        f"«{title}»\n\n"
        "Questo capitolo sviluppa i temi richiesti partendo dallo schema seguente:\n"
        f"{scaffold}\n\n"
        "(Fallback locale: configura OPENAI_API_KEY per la generazione completa.)\n\n"
        "Il protagonista muove i primi passi in un mondo che lo sfida e lo attrae. "
        "Le sue esitazioni si intrecciano con la curiosità, mentre il paesaggio intorno "
        "cambia lentamente, rivelando dettagli e presagi. In assenza di motore creativo esterno, "
        "questo paragrafo funge da segnaposto narrativo, pronto a essere sostituito "
        "dalla generazione AI appena configurata."
    )
