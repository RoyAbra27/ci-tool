# ci-tool

Competitive intelligence pipeline: deterministic ingest -> filter -> dedup -> bounded LLM extraction -> SQLite -> Streamlit UI.

## Commands

- `uv run pytest -q` - full test suite; must pass before any commit
- `uv run python -m ci_tool run --live --summary` - fetch sources, update raw cache, ingest
- `uv run python -m ci_tool run --summary` - replay from cache, zero network, zero keys
- `uv run python -m ci_tool analyze --live --summary` - LLM extraction stage (needs GROQ_API_KEY; caches responses)
- `uv run python -m ci_tool analyze --summary` - LLM stage from cached responses
- `uv run python eval/run_eval.py` - score pipeline against eval/labels.json (regenerate the frozen sample with `uv run python eval/build_sample.py > eval/sample.json`)

## Doctrine (do not violate)

- Files are canonical (data/raw), SQLite (data/ci.db) is derived and safe to delete.
- Deterministic code decides what enters, groups, ranks; the LLM only fills `InsightExtraction` for what already passed. No agentic loops, no model-decided control flow.
- Fail closed: schema or grounding failure -> one re-ask -> quarantine table + run report. Never coerce, never silently drop.
- A broken source or provider is a counted status line, never a dead run.
- Secrets never enter cache files or cache keys (apikey in params only).

## Conventions

- No em-dashes in any file; use hyphens.
- Comments only where they carry a constraint the code cannot show; cite incidents where relevant.
- Every behavior change lands with tests in the same change.
- Conventional commits (feat:/fix:/refactor:/docs:/test:/chore:), no Co-Authored-By trailers.
- Pinned model IDs only, never "latest" (config.toml [llm]).
