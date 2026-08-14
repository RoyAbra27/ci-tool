"""Pipeline entry: fetch (live or replay), filter, fingerprint, cluster, store.
One linear pass; a broken source is a counted status line, never a dead run."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from ci_tool import db, filters, fingerprint, providers
from ci_tool.cache import Fetcher, RawCache, SourceUnavailable
from ci_tool.models import load_config


def run(*, live: bool, config_path: str = "config.toml") -> dict:
    cfg = load_config(config_path)
    root = Path(config_path).resolve().parent
    fetcher = Fetcher(RawCache(root / cfg.settings.raw_dir), live)
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%SZ")

    items = []
    source_status: dict[str, str] = {}
    for source in cfg.sources:
        try:
            fetched = providers.fetch(source, fetcher)
            items.extend(fetched)
            source_status[source.id] = f"ok:{len(fetched)}"
        except SourceUnavailable:
            source_status[source.id] = "no_cache"
        except Exception as e:
            source_status[source.id] = f"error:{type(e).__name__}:{e}"[:200]

    conn = db.connect(root / cfg.settings.db_path)
    try:
        seen_ids, seen_urls = db.seen_keys(conn)
        passed, counters = filters.run_chain(
            items,
            now=now,
            recency_days=cfg.settings.recency_days,
            seen_ids=seen_ids,
            seen_urls=seen_urls,
            matcher=filters.build_matcher(cfg.aliases()),
        )

        since = (now - timedelta(days=cfg.settings.cluster_window_days)).isoformat()
        known = db.recent_fingerprints(conn, since)
        clustered = 0
        with conn:
            for item in passed:
                fp = fingerprint.fingerprint(f"{item.title} {item.text}")
                cluster_id = item.content_hash()
                if fp:
                    for other_fp, other_cluster in known:
                        if fingerprint.similarity(fp, other_fp) >= fingerprint.CROSSLIST_THRESHOLD:
                            cluster_id = other_cluster
                            clustered += 1
                            break
                db.insert_item(conn, item, fp, cluster_id, run_id)
                known.append((fp, cluster_id))

            counters["clustered"] = clustered
            counters["sources_ok"] = sum(1 for v in source_status.values() if v.startswith("ok"))
            counters["sources_failed"] = len(source_status) - counters["sources_ok"]
            db.add_run(conn, run_id, "live" if live else "replay", counters)
    finally:
        conn.close()

    return {
        "run_id": run_id,
        "mode": "live" if live else "replay",
        "sources": source_status,
        "counters": counters,
    }
