import pandas as pd
import pytest

from ui.app import filter_by_title


def df(titles: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"title": titles})


TITLES = ["Snyk (beta) launch", "C++ SDK release", "plain title", None]


@pytest.mark.parametrize(
    ("search", "expected"),
    [
        ("(", ["Snyk (beta) launch"]),
        ("C++", ["C++ SDK release"]),
        ("[", []),
        ("snyk", ["Snyk (beta) launch"]),
    ],
)
def test_search_is_literal_and_case_insensitive(search, expected):
    assert filter_by_title(df(TITLES), search)["title"].tolist() == expected
