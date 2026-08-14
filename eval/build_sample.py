"""Dump the labelling sample for eval/labels.json: every item that passed the
filter chain plus every irrelevant/dup rejection and the 2 newest stale items.
Verdicts are recomputed with the same predicates as filters.run_chain against
empty seen-sets, reproducing the first ingest run. Prints JSON to stdout."""

import json
import sys
from datetime import UTC, datetime, timedelta

from ci_tool import filters, providers
from ci_tool.cache import Fetcher, RawCache, SourceUnavailable
from ci_tool.models import load_config

STALE_SAMPLE = 2
# frozen so the sample is reproducible after the recency window moves on
NOW = datetime(2026, 8, 14, 10, 20, 35, tzinfo=UTC)


def verdict(item, cutoff, batch_ids, matcher):
    url = filters.canonicalize_url(item.url)
    if not url or not item.title.strip():
        return "invalid", item
    item = item.model_copy(update={"url": url})
    published = item.published_at or item.fetched_at
    if published.tzinfo is None:
        published = published.replace(tzinfo=UTC)
    if published < cutoff:
        return "stale", item
    content_id = item.content_hash()
    if content_id in batch_ids:
        return "dup_batch", item
    if item.trust_tier >= 3 and not matcher(f"{item.title} {item.text}"):
        return "irrelevant", item
    batch_ids.add(content_id)
    return "passed", item


def main():
    cfg = load_config("config.toml")
    fetcher = Fetcher(RawCache("data/raw"), live=False)
    items = []
    for source in cfg.sources:
        try:
            items.extend(providers.fetch(source, fetcher))
        except SourceUnavailable:
            pass

    cutoff = NOW - timedelta(days=cfg.settings.recency_days)
    matcher = filters.build_matcher(cfg.aliases())
    batch_ids = set()
    by_verdict = {}
    for item in items:
        v, item = verdict(item, cutoff, batch_ids, matcher)
        by_verdict.setdefault(v, []).append(item)

    stale = sorted(
        by_verdict.get("stale", []),
        key=lambda i: i.published_at or i.fetched_at, reverse=True,
    )[:STALE_SAMPLE]
    labelled = (
        [("passed", i) for i in by_verdict.get("passed", [])]
        + [("irrelevant", i) for i in by_verdict.get("irrelevant", [])]
        + [("dup_batch", i) for i in by_verdict.get("dup_batch", [])]
        + [("stale", i) for i in stale]
    )
    out = [
        {
            "id": item.content_hash(),
            "source_id": item.source_id,
            "trust_tier": item.trust_tier,
            "competitor": item.competitor,
            "title": item.title,
            "text": item.text[:500],
            "url": item.url,
            "published_at": str(item.published_at or item.fetched_at),
            "pipeline_verdict": v,
        }
        for v, item in labelled
    ]
    json.dump(out, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
