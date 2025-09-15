from pydantic import BaseModel
from typing import List, Optional


class ChapterCreate(BaseModel):
    title: str
    outline: str
    prompt: Optional[str] = None


class ChapterOut(ChapterCreate):
    id: str


class BookCreate(BaseModel):
    title: str
    author: Optional[str] = None
    language: Optional[str] = "it"
    genre: Optional[str] = None
    description: Optional[str] = None


class BookOut(BookCreate):
    id: str
    plan: str
    chapters: List[ChapterOut] = []
