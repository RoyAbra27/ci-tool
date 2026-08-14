from datetime import UTC, datetime, timedelta

from ci_tool.filters import build_matcher, canonicalize_url, compile_keyword, run_chain
from ci_tool.models import RawItem

NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)


def make_item(**overrides) -> RawItem:
    base = {
        "source_id": "test-src",
        "trust_tier": 1,
        "competitor": "sonatype",
        "url": "https://example.com/post",
        "title": "A perfectly normal post title",
        "text": "Body text about artifact registries.",
        "published_at": NOW - timedelta(days=1),
        "fetched_at": NOW,
        "raw_ref": "test/ref.json",
    }
    base.update(overrides)
    return RawItem(**base)


class TestCanonicalizeUrl:
    def test_strips_tracking_params_and_fragment(self):
        url = "https://Example.com/Post/?utm_source=x&utm_medium=y&gclid=123&b=2&a=1#section"
        assert canonicalize_url(url) == "https://example.com/Post?a=1&b=2"

    def test_lowercases_host_keeps_path_case(self):
        assert canonicalize_url("https://WWW.Example.COM/CaseSensitive") == "https://www.example.com/CaseSensitive"

    def test_strips_trailing_slash_but_keeps_root(self):
        assert canonicalize_url("https://example.com/blog/") == "https://example.com/blog"
        assert canonicalize_url("https://example.com/") == "https://example.com/"

    def test_rejects_non_http(self):
        assert canonicalize_url("ftp://example.com/x") == ""
        assert canonicalize_url("not a url") == ""
        assert canonicalize_url("javascript:alert(1)") == ""


class TestKeywordMatching:
    def test_short_keyword_needs_word_boundary(self):
        m = compile_keyword("ci")
        assert m("our ci pipeline")
        assert not m("circle of trust")
        assert not m("specific")

    def test_long_keyword_is_substring(self):
        m = compile_keyword("cloudsmith")
        assert m("why cloudsmith raised money")

    def test_matcher_drops_empty_strings(self):
        m = build_matcher(["", "  ", "sonatype"])
        assert not m("random unrelated text")
        assert m("Sonatype shipped a thing")


class TestRunChain:
    def kwargs(self, **overrides):
        base = {"now": NOW, "recency_days": 14, "seen_ids": set(), "seen_urls": set(),
                "matcher": build_matcher(["sonatype", "cloudsmith"])}
        base.update(overrides)
        return base

    def test_happy_path_passes(self):
        passed, counters = run_chain([make_item()], **self.kwargs())
        assert len(passed) == 1
        assert counters["passed"] == 1

    def test_invalid_url_and_blank_title_drop(self):
        items = [make_item(url="not a url"), make_item(title="   ")]
        passed, counters = run_chain(items, **self.kwargs())
        assert not passed
        assert counters["invalid"] == 2

    def test_stale_drops_missing_date_uses_fetched_at(self):
        old = make_item(published_at=NOW - timedelta(days=30))
        undated_fresh = make_item(published_at=None, title="undated but fresh")
        passed, counters = run_chain([old, undated_fresh], **self.kwargs())
        assert [i.title for i in passed] == ["undated but fresh"]
        assert counters["stale"] == 1

    def test_naive_datetime_treated_as_utc(self):
        naive = make_item(published_at=datetime(2026, 8, 13, 12, 0))  # noqa: DTZ001 - naive on purpose, this tests the naive path
        passed, _ = run_chain([naive], **self.kwargs())
        assert len(passed) == 1

    def test_batch_dup_by_content_not_url(self):
        a = make_item(url="https://example.com/a")
        b = make_item(url="https://example.com/b")
        passed, counters = run_chain([a, b], **self.kwargs())
        assert len(passed) == 1
        assert counters["dup_batch"] == 1

    def test_seen_by_id_and_by_url(self):
        item = make_item()
        _, counters = run_chain([item], **self.kwargs(seen_ids={item.content_hash()}))
        assert counters["dup_seen"] == 1
        _, counters = run_chain([item], **self.kwargs(seen_urls={"https://example.com/post"}))
        assert counters["dup_seen"] == 1

    def test_relevance_gates_tier3_only(self):
        offtopic_t1 = make_item(title="Team offsite recap", text="fun times")
        offtopic_t3 = make_item(trust_tier=3, title="Generic tech news", text="nothing tracked here")
        ontopic_t3 = make_item(trust_tier=3, title="Cloudsmith raises Series C", text="")
        passed, counters = run_chain([offtopic_t1, offtopic_t3, ontopic_t3], **self.kwargs())
        assert {i.title for i in passed} == {"Team offsite recap", "Cloudsmith raises Series C"}
        assert counters["irrelevant"] == 1

    def test_counters_add_up(self):
        items = [make_item(), make_item(url="bad"),
                 make_item(trust_tier=3, title="untracked news", text="x")]
        _, c = run_chain(items, **self.kwargs())
        dropped = c["invalid"] + c["stale"] + c["dup_batch"] + c["dup_seen"] + c["irrelevant"]
        assert c["found"] == c["passed"] + dropped
