import pytest

from ui.app import category_label, source_labels


@pytest.mark.parametrize(
    ("slug", "label"),
    [
        ("product_release", "Product release"),
        ("marketing_content", "Marketing content"),
        ("security_research", "Security research"),
        ("other", "Other"),
    ],
)
def test_category_label_humanizes_slug(slug, label):
    assert category_label(slug) == label


def test_source_labels_come_from_config():
    labels = source_labels()
    assert labels["jfrog-blog"] == "JFrog blog"
    assert labels["github-changelog"] == "GitHub changelog"
    assert labels["newsdata"] == "Industry news"


def test_unlabelled_source_falls_back_to_id():
    assert source_labels().get("some-future-source", "some-future-source") == "some-future-source"
