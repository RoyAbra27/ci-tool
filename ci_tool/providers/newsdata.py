"""NewsData.io provider. apikey travels only in params, never in cache_url,
so the cache file for a source never stores the secret."""

import json
import os
import sys
import urllib.parse
from datetime import datetime, timezone

from ci_tool.cache import Fetcher
from ci_tool.models import RawItem, SourceConfig

_ENDPOINT = "https://newsdata.io/api/1/latest"


def _parse_pubdate(pub_date) -> datetime | None:
    if not isinstance(pub_date, str):
        return None
    try:
        return datetime.strptime(pub_date, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def fetch(source: SourceConfig, fetcher: Fetcher) -> list[RawItem]:
    if not source.query:
        raise ValueError(f"newsdata source {source.id!r} has no query")
    cache_url = f"{_ENDPOINT}?q=" + urllib.parse.quote(source.query)

    if fetcher.live and "NEWSDATA_API_KEY" not in os.environ:
        print(f"newsdata: skipping {source.id!r}, no NEWSDATA_API_KEY", file=sys.stderr)
        return []

    # q already lives in cache_url; httpx merges params with the URL query,
    # so repeating it here would send q twice
    params = {"apikey": os.environ.get("NEWSDATA_API_KEY", "")}
    body, raw_ref = fetcher.get_text(source.id, cache_url, params=params)
    fetched_at = datetime.now(timezone.utc)

    results = json.loads(body).get("results", [])
    items = []
    for entry in results:
        if not isinstance(entry, dict):
            continue
        url = entry.get("link")
        title = entry.get("title")
        if not url or not title:
            continue
        items.append(RawItem(
            source_id=source.id,
            trust_tier=source.trust_tier,
            competitor=source.competitor,
            url=url,
            title=title,
            text=entry.get("description") or "",
            published_at=_parse_pubdate(entry.get("pubDate")),
            fetched_at=fetched_at,
            raw_ref=raw_ref,
        ))
    return items
