from typing import Optional, List
from pydantic import BaseModel, Field

# ============================================================
#                    Libri & Capitoli
# ============================================================

class ChapterCreate(BaseModel):
    title: str = Field(
        ...,
        description="Titolo del capitolo",
        example="Capitolo 1: L’inizio"
    )
    prompt: str = Field(
        ...,
        description="Brief/testo guida per generare il capitolo",
        example="Presenta il protagonista e il contesto della storia."
    )
    outline: Optional[str] = Field(
        None,
        description="Outline/struttura del capitolo (facoltativa)",
        example="1) Introduzione 2) Incontro 3) Conflitto 4) Cliffhanger"
    )

    class Config:
        schema_extra = {
            "example": {
                "title": "Capitolo 1: L’inizio",
                "prompt": "Presenta il protagonista e il contesto della storia.",
                "outline": "1) Introduzione\n2) Incontro\n3) Conflitto\n4) Cliffhanger"
            }
        }


class ChapterOut(BaseModel):
    id: str = Field(
        ...,
        description="ID univoco del capitolo",
        example="ch_123456"
    )
    title: str = Field(
        ...,
        description="Titolo del capitolo",
        example="Capitolo 1: L’inizio"
    )
    prompt: str = Field(
        ...,
        description="Brief originario del capitolo",
        example="Presenta il protagonista e il contesto della storia."
    )
    outline: str = Field(
        default="",
        description="Outline/struttura consolidata del capitolo (se presente)",
        example="1) Introduzione 2) Incontro 3) Conflitto 4) Cliffhanger"
    )

    class Config:
        schema_extra = {
            "example": {
                "id": "ch_123456",
                "title": "Capitolo 1: L’inizio",
                "prompt": "Presenta il protagonista e il contesto della storia.",
                "outline": "1) Introduzione 2) Incontro 3) Conflitto 4) Cliffhanger"
            }
        }


class BookCreate(BaseModel):
    title: str = Field(
        ...,
        description="Titolo del libro",
        example="Il Viaggio di Aria"
    )
    author: str = Field(
        ...,
        description="Autore del libro",
        example="EccomiBook AI"
    )
    language: str = Field(
        ...,
        description="Lingua principale del libro",
        example="it"
    )
    genre: str = Field(
        ...,
        description="Genere letterario",
        example="Fantasy"
    )
    description: str = Field(
        "",
        description="Descrizione estesa del libro",
        example="Un’epopea fantastica tra regni e magie."
    )
    abstract: Optional[str] = Field(
        None,
        description="Abstract/riassunto breve del libro (facoltativo)",
        example="Aria scopre un potere antico e parte per un viaggio."
    )
    plan: str = Field(
        "owner_full",
        description="Piano/permessi (placeholder)",
        example="owner_full"
    )

    class Config:
        schema_extra = {
            "example": {
                "title": "Il Viaggio di Aria",
                "author": "EccomiBook AI",
                "language": "it",
                "genre": "Fantasy",
                "description": "Un’epopea fantastica tra regni e magie.",
                "abstract": "Aria scopre un potere antico e parte per un viaggio.",
                "plan": "owner_full"
            }
        }


