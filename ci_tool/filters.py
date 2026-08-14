"""Deterministic gates, ordered cheapest-and-most-decisive first, one counter
each. The LLM never decides what enters the pipeline; these functions do."""

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ci_tool.models import RawItem

TRACKING_PARAM_PREFIXES = ("utm_",)
TRACKING_PARAMS = {"gclid", "fbclid", "mc_cid", "mc_eid", "igshid", "hsCtaTracking"}


def canonicalize_url(url: str) -> str:
    """Same page, one string: lowercase host, no fragment, no tracking params,
    sorted query, no trailing slash. Returns '' for anything not http(s)."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return ""
    query = urlencode(sorted(
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k not in TRACKING_PARAMS and not k.lower().startswith(TRACKING_PARAM_PREFIXES)
    ))
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme, parts.netloc.lower(), path, query, ""))


def compile_keyword(kw: str):
    """Keywords of 2-3 chars match on word boundaries only, so 'ci' never
    matches inside 'circle'; longer keywords stay fast substring checks."""
    kw = kw.lower().strip()
    if re.fullmatch(r"[a-z0-9]{2,3}", kw):
        pattern = re.compile(rf"\b{re.escape(kw)}\b")
        return lambda text: bool(pattern.search(text))
    return lambda text: kw in text


def build_matcher(aliases: list[str]):
    # empty strings are dropped: '' is a substring of everything and would
    # silently bypass the relevance gate
    matchers = [compile_keyword(a) for a in aliases if a.strip()]

    def match(text: str) -> bool:
        lowered = text.lower()
        return any(m(lowered) for m in matchers)

    return match


def _as_utc(ts: datetime) -> datetime:
    return ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts


def run_chain(
    items: list[RawItem],
    *,
    now: datetime,
    recency_days: int,
    seen_ids: set[str],
    seen_urls: set[str],
    matcher,
) -> tuple[list[RawItem], dict[str, int]]:
    counters = {
        "found": len(items), "invalid": 0, "stale": 0,
        "dup_batch": 0, "dup_seen": 0, "irrelevant": 0, "passed": 0,
    }
    cutoff = now - timedelta(days=recency_days)
    passed: list[RawItem] = []
    batch_ids: set[str] = set()

    for item in items:
        url = canonicalize_url(item.url)
        if not url or not item.title.strip():
            counters["invalid"] += 1
            continue
        item = item.model_copy(update={"url": url})
        if _as_utc(item.published_at or item.fetched_at) < cutoff:
            counters["stale"] += 1
            continue
        content_id = item.content_hash()
        if content_id in batch_ids:
            counters["dup_batch"] += 1
            continue
        if content_id in seen_ids or url in seen_urls:
            counters["dup_seen"] += 1
            continue
        # tier 1-2 feeds are on-topic by construction; only third-party news
        # must name a tracked entity
        if item.trust_tier >= 3 and not matcher(f"{item.title} {item.text}"):
            counters["irrelevant"] += 1
            continue
        batch_ids.add(content_id)
        passed.append(item)
        counters["passed"] += 1

    return passed, counters
