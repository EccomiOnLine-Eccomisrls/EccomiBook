# apps/backend/plans.py
from dataclasses import dataclass
from typing import Optional, Dict

@dataclass(frozen=True)
class PlanRules:
    name: str
    model: str
    max_tokens: int
    temperature: float
    target_words: int
    allow_export_book: bool
    monthly_chapter_quota: Optional[int]  # None = illimitato

# MAPPING UFFICIALE DEI PIANI
PLANS: Dict[str, PlanRules] = {
    # START → gpt-3.5-turbo
    "START": PlanRules(
        name="START",
        model="gpt-3.5-turbo",
        max_tokens=700,
        temperature=0.7,
        target_words=450,
        allow_export_book=True,
        monthly_chapter_quota=50,
    ),
    # GROWTH → gpt-4o-mini
    "GROWTH": PlanRules(
        name="GROWTH",
        model="gpt-4o-mini",
        max_tokens=1200,
        temperature=0.8,
        target_words=900,
        allow_export_book=True,
        monthly_chapter_quota=200,
    ),
    # PRO → gpt-4o
    "PRO": PlanRules(
        name="PRO",
        model="gpt-4o",
        max_tokens=1600,
        temperature=0.9,
        target_words=1200,
        allow_export_book=True,
        monthly_chapter_quota=1000,
    ),
    # OWNER_FULL → gpt-4.1
    "OWNER_FULL": PlanRules(
        name="OWNER_FULL",
        model="gpt-4.1",
        max_tokens=2000,
        temperature=0.95,
        target_words=1400,
        allow_export_book=True,
        monthly_chapter_quota=None,
    ),
}

# Alias (case-insensitive) per sicurezza / retrocompatibilità
PLAN_ALIASES = {
    "free": "START",
    "start": "START",
    "growth": "GROWTH",
    "intermedio": "GROWTH",
    "pro": "PRO",
    "max": "PRO",
    "owner_full": "OWNER_FULL",
    "ownerfull": "OWNER_FULL",
    "owner-full": "OWNER_FULL",
}

ACTIVE_STATUSES = {"active", "trialing"}
BLOCKED_STATUSES = {"past_due", "canceled"}

def normalize_plan(plan: Optional[str]) -> str:
    if not plan:
        return "START"
    up = plan.strip().upper()
    if up in PLANS:
        return up
    low = plan.strip().lower()
    return PLAN_ALIASES.get(low, "START")
