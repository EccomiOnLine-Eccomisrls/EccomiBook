from pydantic import BaseModel, Field
from typing import Literal, Optional


Plan = Literal["start", "growth", "pro", "owner_full"]


class BookCreate(BaseModel):
    title: str
    author: str
    language: str
    genre: str
    description: str = ""
    plan: Plan = "owner_full"


class ChapterCreate(BaseModel):
    title: str
    prompt: str
    outline: Optional[str] = None


class BookOut(BaseModel):
    id: str
    title: str
    author: str
    language: str
    genre: str
    description: str = ""
    plan: Plan = "owner_full"
    chapters: list["ChapterOut"] = []


class ChapterOut(BaseModel):
    id: str
    title: str
    prompt: str | None = None
    outline: str | None = None


class GenChapterIn(BaseModel):
    title: str = Field(..., description="Titolo del capitolo")
    prompt: str | None = Field(default=None, description="Prompt testuale")
    outline: str | None = Field(default=None, description="Outline riassuntiva")
    book_id: str | None = Field(default=None, description="Se presente, aggiunge il capitolo al libro")


class GenChapterOut(BaseModel):
    chapter_id: str | None
    title: str
    content: str
