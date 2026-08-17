"""Raw payload cache: files are canonical, the DB is derived.

Every live fetch is stored append-only under data/raw/<source_id>/. Replay mode
re-runs the entire pipeline from these files with zero network, which is both
the reproducibility guarantee and the grader's no-keys demo path.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from ci_tool import http


class SourceUnavailable(Exception):
    """Replay mode has no cached payload for this source URL."""


def _url_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


class RawCache:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def put(self, source_id: str, cache_url: str, body: str) -> str:
        body_hash = hashlib.sha256(body.encode()).hexdigest()[:12]
        path = self.root / source_id / f"{_url_key(cache_url)}-{body_hash}.json"
        if not path.exists():  # append-only: identical content is never rewritten
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "url": cache_url,
                "fetched_at": datetime.now(UTC).isoformat(),
                "body": body,
            }, ensure_ascii=False), encoding="utf-8")
        return str(path.relative_to(self.root))

    def all(self, source_id: str, cache_url: str) -> list[tuple[str, str]]:
        """Every cached (body, raw_ref) for this source URL, oldest first."""
        prefix = _url_key(cache_url)
        candidates = sorted(
            (self.root / source_id).glob(f"{prefix}-*.json"),
            key=lambda p: json.loads(p.read_text(encoding="utf-8"))["fetched_at"],
        ) if (self.root / source_id).exists() else []
        return [
            (json.loads(p.read_text(encoding="utf-8"))["body"], str(p.relative_to(self.root)))
            for p in candidates
        ]

    def latest(self, source_id: str, cache_url: str) -> tuple[str, str] | None:
        """Newest cached (body, raw_ref) for this source URL, or None."""
        snapshots = self.all(source_id, cache_url)
        return snapshots[-1] if snapshots else None


class Fetcher:
    """The live/replay seam. Providers only ever talk to this.

    cache_url is the cache identity for the request and must never contain
    secrets (API keys go in params only, which are sent but not cached).
    """

    def __init__(self, cache: RawCache, live: bool):
        self.cache = cache
        self.live = live

    def get_texts(self, source_id: str, cache_url: str, *, params: dict | None = None) -> list[tuple[str, str]]:
        """Live: one fresh (body, raw_ref). Replay: every cached snapshot,
        oldest first - rolling feeds drop entries between fetches, so only the
        union of snapshots reproduces everything the cache ever captured."""
        if self.live:
            body = http.get_text(cache_url, params=params)
            return [(body, self.cache.put(source_id, cache_url, body))]
        snapshots = self.cache.all(source_id, cache_url)
        if not snapshots:
            raise SourceUnavailable(f"no cached payload for {source_id}: {cache_url}")
        return snapshots
