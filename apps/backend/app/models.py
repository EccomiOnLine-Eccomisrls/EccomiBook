from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime

# ==== Domain ====

class Chapter(BaseModel):
    id: str
    index: int
    title: str
    content_md: str = ""        # markdown
    images: List[str] = []      # url o path locali
    created_at: datetime
    updated_at: datetime

class Book(BaseModel):
    id: str
    title: str
    genre: str = "General"
    language: str = "it"
    plan: Literal["owner_full", "pro", "growth", "start", "free"] = "owner_full"
    outline: List[str] = []     # titoli capitoli proposti
    chapters: List[Chapter] = []
    created_at: datetime
    updated_at: datetime

# ==== Requests / Responses ====

class CreateBookReq(BaseModel):
    title: str = Field(..., min_length=3)
    genre: str = "General"
    language: str = "it"
    plan: Optional[Literal["owner_full", "pro", "growth", "start", "free"]] = None

class GenerateOutlineReq(BaseModel):
    chapters: int = 10

class GenerateChapterReq(BaseModel):
    chapter_index: int
    prompt: Optional[str] = None
    hd_images: bool = False
    images: int = 0

class EditChapterReq(BaseModel):
    title: Optional[str] = None
    content_md: Optional[str] = None

class ExportReq(BaseModel):
    fmt: Literal["mdzip", "json"] = "mdzip"  # semplice: zip di markdown, oppure json grezzo

class BookList(BaseModel):
    items: List[Book]
