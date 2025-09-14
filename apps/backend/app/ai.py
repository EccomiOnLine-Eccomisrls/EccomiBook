from typing import List
from textwrap import dedent

def generate_outline(title: str, chapters: int, language: str) -> List[str]:
    """Bozza finta ma carina; sostituiscila con il tuo LLM quando vuoi."""
    base = [
        "Introduzione",
        "Contesto e obiettivi",
        "I protagonisti",
        "Sfide iniziali",
        "Strategie e metodi",
        "Sviluppi e colpi di scena",
        "Approfondimenti",
        "Risultati e impatto",
        "Conclusioni",
        "Prossimi passi"
    ]
    if chapters <= len(base):
        return base[:chapters]
    # se vuoi più capitoli, duplica pattern
    extra = [f"Appendice {i}" for i in range(1, chapters - len(base) + 1)]
    return base + extra

def generate_chapter_md(title: str, prompt: str | None, language: str) -> str:
    p = prompt or ""
    return dedent(f"""
    **{title}**

    {("Istruzioni: " + p + "\\n\\n") if p else ""}Testo generato in stile narrativo.
    - Paragrafi ordinati
    - Qualche elenco puntato
    - Finale con take-away

    _Questo capitolo è un segnaposto: collega qui il tuo modello AI per contenuti reali._
    """).strip()

def generate_image_urls(n: int, hd: bool) -> List[str]:
    # placeholder (potrai sostituire con il tuo generatore immagini)
    quality = "hd" if hd else "base"
    return [f"https://placehold.co/800x500?text=img_{i+1}+{quality}" for i in range(max(0, n))]
