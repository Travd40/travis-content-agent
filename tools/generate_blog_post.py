"""
generate_blog_post.py
Writes one SEO blog article for travisdixoncoaching.com and drops it into a
checkout of Travd40/travis_coaching_site as blog/<slug>.md.

The site lists, dates and sitemaps any .md in blog/ that carries a
"<!-- date: YYYY-MM-DD -->" line, so writing the file is all publishing takes.
Run weekly by .github/workflows/weekly-blog.yml.

Topic order: --topic argument, then the next entry in blog_topic_queue.json,
then Claude picks a search question the existing posts don't cover yet.

Usage:
  python tools/generate_blog_post.py --site-dir site
  python tools/generate_blog_post.py --site-dir site --topic "why does my wife say I don't listen"
"""

import os
import re
import sys
import json
import time
import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic

MODEL = "claude-opus-4-7"
REQUEST_TIMEOUT_S = 300.0
MAX_ATTEMPTS = 5
BACKOFF_BASE_S = 4  # 4s, 8s, 16s, 32s between attempts 1→5
MIN_WORDS = 700

TOPIC_QUEUE = Path(__file__).parent.parent / "blog_topic_queue.json"
STYLE_SAMPLE_SLUG = "week-5-say-the-hard-thing"
STYLE_SAMPLE_CHARS = 3500

SYSTEM_PROMPT = """You write blog articles for travisdixoncoaching.com in the voice of Travis Dixon, a relationship coach.

Facts you may use (use no others about Travis):
- Travis is a relationship and life coach based in the Charlotte, NC area.
- He wrote the book "I Am A Dog: The Discipline of Becoming a Trained Partner".
- The free chapter (/freechapter) is the book's first chapter: the 5 signs you're an untrained partner, and the discipline that turns it around. Describe it only that way, and never claim the book or the chapter covers a specific topic beyond that.
- Brand idea: relationships fail from lack of TRAINING, not lack of love. Becoming a "trained partner" means discipline, loyalty, accountability and structure.
- He coaches couples, men, and individuals. He offers a free 15-minute strategy call.

Audience: people struggling in their relationship or marriage who are searching Google for help, usually late at night, usually hurting. Write for the exact question they typed.

Writing rules:
- First person as Travis. Direct, warm, structured. A coach, not a therapist. Plain words.
- Do NOT invent personal stories, client stories, statistics, studies, quotes or credentials. Speak from the coaching framework instead.
- Do NOT use em dashes or en dashes anywhere. Use commas, periods or colons.
- No clichés like "communication is key". No diagnosing. No medical or legal advice.
- If the topic touches abuse, violence or fear for safety, say plainly that coaching is not the right tool and point readers to the National Domestic Violence Hotline (1-800-799-7233) or 911.
- Speak to both men and women unless the topic is about one of them.

SEO rules:
- The title is the searcher's own question or phrase, natural and specific, 50 to 70 characters.
- Use the main search phrase in the title, the first paragraph, and one H2.
- The first paragraph answers the question directly in 2 or 3 sentences (it becomes the meta description).
- 900 to 1300 words. 4 to 6 H2 sections (##). Short paragraphs. Use a bulleted or numbered list where it helps, and give example sentences people can actually say.
- Include one natural internal link to [the book](/book) and one to [the free chapter](/freechapter) in the body.
- End with a short "## Where to start" section and a final line inviting them to [book a free 15-minute call](/freecall).

Output format, exactly:
TITLE: <title>
SLUG: <lowercase-hyphenated-slug, 3 to 8 words, no stop-word padding>
---
# <title>

<article body in Markdown>"""


def _pop_queued_topic() -> str | None:
    """Return and consume the next queued topic, or None. blog_topic_queue.json
    is a JSON list of topic strings; the workflow commits the consumed queue
    back to the repo only after a real publish."""
    if not TOPIC_QUEUE.exists():
        return None
    try:
        with open(TOPIC_QUEUE) as f:
            queue = json.load(f)
        if not isinstance(queue, list) or not queue:
            return None
        topic = queue.pop(0)
        with open(TOPIC_QUEUE, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=2)
            f.write("\n")
        if isinstance(topic, str) and topic.strip():
            return topic.strip()
        return None
    except Exception:
        return None


def _slugify(text: str, max_words: int = 8) -> str:
    words = re.sub(r"[^a-z0-9\s-]", "", text.lower().replace("'", "")).split()[:max_words]
    return re.sub(r"-+", "-", "-".join(words)).strip("-")


def _existing_titles(site_dir: Path) -> list[str]:
    titles = []
    for path in sorted((site_dir / "blog").glob("*.md")):
        m = re.search(r"^#\s+(.+)$", path.read_text(encoding="utf-8"), re.MULTILINE)
        titles.append(m.group(1).strip() if m else path.stem.replace("-", " "))
    return titles


