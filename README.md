# ci-tool

A competitive intelligence pipeline for JFrog's CI team. Deterministic code decides what enters (source allowlist, recency, dedup, entity rules) and how items group; a schema-confined LLM only compresses what already passed, and every claim it makes is mechanically verified against the source text or quarantined. The result is a daily digest where every line has a verbatim quote, a source link, and a computed confidence.

## Quickstart (no API keys needed)

```bash
git clone <this repo>
cd ci-tool
uv sync
uv run python -m ci_tool run        # ingest, replayed from the bundled raw cache
uv run python -m ci_tool analyze    # LLM stage, replayed from cached responses
uv run streamlit run ui/app.py      # web UI at http://localhost:8501
```

Replay mode is the default everywhere: the repo ships its raw inputs (`data/raw/`), so the full pipeline and UI run offline with zero keys. The SQLite file is derived and safe to delete; it rebuilds from the cache.

## Live mode (optional)

Copy `.env.example` to `.env`, fill any keys you have, then add `--live`:

```bash
uv run python -m ci_tool run --live      # fetch feeds, update the raw cache
uv run python -m ci_tool analyze --live  # call the LLM for new clusters (GROQ_API_KEY)
```

## The web UI

Four views, reading only from SQLite:

1. **Daily digest** - the morning read: clustered insights per competitor, each with category, JFrog-theme tags, computed confidence, and the verbatim evidence quote.
2. **Competitor timeline** - chronological events and a competitor-by-category count matrix (counts, deliberately no scores).
3. **Item explorer** - every ingested item with full provenance: source, trust tier, content hash, raw cache file, and the insight it produced.
4. **Run report** - per-filter drop counters for every run, plus the quarantine: LLM outputs that failed schema or grounding verification, kept out of the digest by design.

## How it decides (short version)

```
feeds/APIs -> raw cache (files, canonical) -> deterministic filters -> SimHash clustering
          -> LLM extraction (fixed schema) -> mechanical grounding checks -> SQLite -> UI
                                                   |__ fail twice -> quarantine + run report
```

Docs: ARCHITECTURE.md, DECISIONS.md, ROADMAP.md, CHALLENGES.md, EVALUATION.md, MODEL-GOVERNANCE.md, SOURCES.md (see repo root).

## Tests

```bash
uv run pytest -q
```
