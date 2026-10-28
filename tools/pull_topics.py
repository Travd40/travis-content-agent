"""Pull queued topics from the coaching site repo into topic_queue.json.

The YouTube agent in Travd40/travis_coaching_site writes buyer-matched topics to
agents/youtube/topics_for_content_bot.json (a JSON list of strings). Each daily
run of this bot appends any new entries to its own topic_queue.json, skipping
ones already queued or already posted. Nothing is removed from the source file;
the "seen" set below is what prevents repeats.

    python tools/pull_topics.py          # prints how many topics were added
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
QUEUE = ROOT / "topic_queue.json"
SEEN = ROOT / "topics_seen.json"
SOURCE = ("https://raw.githubusercontent.com/Travd40/travis_coaching_site/main/"
          "agents/youtube/topics_for_content_bot.json")


def _load_list(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text())
        return [t for t in data if isinstance(t, str) and t.strip()] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def merge(incoming: list[str], queue: list[str], seen: list[str]) -> tuple[list[str], list[str], int]:
    """Pure: append unseen incoming topics to queue; return (queue, seen, added)."""
    queued = {t.strip() for t in queue}
    known = queued | {t.strip() for t in seen}
    seen_set = {t.strip() for t in seen}
    added = 0
    for t in incoming:
        t = t.strip()
        if not t:
            continue
        if t not in known:
            queue.append(t)
            known.add(t)
            added += 1
        if t not in seen_set:
            # Record every incoming topic, even one already queued by hand, so a
            # consumed queue entry is never re-imported from the unchanged source.
            seen.append(t)
            seen_set.add(t)
    return queue, seen, added


def main() -> int:
    try:
        with urllib.request.urlopen(SOURCE, timeout=30) as r:
            incoming = json.loads(r.read().decode())
        incoming = [t for t in incoming if isinstance(t, str)] if isinstance(incoming, list) else []
    except Exception as exc:  # noqa: BLE001  never block the daily post over this
        print(f"pull_topics: could not fetch source ({exc}); skipping")
        return 0
    queue, seen, added = merge(incoming, _load_list(QUEUE), _load_list(SEEN))
    if added:
        QUEUE.write_text(json.dumps(queue, indent=2) + "\n")
        SEEN.write_text(json.dumps(seen, indent=2) + "\n")
    print(f"pull_topics: {added} new topic(s) added, {len(queue)} queued")
    return 0


if __name__ == "__main__":
    sys.exit(main())
