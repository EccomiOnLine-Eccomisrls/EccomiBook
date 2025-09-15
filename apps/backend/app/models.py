from typing import Optional, List
from pydantic import BaseModel, Field


# ----- Libri & Capitoli -----

class ChapterCreate(BaseModel):
    title: str = Field(..., description="Titolo capitolo")
    prompt: str = Field(..., description="Testo/brief del capitolo")
    outline: Optional[str] = Field(None, description="Contenuto/outline del capitolo (facoltativo)")


class ChapterOut(BaseModel):
    id: str
    title: str
    prompt: str
    outline: str = ""


class BookCreate(BaseModel):
    title: str
    author: str
    language: str
    genre: str
    description: str = ""
    abstract: Optional[str] = Field(None, description="Abstract del libro (facoltativo)")
    plan: str = Field("owner_full", description="Piano/permessi (solo segnaposto)")


class BookOut(BaseModel):
    id: str
    title: str
    author: str
    language: str
    genre: str
    description: str = ""
    abstract: Optional[str] = None
    plan: str
    chapters: List[ChapterOut]


# ----- Generazione capitolo (mock) -----

class GenChapterIn(BaseModel):
    title: str
    prompt: Optional[str] = ""
    outline: Optional[str] = ""
    book_id: Optional[str] = None


class GenChapterOut(BaseModel):
    chapter_id: Optional[str]
    title: str
    content: str
