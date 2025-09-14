# app/models.py
from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Plan(str, Enum):
    OWNER_FULL = "owner_full"
    PRO        = "pro"
    GROWTH     = "growth"
    START      = "start"

PLAN_CAPS = {
    Plan.OWNER_FULL: dict(max_books=None, max_chapters_per_day=None, images_hd=True,  export_hd=True,  priority="highest"),
    Plan.PRO:        dict(max_books=None, max_chapters_per_day=200,  images_hd=True,  export_hd=True,  priority="high"),
    Plan.GROWTH:     dict(max_books=20,   max_chapters_per_day=50,   images_hd=True,  export_hd=True,  priority="high"),
    Plan.START:      dict(max_books=3,    max_chapters_per_day=10,   images_hd=False, export_hd=False, priority="normal"),
}

class Chapter(BaseModel):
    id: str
    title: str
    text: str
    image_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Book(BaseModel):
    id: str
    title: str
    synopsis: Optional[str] = ""
    genre: Optional[str] = "general"
    language: str = "it"
    plan: Plan = Plan.OWNER_FULL
    chapters: List[Chapter] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CreateBookInput(BaseModel):
    title: str
    synopsis: Optional[str] = ""
    genre: Optional[str] = "general"
    language: str = "it"

class GenerateChapterInput(BaseModel):
    title_hint: Optional[str] = None
    words: int = 600
    want_image: bool = True

class ExportFormat(str, Enum):
    ZIP_MARKDOWN = "zip_markdown"
