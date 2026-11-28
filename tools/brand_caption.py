"""Make every caption searchable as Travis Dixon Coaching, and keep dashes out.

Facebook and Instagram Reels search match on caption text and hashtags, not on
the page name, so each post opens with the full brand phrase and carries a few
hashtags only Travis uses. Applied after generation so the model cannot drift.
"""
from __future__ import annotations

import re

BRAND_LINE = "Travis Dixon Coaching | Relationship coach"
BRAND_TAGS = ("#TravisDixonCoaching", "#CoachTee", "#TrainedPartner", "#RelationshipCoach", "#CharlotteNC")

_DASH_RE = re.compile(r"\s*[—–]\s*|\s+-\s+")


def strip_dashes(text: str) -> str:
    """Em dashes, en dashes and spaced hyphens become a comma and a space. Hyphenated words stay."""
    return _DASH_RE.sub(", ", text or "")


def brand_caption(caption: str, hashtags: str) -> tuple[str, str]:
    cap = strip_dashes(caption).strip()
    if not cap.startswith(BRAND_LINE):
        cap = f"{BRAND_LINE}\n\n{cap}"
    seen, tags = set(), []
    for t in list(BRAND_TAGS) + (hashtags or "").split():
        if t.startswith("#") and t.lower() not in seen:
            seen.add(t.lower())
            tags.append(t)
    return cap, " ".join(tags)
