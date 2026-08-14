"""GitHub releases provider: same Atom shape as rss.py, title prefixed with repo."""

from ci_tool.cache import Fetcher
from ci_tool.models import RawItem, SourceConfig
from ci_tool.providers.rss import parse_feed


def fetch(source: SourceConfig, fetcher: Fetcher) -> list[RawItem]:
    if not source.repo:
        raise ValueError(f"github_releases source {source.id!r} has no repo")
    cache_url = f"https://github.com/{source.repo}/releases.atom"
    body, raw_ref = fetcher.get_text(source.id, cache_url)
    return [
        item.model_copy(update={"title": f"{source.repo}: {item.title}"})
        for item in parse_feed(body, source, raw_ref)
    ]
