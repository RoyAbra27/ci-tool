"""RSS/Atom provider. Also supplies the feed-parsing helper github_releases reuses."""

import time
from datetime import datetime, timezone
from html.parser import HTMLParser

import feedparser

from ci_tool.cache import Fetcher
from ci_tool.models import RawItem, SourceConfig


class _TextStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.chunks: list[str] = []

    def handle_data(self, data):
        self.chunks.append(data)


def _strip_html(html: str) -> str:
    stripper = _TextStripper()
    stripper.feed(html)
    return " ".join(" ".join(stripper.chunks).split())


def _best_text(entry) -> str:
    content = entry.get("content")
    raw = entry.get("summary") or (content[0].value if content else "") or ""
    return _strip_html(raw)


def _to_datetime(struct_time: time.struct_time | None) -> datetime | None:
    if struct_time is None:
        return None
    return datetime(*struct_time[:6], tzinfo=timezone.utc)


def _parse_entry(entry, source: SourceConfig, raw_ref: str, fetched_at: datetime) -> RawItem | None:
    url = entry.get("link")
    title = entry.get("title")
    if not url or not title:
        return None
    published_at = _to_datetime(entry.get("published_parsed") or entry.get("updated_parsed"))
    return RawItem(
        source_id=source.id,
        trust_tier=source.trust_tier,
        competitor=source.competitor,
        url=url,
        title=title,
        text=_best_text(entry),
        published_at=published_at,
        fetched_at=fetched_at,
        raw_ref=raw_ref,
    )


def parse_feed(body: str, source: SourceConfig, raw_ref: str) -> list[RawItem]:
    """Entries of one RSS/Atom body, skipping any without a url and title."""
    fetched_at = datetime.now(timezone.utc)
    items = (
        _parse_entry(entry, source, raw_ref, fetched_at)
        for entry in feedparser.parse(body).entries
    )
    return [item for item in items if item is not None]


def fetch(source: SourceConfig, fetcher: Fetcher) -> list[RawItem]:
    if source.url is None:
        raise ValueError(f"rss source {source.id!r} has no url")
    body, raw_ref = fetcher.get_text(source.id, source.url)
    return parse_feed(body, source, raw_ref)
