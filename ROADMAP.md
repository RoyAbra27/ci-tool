# Roadmap

Deferred work, tagged with why it's deferred and when it becomes worth
doing. Nothing here is missing by accident.

## Embeddings for near-dup / clustering

**Deferred.** SimHash (parameters in ARCHITECTURE.md) is a zero-dependency,
near-verbatim duplicate detector, and that's what the pipeline sees today:
the same press release or blog post cross-posted across feeds, not
paraphrased coverage of the same event.

**Revisit when:** cross-source paraphrase duplicates start showing up -
two sources covering the same announcement in their own words, which
SimHash's shingle overlap won't catch. At current volume (~2k raw items
per run, ~30 passing all filters) that hasn't happened yet.

## Paid LLM tier

**Deferred.** The free-tier Groq model (`openai/gpt-oss-120b`) handles the
extraction volume and latency the pipeline sees today.

**Revisit when:** run volume or latency requirements outgrow what the free
tier delivers.

## Provider-swap demo (Gemini)

**Deferred, code done.** `ci_tool/llm.py` already has a `_gemini` path
alongside `_groq`, selected by `[llm].provider` in config - the seam is
one function per provider behind a shared interface, not per-provider
branching in the caller. What's missing is a `GEMINI_API_KEY` to actually
run it live and confirm the swap end to end.

**Revisit when:** a Gemini key is available to demonstrate the swap.

## `trust_tier` naming cleanup

**Deferred.** Tier currently does two jobs: how much to trust a source's
claims (1 = vendor's own words, 2 = official platform changelogs, 3 =
third-party news), and whether a source needs topic filtering because it
isn't scoped to a single competitor by construction. Those are different
axes - see the Snyk feed writeup in CHALLENGES.md for where that
conflation shows up in practice.

**Revisit when:** a source needs "trusted but unscoped" or "scoped but
low-trust" - the first source that doesn't fit the current tier cleanly.

## Full-text retrieval for tier-3 gating

**Deferred.** The product-alias fix the eval motivated is applied (2026-08-15:
`evo` added for Snyk; before/after in EVALUATION.md). The residual gate miss
is a relevant Snyk research post whose full text names neither company nor
product - no alias can catch it. The next rung is fetching article full text
for tier-3 items before the entity gate, which costs a fetch per candidate
and a paid news tier.

**Revisit when:** measured misses justify the fetch cost; one residual miss
in 40 items does not.

## NewsData industry-news coverage tuning

**Partially validated.** The first fully-live run (2026-08-15, 9/9 sources
ok) confirmed the provider works end to end: 10 articles fetched, cached,
and filtered. None passed the entity gate that run - general industry news
rarely names a tracked competitor in its snippet, and the free tier is
snippet-only. The channel is mechanically proven but not yet contributing
digest items.

**Revisit when:** the query terms are broadened per competitor product
names (e.g. "Evo", now that the entity gate tracks it) or a full-text news
tier is justified; measure contribution per run before paying for either.

## Streamlit `st.logo` wordmark polish

**Deferred.** Cosmetic - the UI theme and layout work, the wordmark
treatment in the sidebar logo isn't tuned.

**Revisit when:** UI polish passes are prioritized over pipeline work.
