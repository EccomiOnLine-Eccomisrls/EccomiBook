# app/ai.py
from .models import Chapter
from .storage import new_id

BLURB = ("In questo capitolo esploriamo l'idea principale con esempi concreti. "
         "Tono chiaro e scorrevole, utile per il lettore. ")

def generate_chapter(title_hint: str | None, words: int = 600, want_image: bool = True) -> Chapter:
    title = title_hint or "Capitolo"
    text = (f"# {title}\n\n" + BLURB) * max(1, words // 80)
    image_url = "https://picsum.photos/seed/eccomibook/1024/640" if want_image else None
    return Chapter(id=new_id("ch"), title=title, text=text, image_url=image_url)
