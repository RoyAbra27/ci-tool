import pandas as pd

from ui.app import digest_markdown

INSIGHTS = pd.DataFrame(
    {
        "competitor": ["snyk", None, "jfrog"],
        "category": ["security_research", "other", "product_release"],
        "summary": ["Snyk found a worm", "Some industry piece", "Artifactory shipped X"],
        "quote": ["worm quote", "industry quote", "artifactory quote"],
        "confidence": ["high", "low", "medium"],
        "cluster_id": ["c1", "c2", "c3"],
    }
)
LINKS = pd.DataFrame(
    {
        "cluster_id": ["c1", "c3", "c3"],
        "source_id": ["snyk-blog", "jfrog-blog", "newsdata"],
        "url": ["https://s.example/1", "https://j.example/2", "https://n.example/3"],
    }
)


def test_sections_in_ui_order_with_industry_last():
    md = digest_markdown(INSIGHTS, LINKS, "2026-08-15")
    jfrog, snyk, industry = md.index("## JFrog"), md.index("## Snyk"), md.index("## Industry")
    assert jfrog < snyk < industry


def test_insight_line_carries_label_confidence_quote_and_links():
    md = digest_markdown(INSIGHTS, LINKS, "2026-08-15")
    assert "# Competitive intelligence digest - 2026-08-15" in md
    assert "- **Snyk found a worm** (Security research, high confidence)" in md
    assert "  > worm quote" in md
    assert "  - [Snyk blog](https://s.example/1)" in md
    assert "  - [JFrog blog](https://j.example/2)" in md
    assert "  - [Industry news](https://n.example/3)" in md


def test_insight_without_links_still_renders():
    md = digest_markdown(INSIGHTS, LINKS, "2026-08-15")
    assert "- **Some industry piece** (Other, low confidence)" in md
