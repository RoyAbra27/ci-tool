from ci_tool.grounding import confidence, verify
from ci_tool.models import InsightExtraction

SOURCE = (
    "Cloudsmith today announced it has raised $72M in Series C funding led by TCV. "
    "The company plans to expand its artifact management platform to 500 enterprises."
)


def make_extraction(**overrides) -> InsightExtraction:
    base = dict(
        summary="Cloudsmith raised $72M in Series C funding.",
        category="funding",
        themes=[],
        entities=["Cloudsmith", "TCV"],
        numbers=["$72M"],
        quote="Cloudsmith today announced it has raised $72M in Series C funding led by TCV.",
    )
    base.update(overrides)
    return InsightExtraction(**base)


def test_grounded_extraction_passes():
    assert verify(make_extraction(), SOURCE) == []


def test_quote_matching_ignores_whitespace_and_case():
    quote = "cloudsmith  today announced it has raised $72M\nin Series C funding led by TCV."
    assert verify(make_extraction(quote=quote), SOURCE) == []


def test_fabricated_quote_fails():
    errors = verify(make_extraction(quote="Cloudsmith will destroy JFrog next year."), SOURCE)
    assert any("quote" in e for e in errors)


def test_unknown_entity_fails():
    errors = verify(make_extraction(entities=["Cloudsmith", "Microsoft"]), SOURCE)
    assert any("Microsoft" in e for e in errors)


def test_undeclared_summary_number_must_still_exist_in_source():
    errors = verify(
        make_extraction(summary="Cloudsmith raised $99M.", numbers=[]), SOURCE
    )
    assert any("99" in e for e in errors)


def test_comma_insensitive_number_match():
    src = "The registry now serves 72,000 customers."
    ext = make_extraction(
        summary="The registry serves 72000 customers.",
        entities=[], numbers=[], quote="The registry now serves 72,000 customers.",
    )
    assert verify(ext, src) == []


def test_confidence_is_computed_from_tier_and_corroboration():
    assert confidence(1, 1) == "high"
    assert confidence(2, 1) == "medium"
    assert confidence(3, 1) == "low"
    assert confidence(3, 2) == "medium"
    assert confidence(1, 5) == "high"
