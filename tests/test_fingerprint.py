from ci_tool.fingerprint import fingerprint, normalize_text, similarity

BASE_TEXT = (
    "We are looking for a senior backend engineer to join our platform team. "
    "You will design and build scalable services, own the data pipeline, "
    "and collaborate closely with product and design partners on a daily basis. "
    "Strong experience with distributed systems, databases, and cloud infrastructure "
    "is required for this role. You will mentor junior engineers and drive technical "
    "decisions across the organization while keeping reliability and performance front "
    "of mind at all times. This role reports to the head of engineering and partners "
    "with the site reliability group on incident response and capacity planning work. "
    "The team ships weekly, values pragmatic engineering, and invests heavily in "
    "automated testing, observability tooling, and clear documentation for every service."
)

DIFFERENT_TEXT = (
    "Zutrix qorvenal blimspar the ancient fjord council gathered beneath moss covered "
    "stones to debate the harvest of glowing kelp forests along the frozen tundra coastline. "
    "Elder navigators carved runes into driftwood staffs while apprentices tuned copper bells "
    "salvaged from sunken merchant vessels lost to the crimson tide decades earlier this century. "
    "Nobody spoke of the buried lighthouse keeper whose lantern still flickered each solstice "
    "eve above the whale bone archway guarding the abandoned salt mining village to the north."
)


def slightly_modified(text: str) -> str:
    return text.replace("senior backend engineer", "staff backend developer")


def test_short_text_returns_empty_fingerprint():
    assert fingerprint("too short") == ""


def test_degenerate_single_token_returns_empty_fingerprint():
    cjk_run = "中文测试" * 60
    assert len(normalize_text(cjk_run)) >= 200
    assert fingerprint(cjk_run) == ""


def test_identical_texts_have_similarity_one():
    fp_a = fingerprint(BASE_TEXT)
    fp_b = fingerprint(BASE_TEXT)
    assert similarity(fp_a, fp_b) == 1.0


def test_slightly_modified_text_scores_above_crosslist_threshold():
    modified = slightly_modified(BASE_TEXT)
    assert modified != BASE_TEXT
    score = similarity(fingerprint(BASE_TEXT), fingerprint(modified))
    assert score > 0.92, f"observed similarity was {score}"


def test_different_texts_score_well_below_half():
    score = similarity(fingerprint(BASE_TEXT), fingerprint(DIFFERENT_TEXT))
    assert score < 0.5, f"observed similarity was {score}"


def test_empty_or_malformed_fingerprints_never_match():
    assert similarity("", "anything") == 0.0
    assert similarity("zzzz", "zzzz") == 0.0


def test_fingerprint_is_deterministic():
    assert fingerprint(BASE_TEXT) == fingerprint(BASE_TEXT)