def _style_sample(site_dir: Path) -> str:
    path = site_dir / "blog" / f"{STYLE_SAMPLE_SLUG}.md"
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")[:STYLE_SAMPLE_CHARS]
    return text.rsplit("\n\n", 1)[0]


def _call_claude_with_retry(client, user_prompt: str):
    last_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return client.messages.create(
                model=MODEL,
                max_tokens=6000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                timeout=REQUEST_TIMEOUT_S,
            )
        except (
            anthropic.APITimeoutError,
            anthropic.APIConnectionError,
            anthropic.RateLimitError,
            anthropic.InternalServerError,
        ) as e:
            last_err = e
            if attempt == MAX_ATTEMPTS:
                break
            wait = BACKOFF_BASE_S * (2 ** (attempt - 1))
            print(f"[generate_blog_post] {type(e).__name__} on attempt {attempt}/{MAX_ATTEMPTS}, retrying in {wait}s...", flush=True)
            time.sleep(wait)
    raise last_err


def _parse(raw: str) -> tuple[str, str, str]:
    """Split the model output into (title, slug, markdown starting with '# title')."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    title_m = re.search(r"^TITLE:\s*(.+)$", raw, re.MULTILINE)
    slug_m = re.search(r"^SLUG:\s*(.+)$", raw, re.MULTILINE)
    h1_m = re.search(r"^#\s+.+$", raw, re.MULTILINE)
    if not h1_m:
        raise ValueError("model output has no '# Title' line")
    body = raw[h1_m.start():].strip()
    title = title_m.group(1).strip() if title_m else h1_m.group(0)[1:].strip()
    slug = _slugify(slug_m.group(1) if slug_m else title)
    if not slug:
        slug = _slugify(title)
    # House style: no em or en dashes in published prose.
    body = re.sub(r"\s*[—–]\s*", ", ", body)
    title = re.sub(r"\s*[—–]\s*", ": ", title)
    body = re.sub(r"^#\s+.+$", f"# {title}", body, count=1, flags=re.MULTILINE)
    return title, slug, body


def _unique_path(blog_dir: Path, slug: str) -> Path:
    path = blog_dir / f"{slug}.md"
    n = 2
    while path.exists():
        path = blog_dir / f"{slug}-{n}.md"
        n += 1
    return path


def generate_blog_post(site_dir: Path, topic: str | None = None) -> dict:
    blog_dir = site_dir / "blog"
    if not blog_dir.is_dir():
        raise FileNotFoundError(f"{blog_dir} not found; is --site-dir a checkout of travis_coaching_site?")

    topic = (topic or "").strip() or _pop_queued_topic()
    existing = _existing_titles(site_dir)
    existing_block = "\n".join(f"  - {t}" for t in existing) or "  (none yet)"
    sample = _style_sample(site_dir)
    sample_block = f"\n\nHere is the opening of one of Travis's existing posts, for voice only (do not copy it, and ignore its dashes):\n\n<sample>\n{sample}\n</sample>" if sample else ""

    if topic:
        print(f"[generate_blog_post] Topic: {topic[:100]}", flush=True)
        ask = (
            f"Write this week's article on this REQUIRED topic:\n\n{topic}\n\n"
            f"Shape the title around how a struggling person would search for it."
        )
    else:
        print("[generate_blog_post] No queued topic, letting Claude pick one.", flush=True)
        ask = (
            "Pick this week's topic yourself: one specific, high-intent question that people "
            "struggling in a relationship or marriage really type into Google (for example about "
            "shutting down, constant arguing, trust after lying, feeling like roommates, "
            "resentment, apologizing, or wanting to save the marriage). Choose one that none of "
            "the existing posts already answer, then write the article."
        )

    user_prompt = (
        f"{ask}\n\nExisting posts on the site (do not repeat their topic or angle):\n{existing_block}"
        f"{sample_block}\n\nFollow the output format exactly."
    )

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    message = _call_claude_with_retry(client, user_prompt)
    raw = "".join(b.text for b in message.content if getattr(b, "type", "") == "text")
    title, slug, body = _parse(raw)

    words = len(body.split())
    if words < MIN_WORDS:
        raise ValueError(f"article too short ({words} words), not publishing")

    today = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    path = _unique_path(blog_dir, slug)
    path.write_text(f"<!-- date: {today} -->\n{body}\n", encoding="utf-8")

    result = {"title": title, "slug": path.stem, "path": str(path), "words": words, "date": today}
    print(f"[generate_blog_post] Wrote {path} ({words} words): {title}", flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-dir", required=True, help="checkout of Travd40/travis_coaching_site")
    parser.add_argument("--topic", default="", help="optional topic for this post")
    args = parser.parse_args()

    result = generate_blog_post(Path(args.site_dir), args.topic)

    gh_out = os.getenv("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"slug={result['slug']}\n")
            f.write(f"path={result['path']}\n")
            f.write(f"title={result['title']}\n")
    print(json.dumps(result, indent=2))
    sys.exit(0)
