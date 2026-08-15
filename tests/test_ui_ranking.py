import pandas as pd
import pytest

from ui.app import demote_low_signal


def df(categories: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"category": categories, "summary": [f"s{i}" for i in range(len(categories))]})


@pytest.mark.parametrize(
    ("categories", "expected"),
    [
        (
            ["marketing_content", "product_release", "other", "security_research"],
            ["product_release", "security_research", "marketing_content", "other"],
        ),
        (["marketing_content", "other"], ["marketing_content", "other"]),
        (["funding", "partnership"], ["funding", "partnership"]),
    ],
)
def test_low_signal_categories_sink(categories, expected):
    assert demote_low_signal(df(categories))["category"].tolist() == expected


def test_sort_is_stable_within_rank():
    out = demote_low_signal(df(["marketing_content", "product_release", "marketing_content"]))
    assert out["summary"].tolist() == ["s1", "s0", "s2"]


def test_empty_frame_passes_through():
    empty = df([])
    assert demote_low_signal(empty).empty
