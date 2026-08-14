"""Provider registry: maps source.provider to its fetch function."""

from ci_tool.cache import Fetcher
from ci_tool.models import RawItem, SourceConfig
from ci_tool.providers import github_releases, newsdata, rss

PROVIDERS = {
    "rss": rss.fetch,
    "github_releases": github_releases.fetch,
    "newsdata": newsdata.fetch,
}


def fetch(source: SourceConfig, fetcher: Fetcher) -> list[RawItem]:
    if source.provider not in PROVIDERS:
        raise ValueError(f"unknown provider: {source.provider!r}")
    return PROVIDERS[source.provider](source, fetcher)
