# Model Governance

## Model card

| Role | Provider | Model ID | Notes |
|---|---|---|---|
| Primary | Groq | `openai/gpt-oss-120b` | strict JSON schema decoding, temperature 0 |
| Fallback | Gemini | `gemini-2.5-flash` | Pydantic-only schema enforcement, temperature 0 |

Both model IDs are pinned in `config.toml` under `[llm]` and never resolved as
"latest". A pinned ID means the same prompt produces comparable output across
runs, cached responses stay valid for replay indefinitely, and a provider
cannot silently change model behavior underneath the pipeline. Provider
selection and the pinned IDs are defined in `ci_tool/models.py`
(`LLMConfig`); the HTTP calls live in `ci_tool/llm.py`.

## Prompt versioning

`prompts/extract.md` is content-addressed: its `prompt_version` is the first
12 hex characters of its own sha256 (currently `55bea48e75b4`). This value is:

- stored on every insight row in the database, so any extraction can be
  traced back to the exact prompt text that produced it
- implied by the LLM response cache key (`ci_tool/llm.py` hashes the full
  prompt text alongside provider and model), so a cached response is only
  ever reused for the exact prompt that generated it

Editing `prompts/extract.md` changes its hash, minting a new
`prompt_version`. Old cached responses remain valid and replayable under
their original version; they are never reinterpreted under the new prompt.

## Task-to-tier mapping

| Task | Handled by |
|---|---|
| Ingest, parse, normalize | deterministic code |
| Relevance filtering, dedup | deterministic code |
| Clustering, ranking | deterministic code |
| Grounding / verbatim checks | deterministic code (`ci_tool/grounding.py`) |
| Confidence scoring | deterministic code (trust tier + corroboration count) |
| Schema-filling extraction | LLM, one call per cluster |

The LLM is invoked for exactly one task: filling `InsightExtraction` for
clusters that have already passed every deterministic gate (source
allowlist, dedup, recency, entity match). It never decides what enters the
pipeline, never controls branching, and never runs in a loop.

Each extraction call is validated against the schema, then checked
word-for-word against the source text (`ci_tool/grounding.py`): quote,
entities, and numbers must appear verbatim in the source. A failure on
either check triggers exactly one re-ask with the errors appended to the
prompt. If the re-ask also fails, the item is quarantined with the raw
model output and the failure reasons, and the run report counts it
(`ci_tool/analyze.py::analyze`). Nothing is coerced or dropped silently;
failure always fails closed.

## Vendor data terms (as of 2026-08)

- **Groq**: Services Agreement section 4.2 states customer API data is not
  used for model training. Groq is the primary provider and the one used for
  production extraction.
- **Google Gemini (free tier)**: prompt content submitted on the free tier
  may be used for training. For this reason Gemini is restricted to
  development and experimentation in this pipeline and is never used to
  process production data.
- **Recommendation**: if Gemini is adopted for production use, move to a
  paid tier with no-training terms, or another provider with an equivalent
  no-training clause, before sending real source content.

## Data classes

- **Public web content**: the only class of data the pipeline ingests
  (RSS feeds, GitHub release notes, news API results). No private or
  customer data passes through this system.
- **API keys**: read from `.env` / environment variables only. They are
  never written into cache files or used as part of a cache key
  (`ci_tool/cache.py`: cache identity is the request URL, keys travel as
  request params only and are excluded from what gets cached).
- **Quarantine payloads**: may contain raw model output. They are stored
  locally only, alongside the failure reasons that caused quarantine, and
  are not transmitted anywhere else.
