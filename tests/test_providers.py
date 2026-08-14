from datetime import timezone

import pytest

from ci_tool.models import SourceConfig
from ci_tool.providers import fetch as dispatch_fetch
from ci_tool.providers import github_releases, newsdata, rss

RSS_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Feed</title>
<item>
  <title>First post</title>
  <link>https://example.com/1</link>
  <description>&lt;p&gt;Hello &lt;b&gt;world&lt;/b&gt;&lt;/p&gt;</description>
  <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
</item>
<item>
  <title>No link post</title>
  <description>orphan</description>
</item>
</channel></rss>
"""

ATOM_XML = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
  <title>v1.2.3</title>
  <link href="https://github.com/acme/widget/releases/tag/v1.2.3"/>
  <updated>2024-02-01T00:00:00Z</updated>
  <content>Release notes</content>
</entry>
</feed>
"""

NEWSDATA_JSON = """
{"results": [
  {"title": "Story one", "link": "https://news.example/1",
   "description": "desc one", "pubDate": "2024-03-01 10:00:00"},
  {"title": "Missing link"}
]}
"""


class FakeFetcher:
    def __init__(self, body="", ref="fake/ref.json", live=False):
        self.body = body
        self.ref = ref
        self.live = live
        self.calls = 0

    def get_text(self, source_id, cache_url, *, params=None):
        self.calls += 1
        return self.body, self.ref


def test_rss_parses_strips_html_and_skips_missing_link():
    source = SourceConfig(id="s1", provider="rss", trust_tier=2, url="https://feed.example/rss.xml")
    fetcher = FakeFetcher(body=RSS_XML)

    items = rss.fetch(source, fetcher)

    assert len(items) == 1
    item = items[0]
    assert item.url == "https://example.com/1"
    assert item.title == "First post"
    assert "<" not in item.text and ">" not in item.text
    assert "Hello world" in item.text
    assert item.published_at is not None
    assert item.published_at.tzinfo is not None
    assert item.published_at.utcoffset() == timezone.utc.utcoffset(None)


def test_github_releases_prefixes_title_with_repo():
    source = SourceConfig(id="s2", provider="github_releases", trust_tier=1, repo="acme/widget")
    fetcher = FakeFetcher(body=ATOM_XML)

    items = github_releases.fetch(source, fetcher)

    assert len(items) == 1
    assert items[0].title == "acme/widget: v1.2.3"
    assert items[0].url == "https://github.com/acme/widget/releases/tag/v1.2.3"


def test_newsdata_skips_malformed_entries_and_parses_pubdate():
    source = SourceConfig(id="s3", provider="newsdata", trust_tier=3, query="acme")
    fetcher = FakeFetcher(body=NEWSDATA_JSON)

    items = newsdata.fetch(source, fetcher)

    assert len(items) == 1
    item = items[0]
    assert item.title == "Story one"
    assert item.text == "desc one"
    assert item.published_at.tzinfo is not None


def test_newsdata_live_without_key_skips_without_fetch(monkeypatch):
    monkeypatch.delenv("NEWSDATA_API_KEY", raising=False)
    source = SourceConfig(id="s4", provider="newsdata", trust_tier=3, query="acme")
    fetcher = FakeFetcher(live=True)

    items = newsdata.fetch(source, fetcher)

    assert items == []
    assert fetcher.calls == 0


def test_dispatch_unknown_provider_raises():
    source = SourceConfig(id="s5", provider="nope")
    with pytest.raises(ValueError):
        dispatch_fetch(source, FakeFetcher())
