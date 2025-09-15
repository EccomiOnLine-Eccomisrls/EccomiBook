# apps/backend/app/storage.py
from __future__ import annotations
import json, os, tempfile, shutil, time
from typing import Dict, Any

DEFAULT_DIR = os.getenv("STORAGE_DIR", "/data/eccomibook")
STATE_FILE = "state.json"

def ensure_dirs() -> str:
    os.makedirs(DEFAULT_DIR, exist_ok=True)
    os.makedirs(os.path.join(DEFAULT_DIR, "exports"), exist_ok=True)
    return DEFAULT_DIR

def state_path() -> str:
    return os.path.join(DEFAULT_DIR, STATE_FILE)

def load_state() -> Dict[str, Any]:
    ensure_dirs()
    p = state_path()
    if not os.path.exists(p):
        return {"books": {}, "counters": {"books": 0, "chapters": 0}}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(data: Dict[str, Any]) -> None:
    ensure_dirs()
    p = state_path()
    d = os.path.dirname(p)
    os.makedirs(d, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile("w", delete=False, dir=d, encoding="utf-8")
    json.dump(data, tmp, ensure_ascii=False, indent=2)
    tmp.flush(); os.fsync(tmp.fileno()); tmp.close()
    shutil.move(tmp.name, p)

def new_book_id(counter: int | None = None) -> str:
    ts = int(time.time()) % 1000000
    if counter is None: counter = ts
    return f"book_{counter:06d}"

def new_chapter_id(counter: int | None = None) -> str:
    ts = int(time.time()) % 1000000
    if counter is None: counter = ts
    return f"ch_{counter:06d}"

def exports_dir() -> str:
    return os.path.join(DEFAULT_DIR, "exports")
