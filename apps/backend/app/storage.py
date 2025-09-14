# app/storage.py
from typing import Dict, List
from .models import Book, Chapter
from uuid import uuid4

class MemoryStorage:
    def __init__(self):
        self.books: Dict[str, Book] = {}

    def list_books(self) -> List[Book]:
        return list(self.books.values())

    def get_book(self, book_id: str) -> Book | None:
        return self.books.get(book_id)

    def create_book(self, book: Book) -> Book:
        self.books[book.id] = book
        return book

    def delete_book(self, book_id: str) -> bool:
        return self.books.pop(book_id, None) is not None

    def add_chapter(self, book_id: str, ch: Chapter) -> Chapter:
        self.books[book_id].chapters.append(ch)
        return ch

store = MemoryStorage()

def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"
