"""Provider registry: dispatches fetch() to ci_tool.providers.<name> by source.provider."""

import importlib

from ci_tool.cache import Fetcher
from ci_tool.models import RawItem, SourceConfig


def fetch(source: SourceConfig, fetcher: Fetcher) -> list[RawItem]:
    try:
        module = importlib.import_module(f".{source.provider}", __package__)
    except ImportError:
        raise ValueError(f"unknown provider: {source.provider!r}")
    return module.fetch(source, fetcher)
