# Roadmap

Deferred work, tagged with why it's deferred and when it becomes worth
doing. Nothing here is missing by accident.

## Embeddings for near-dup / clustering

**Deferred.** SimHash (64-bit, 3-token shingles, 0.92 similarity threshold
- at most 5 of 64 bits differ, see `ci_tool/fingerprint.py`) is a
zero-dependency, near-verbatim duplicate detector, and that's what the
pipeline sees today: the same press release or blog post cross-posted
across feeds, not paraphrased coverage of the same event.

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

## Product-name aliases for the tier-3 entity matcher

**Deferred.** The alias list in `config.toml` holds company names only, so a
tier-3 post about a tracked competitor's *product* that never names the
company slips past the gate. The eval measured this: 3 of 5 entity-matcher
rejections were relevant Snyk posts that only say "Evo" (see EVALUATION.md).
The fix is one alias line per competitor product; it is deliberately left
unapplied so the published eval reflects the gate as measured.

**Revisit when:** the current eval numbers have served their purpose; apply
together with a re-run of `eval/run_eval.py` and refreshed EVALUATION.md.

## Category-aware digest ranking

**Deferred.** Tier 1-2 sources pass the gate unconditionally (recall-first
by design), so first-party marketing lands in the digest alongside product
news. The extraction stage already labels it (`marketing_content`), and the
UI shows category badges, but nothing demotes or folds those items yet.

**Revisit when:** digest readers report noise; the demotion is a sort key
on the existing category column, no new data needed.

## NewsData industry-news coverage tuning

**Partially validated.** The first fully-live run (2026-08-15, 9/9 sources
ok) confirmed the provider works end to end: 10 articles fetched, cached,
and filtered. None passed the entity gate that run - general industry news
rarely names a tracked competitor in its snippet, and the free tier is
snippet-only. The channel is mechanically proven but not yet contributing
digest items.

**Revisit when:** the query terms are broadened per competitor product
names (same fix as the alias item above) or a full-text news tier is
justified; measure contribution per run before paying for either.

## Streamlit `st.logo` wordmark polish

**Deferred.** Cosmetic - the UI theme and layout work, the wordmark
treatment in the sidebar logo isn't tuned.

**Revisit when:** UI polish passes are prioritized over pipeline work.
