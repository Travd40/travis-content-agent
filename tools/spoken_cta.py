"""
spoken_cta.py: the one spoken ask that ends every video's voiceover.

Shorts viewers swipe past without seeing the channel page, so each video ends
with a single clear ask. It alternates by post number between growing the
audience (follow) and booking the free call (link on the channel).
Set VOICEOVER_CTA to override the rotation with one fixed line.
"""

import os

SPOKEN_CTAS = [
    "Follow so you don't miss tomorrow's tip.",
    "Want help with this? The free call link is on my channel.",
]


def spoken_cta(post_number: int) -> str:
    override = os.getenv("VOICEOVER_CTA")
    if override:
        return override
    return SPOKEN_CTAS[post_number % len(SPOKEN_CTAS)]


def voiceover_script(content: dict, post_number: int) -> str:
    """Hook question first (the first ~2 seconds), then the tip, then the ask."""
    parts = [content.get("hook"), content["tip"], spoken_cta(post_number)]
    return " ... ".join(p for p in parts if p)


if __name__ == "__main__":
    sample = {
        "hook": "Why does he shut down every time we argue?",
        "tip": "Schedule the hard conversation. Ambushing her with heavy topics guarantees she'll defend before she listens.",
    }
    for n in (0, 1):
        print(voiceover_script(sample, n))
