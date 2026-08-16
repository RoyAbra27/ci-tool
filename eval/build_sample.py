"""Dump the labelling sample for eval/labels.json: every item that passed the
filter chain plus every irrelevant/dup rejection and the 2 newest stale items.
Verdicts come from filters.classify_item (the production gate) against empty
seen-sets, reproducing the first ingest run. Prints JSON to stdout."""

import json
import sys
from datetime import UTC, datetime, timedelta

from ci_tool import filters, providers
from ci_tool.cache import Fetcher, RawCache, SourceUnavailable
from ci_tool.models import load_config

STALE_SAMPLE = 2
# frozen so the sample is reproducible after the recency window moves on
NOW = datetime(2026, 8, 14, 10, 20, 35, tzinfo=UTC)


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
        v, item = filters.classify_item(
            item, cutoff=cutoff, batch_ids=batch_ids,
            seen_ids=set(), seen_urls=set(), matcher=matcher,
        )
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
