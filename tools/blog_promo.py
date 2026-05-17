"""
blog_promo.py — Returns a "blog promo" content dict for the bot to render & post.

When called, this gives the bot a ready-to-render blog promo instead of a generic
coaching tip. The bot uses the same render pipeline (Remotion video + caption +
publish to IG/FB) — but the caption drives traffic to one of Travis's blog posts.

Rotates through 4 blog posts. Used by agent.py on Fridays.
"""

import random

# 4 blog posts — bot rotates through these every Friday.
BLOG_PROMOS = [
    {
        "category": "MEN'S COACHING",
        "tip": "When he goes silent, he isn't punishing you — he's protecting himself.",
        "caption": (
            "Most men don't go silent because they're mad.\n\n"
            "They go silent because they ran the math: "
            "'Will this actually get resolved? Or will it become "
            "a list of what I did wrong?'\n\n"
            "I was the silent man for 15 of my 18 years married. "
            "I thought going quiet was maturity. It wasn't.\n\n"
            "Full breakdown of what's behind the shutdown — and how to "
            "talk to him without triggering more of it ↓\n\n"
            "https://travis-coaching-site-1.onrender.com/blog/week-1-why-does-my-husband-shut-down\n\n"
            "Free 15-min call: https://calendly.com/travd40/15-minute-strategy-call\n"
            "Book: amazon.com/dp/B0GPSNXGY8"
        ),
        "hashtags": "#relationshipcoaching #marriage #menshealth #charlottenc #couples #emotionalsafety",
    },
    {
        "category": "COMMUNICATION",
        "tip": "Most couples don't have a communication problem. They have a courtroom problem.",
        "caption": (
            "Every disagreement turns into:\n"
            "→ Who's right\n"
            "→ Who started it\n"
            "→ Who has more receipts\n\n"
            "That's not a conversation. That's a trial. "
            "And trials don't build relationships — they end them.\n\n"
            "Stop arguing like a lawyer. Start showing up like a teammate.\n\n"
            "Just published the full piece ↓\n\n"
            "https://travis-coaching-site-1.onrender.com/blog/week-2-communication-isnt-a-courtroom\n\n"
            "Free 15-min call: https://calendly.com/travd40/15-minute-strategy-call\n"
            "Book: amazon.com/dp/B0GPSNXGY8"
        ),
        "hashtags": "#communication #marriage #couples #relationshiptips #charlottenc",
    },
    {
        "category": "COUPLES COACHING",
        "tip": "'I'm sorry, BUT' is not an apology. It's a defense in disguise.",
        "caption": (
            "A real apology doesn't need a 'but.' "
            "It just sits in the discomfort and owns it.\n\n"
            "If you can't apologize without justifying yourself, "
            "you don't actually want repair. You want to win while "
            "looking like you tried.\n\n"
            "Full breakdown — how to apologize without the excuse ↓\n\n"
            "https://travis-coaching-site-1.onrender.com/blog/week-3-how-to-apologize-without-excuses\n\n"
            "Free 15-min call: https://calendly.com/travd40/15-minute-strategy-call\n"
            "Book: amazon.com/dp/B0GPSNXGY8"
        ),
        "hashtags": "#apology #relationships #emotionalintelligence #marriage #couples",
    },
    {
        "category": "COUPLES COACHING",
        "tip": "50/50 marriages don't work. The math sounds fair. The math kills relationships.",
        "caption": (
            "Some weeks she's at 30%. Some weeks he's at 30%.\n\n"
            "If you're keeping score, the moment one person drops below 50, "
            "the other one stops giving 100.\n\n"
            "Real partnership is 100/100. You both bring everything you have. "
            "Every time.\n\n"
            "The full case for why 50/50 is the most common marriage trap I see ↓\n\n"
            "https://travis-coaching-site-1.onrender.com/blog/week-4-the-50-50-marriage-myth\n\n"
            "Free 15-min call: https://calendly.com/travd40/15-minute-strategy-call\n"
            "Book: amazon.com/dp/B0GPSNXGY8"
        ),
        "hashtags": "#marriage #couples #relationshipgoals #charlottenc #partnership",
    },
]


def get_blog_promo(post_count: int) -> dict:
    """Return the next blog promo in rotation. post_count comes from agent.py state."""
    idx = post_count % len(BLOG_PROMOS)
    return dict(BLOG_PROMOS[idx])  # copy so caller can mutate freely


if __name__ == "__main__":
    # Quick smoke test
    for i in range(5):
        promo = get_blog_promo(i)
        print(f"#{i}: {promo['category']} — {promo['tip'][:60]}...")