class BookOut(BaseModel):
    id: str = Field(
        ...,
        description="ID univoco del libro",
        example="bk_987654"
    )
    title: str = Field(
        ...,
        description="Titolo del libro",
        example="Il Viaggio di Aria"
    )
    author: str = Field(
        ...,
        description="Autore del libro",
        example="EccomiBook AI"
    )
    language: str = Field(
        ...,
        description="Lingua principale del libro",
        example="it"
    )
    genre: str = Field(
        ...,
        description="Genere letterario",
        example="Fantasy"
    )
    description: str = Field(
        "",
        description="Descrizione estesa del libro",
        example="Un’epopea fantastica tra regni e magie."
    )
    abstract: Optional[str] = Field(
        None,
        description="Abstract/riassunto breve del libro (se impostato)",
        example="Aria scopre un potere antico e parte per un viaggio."
    )
    plan: str = Field(
        ...,
        description="Piano/permessi (placeholder)",
        example="owner_full"
    )
    chapters: List['ChapterOut'] = Field(
        ...,
        description="Elenco capitoli del libro"
    )

    class Config:
        schema_extra = {
            "example": {
                "id": "bk_987654",
                "title": "Il Viaggio di Aria",
                "author": "EccomiBook AI",
                "language": "it",
                "genre": "Fantasy",
                "description": "Un’epopea fantastica tra regni e magie.",
                "abstract": "Aria scopre un potere antico e parte per un viaggio.",
                "plan": "owner_full",
                "chapters": [
                    {
                        "id": "ch_123456",
                        "title": "Capitolo 1: L’inizio",
                        "prompt": "Presenta il protagonista e il contesto della storia.",
                        "outline": "1) Introduzione 2) Incontro 3) Conflitto 4) Cliffhanger"
                    }
                ]
            }
        }


# ============================================================
#              Generazione capitolo (API generate)
# ============================================================

# Request: con esempio completo precompilato
class GenChapterIn(BaseModel):
    title: str = Field(
        ...,
        description="Titolo del capitolo da generare",
        example="Capitolo 1: L’inizio"
    )
    prompt: Optional[str] = Field(
        "",
        description="Brief per guidare la generazione del capitolo",
        example="Racconta l’incipit della storia in tono avventuroso."
    )
    outline: Optional[str] = Field(
        "",
        description="Outline opzionale del capitolo",
        example="1) Scena iniziale\n2) Piccolo conflitto\n3) Hook finale"
    )
    book_id: Optional[str] = Field(
        None,
        description="ID del libro a cui associare il capitolo (se esiste)",
        example="bk_987654"
    )
    abstract: Optional[str] = Field(
        None,
        description="Riassunto breve del capitolo (facoltativo)",
        example="Il protagonista sente la chiamata all’avventura."
    )
    page_numbers: bool = Field(
        default=True,
        description="Se True, il PDF generato includerà la numerazione delle pagine",
        example=True
    )

    class Config:
        schema_extra = {
            "example": {
                "title": "Capitolo 1: L’inizio",
                "prompt": "Racconta l’incipit della storia in tono avventuroso.",
                "outline": "1) Scena iniziale\n2) Piccolo conflitto\n3) Hook finale",
                "book_id": "bk_987654",
                "abstract": "Il protagonista sente la chiamata all’avventura.",
                "page_numbers": True
            }
        }


# Response: include pdf_url + esempio completo (cliccabile)
class GenChapterOut(BaseModel):
    chapter_id: Optional[str] = Field(
        None,
        description="ID del capitolo generato",
        example="ch_12345678"
    )
    title: str = Field(
        ...,
        description="Titolo del capitolo",
        example="Capitolo 1: L’inizio"
    )
    content: str = Field(
        ...,
        description="Contenuto testuale generato del capitolo",
        example="C’era una volta..."
    )
    abstract: Optional[str] = Field(
        None,
        description="Riassunto breve del capitolo",
        example="Il protagonista sente la chiamata all’avventura."
    )
    page_numbers: bool = Field(
        ...,
        description="Indica se il PDF generato include la numerazione delle pagine",
        example=True
    )
    pdf_url: Optional[str] = Field(
        None,
        description="URL del PDF generato",
        example="https://eccomibook-backend.onrender.com/static/chapters/ch_12345678.pdf"
    )

    class Config:
        schema_extra = {
            "example": {
                "chapter_id": "ch_12345678",
                "title": "Capitolo 1: L’inizio",
                "content": "C’era una volta...",
                "abstract": "Il protagonista sente la chiamata all’avventura.",
                "page_numbers": True,
                "pdf_url": "https://eccomibook-backend.onrender.com/static/chapters/ch_12345678.pdf"
            }
        }
