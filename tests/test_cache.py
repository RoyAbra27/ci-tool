import json

import pytest

from ci_tool.cache import Fetcher, RawCache, SourceUnavailable


def test_put_then_latest_roundtrip(tmp_path):
    cache = RawCache(tmp_path)
    ref = cache.put("src", "https://example.com/feed", "<rss>v1</rss>")
    body, raw_ref = cache.latest("src", "https://example.com/feed")
    assert body == "<rss>v1</rss>"
    assert raw_ref == ref


def test_identical_body_is_not_duplicated(tmp_path):
    cache = RawCache(tmp_path)
    ref1 = cache.put("src", "https://example.com/feed", "same")
    ref2 = cache.put("src", "https://example.com/feed", "same")
    assert ref1 == ref2
    assert len(list((tmp_path / "src").glob("*.json"))) == 1


def test_latest_picks_newest_fetch(tmp_path):
    cache = RawCache(tmp_path)
    ref_old = cache.put("src", "https://example.com/feed", "old body")
    # age the first entry so ordering does not depend on write timing
    old_path = tmp_path / ref_old
    data = json.loads(old_path.read_text(encoding="utf-8"))
    data["fetched_at"] = "2000-01-01T00:00:00+00:00"
    old_path.write_text(json.dumps(data), encoding="utf-8")
    cache.put("src", "https://example.com/feed", "new body")
    body, _ = cache.latest("src", "https://example.com/feed")
    assert body == "new body"


def test_latest_is_per_url(tmp_path):
    cache = RawCache(tmp_path)
    cache.put("src", "https://example.com/a", "body a")
    cache.put("src", "https://example.com/b", "body b")
    assert cache.latest("src", "https://example.com/a")[0] == "body a"
    assert cache.latest("src", "https://example.com/missing") is None


def test_replay_fetcher_reads_cache_and_fails_closed(tmp_path):
    cache = RawCache(tmp_path)
    cache.put("src", "https://example.com/feed", "cached")
    fetcher = Fetcher(cache, live=False)
    body, ref = fetcher.get_text("src", "https://example.com/feed")
    assert body == "cached"
    assert ref
    with pytest.raises(SourceUnavailable):
        fetcher.get_text("src", "https://example.com/other")
