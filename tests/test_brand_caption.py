from brand_caption import brand_caption, BRAND_TAGS, strip_dashes
from spoken_cta import voiceover_script


def test_strip_dashes_rewrites_em_en_and_spaced_hyphen():
    assert strip_dashes("public — and every gap") == "public, and every gap"
    assert strip_dashes("one – two") == "one, two"
    assert strip_dashes("one - two") == "one, two"
    assert strip_dashes("15-min call") == "15-min call"


def test_brand_caption_opens_with_name_and_adds_brand_tags():
    cap, tags = brand_caption("She's not paranoid. She's pattern-matching.", "#relationships #couples")
    assert cap.startswith("Travis Dixon Coaching | Relationship coach")
    assert "She's not paranoid" in cap
    for t in BRAND_TAGS:
        assert t in tags
    assert "#relationships" in tags and tags.count("#TravisDixonCoaching") == 1


def test_brand_caption_is_idempotent():
    cap, tags = brand_caption("Travis Dixon Coaching | Relationship coach\n\nBody.", "#TravisDixonCoaching #x")
    assert cap.count("Travis Dixon Coaching | Relationship coach") == 1
    assert tags.count("#TravisDixonCoaching") == 1


def test_voiceover_opens_with_the_name():
    vo = voiceover_script({"hook": "Why does he shut down?", "tip": "Tip.", "script": "Body sentence one. Body two."}, 0)
    assert vo.startswith("Why does he shut down? ... Coach Tee here from Travis Dixon Coaching.")
