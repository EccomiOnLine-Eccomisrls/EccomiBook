from datetime import date
from collections import defaultdict

# user -> (yyyymm -> n_books)
_books_month_counter = defaultdict(int)
_books_month_bucket  = defaultdict(lambda: date.today().strftime("%Y%m"))

# user -> (yyyymmdd -> n_chapters)
_chapters_day_counter = defaultdict(int)
_chapters_day_bucket  = defaultdict(lambda: date.today().strftime("%Y%m%d"))

def inc_book(user_id: str) -> int:
    key_bucket = _books_month_bucket[user_id]
    today_bucket = date.today().strftime("%Y%m")
    if key_bucket != today_bucket:
        _books_month_bucket[user_id] = today_bucket
        _books_month_counter[user_id] = 0
    _books_month_counter[user_id] += 1
    return _books_month_counter[user_id]

def get_books_this_month(user_id: str) -> int:
    key_bucket = _books_month_bucket[user_id]
    if key_bucket != date.today().strftime("%Y%m"):
        return 0
    return _books_month_counter[user_id]

def inc_chapter(user_id: str) -> int:
    key_bucket = _chapters_day_bucket[user_id]
    today_bucket = date.today().strftime("%Y%m%d")
    if key_bucket != today_bucket:
        _chapters_day_bucket[user_id] = today_bucket
        _chapters_day_counter[user_id] = 0
    _chapters_day_counter[user_id] += 1
    return _chapters_day_counter[user_id]

def get_chapters_today(user_id: str) -> int:
    key_bucket = _chapters_day_bucket[user_id]
    if key_bucket != date.today().strftime("%Y%m%d"):
        return 0
    return _chapters_day_counter[user_id]
