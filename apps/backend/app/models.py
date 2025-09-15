from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class Plan(str, Enum):
    OWNER_FULL = "owner_full"
    PRO        = "pro"
    GROWTH     = "growth"
    START      = "start"

class ChapterCreate(BaseModel):
    title: str = Field(..., description="Titolo del capitolo")
    outline: str = Field("", description="Breve outline/indice del capitolo")
    prompt: str = Field(..., description="Prompt per la generazione del capitolo")

class ChapterOut(ChapterCreate):
    id: str

class BookCreate(BaseModel):
    title: str
    author: str = "Eccomi Online"
    language: str = "it"
    genre: str = "Saggio"
    description: str = ""

class BookOut(BookCreate):
    id: str
    plan: Plan
    chapters: List[ChapterOut] = []
