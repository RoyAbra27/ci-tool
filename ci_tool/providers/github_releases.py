"""GitHub releases provider: same Atom shape as rss.py, title prefixed with repo."""

from datetime import datetime, timezone

import feedparser

from ci_tool.cache import Fetcher
from ci_tool.models import RawItem, SourceConfig
from ci_tool.providers.rss import parse_entry


def fetch(source: SourceConfig, fetcher: Fetcher) -> list[RawItem]:
    if not source.repo:
        raise ValueError(f"github_releases source {source.id!r} has no repo")
    cache_url = f"https://github.com/{source.repo}/releases.atom"
    body, raw_ref = fetcher.get_text(source.id, cache_url)
    parsed = feedparser.parse(body)
    fetched_at = datetime.now(timezone.utc)
    items = []
    for entry in parsed.entries:
        item = parse_entry(entry, source, raw_ref, fetched_at)
        if item is None:
            continue
        items.append(item.model_copy(update={"title": f"{source.repo}: {item.title}"}))
    return items
