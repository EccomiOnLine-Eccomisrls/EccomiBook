from enum import Enum

class Plan(str, Enum):
    OWNER_FULL = "owner_full"
    START      = "start"
    GROWTH     = "growth"
    PRO        = "pro"

PLAN_CAPS = {
    Plan.OWNER_FULL: dict(
        max_books_per_month=None,     # illimitati
        max_chapters_per_day=None,    # illimitati
        images_hd=True,
        export_pdf=True, export_epub=True, export_docx=True,
        priority="highest",
    ),
    Plan.START: dict(
        max_books_per_month=1,
        max_chapters_per_day=10,
        images_hd=False,
        export_pdf=True, export_epub=False, export_docx=False,
        priority="normal",
    ),
    Plan.GROWTH: dict(
        max_books_per_month=5,
        max_chapters_per_day=50,
        images_hd=True,
        export_pdf=True, export_epub=True, export_docx=False,
        priority="high",
    ),
    Plan.PRO: dict(
        max_books_per_month=None,     # “Illimitati”
        max_chapters_per_day=200,
        images_hd=True,
        export_pdf=True, export_epub=True, export_docx=True,
        priority="max",
    ),
}
