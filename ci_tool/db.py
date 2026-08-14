"""SQLite derived index. Files under data/raw are canonical; this DB is safe
to delete and rebuilds from them. The events table is append-only provenance."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ci_tool.models import RawItem

DDL = """
CREATE TABLE IF NOT EXISTS items(
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  trust_tier INTEGER NOT NULL,
  competitor TEXT,
  url TEXT NOT NULL,
  title TEXT NOT NULL,
  text TEXT NOT NULL DEFAULT '',
  published_at TEXT,
  fetched_at TEXT NOT NULL,
  fingerprint TEXT NOT NULL DEFAULT '',
  cluster_id TEXT NOT NULL,
  raw_ref TEXT NOT NULL,
  run_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_url ON items(url);
CREATE INDEX IF NOT EXISTS idx_items_cluster ON items(cluster_id);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id TEXT NOT NULL,
  event TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '',
  ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quarantine(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ref_id TEXT NOT NULL,
  stage TEXT NOT NULL,
  error TEXT NOT NULL,
  payload TEXT NOT NULL DEFAULT '',
  ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS insights(
  cluster_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  summary TEXT NOT NULL,
  category TEXT NOT NULL,
  themes TEXT NOT NULL,
  entities TEXT NOT NULL,
  numbers TEXT NOT NULL,
  quote TEXT NOT NULL,
  confidence TEXT NOT NULL,
  competitor TEXT,
  item_count INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs(
  run_id TEXT PRIMARY KEY,
  ts TEXT NOT NULL,
  mode TEXT NOT NULL,
  counters TEXT NOT NULL
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    return conn


def seen_keys(conn: sqlite3.Connection) -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    urls: set[str] = set()
    for row in conn.execute("SELECT id, url FROM items"):
        ids.add(row["id"])
        urls.add(row["url"])
    return ids, urls


def recent_fingerprints(conn: sqlite3.Connection, since_iso: str) -> list[tuple[str, str]]:
    return [
        (row["fingerprint"], row["cluster_id"])
        for row in conn.execute(
            "SELECT fingerprint, cluster_id FROM items"
            " WHERE fingerprint != '' AND fetched_at >= ?",
            (since_iso,),
        )
    ]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_event(conn: sqlite3.Connection, item_id: str, event: str, detail: str = "") -> None:
    conn.execute(
        "INSERT INTO events(item_id, event, detail, ts) VALUES(?,?,?,?)",
        (item_id, event, detail, _now()),
    )


def insert_item(
    conn: sqlite3.Connection, item: RawItem, fingerprint: str, cluster_id: str, run_id: str
) -> None:
    item_id = item.content_hash()
    conn.execute(
        "INSERT OR IGNORE INTO items"
        "(id, source_id, trust_tier, competitor, url, title, text,"
        " published_at, fetched_at, fingerprint, cluster_id, raw_ref, run_id)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            item_id, item.source_id, item.trust_tier, item.competitor,
            item.url, item.title, item.text,
            item.published_at.isoformat() if item.published_at else None,
            item.fetched_at.isoformat(), fingerprint, cluster_id, item.raw_ref, run_id,
        ),
    )
    add_event(conn, item_id, "ingested", f"run={run_id} source={item.source_id}")


def unanalyzed_clusters(conn: sqlite3.Connection) -> dict[str, list[sqlite3.Row]]:
    """Clusters with no insight yet; quarantined clusters stay out until a
    human looks at them (they are visible in the run report, not retried)."""
    clusters: dict[str, list[sqlite3.Row]] = {}
    for row in conn.execute(
        "SELECT * FROM items"
        " WHERE cluster_id NOT IN (SELECT cluster_id FROM insights)"
        "   AND cluster_id NOT IN (SELECT ref_id FROM quarantine WHERE stage = 'extract')"
        " ORDER BY published_at"
    ):
        clusters.setdefault(row["cluster_id"], []).append(row)
    return clusters


def quarantine_add(conn: sqlite3.Connection, ref_id: str, stage: str, error: str, payload: str) -> None:
    conn.execute(
        "INSERT INTO quarantine(ref_id, stage, error, payload, ts) VALUES(?,?,?,?,?)",
        (ref_id, stage, error, payload, _now()),
    )


def add_insight(conn: sqlite3.Connection, **fields) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO insights"
        "(cluster_id, run_id, provider, model, prompt_version, summary, category,"
        " themes, entities, numbers, quote, confidence, competitor, item_count, created_at)"
        " VALUES(:cluster_id, :run_id, :provider, :model, :prompt_version, :summary,"
        " :category, :themes, :entities, :numbers, :quote, :confidence, :competitor,"
        " :item_count, :created_at)",
        {**fields, "created_at": _now()},
    )


def add_run(conn: sqlite3.Connection, run_id: str, mode: str, counters: dict) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO runs(run_id, ts, mode, counters) VALUES(?,?,?,?)",
        (run_id, _now(), mode, json.dumps(counters, ensure_ascii=False)),
    )
