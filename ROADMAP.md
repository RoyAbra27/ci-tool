# Roadmap

Deferred work, tagged with why it's deferred and when it becomes worth
doing. Nothing here is missing by accident.

## Daily "what changed" delta view

**Next up.** The digest is already daily; the next step is making the
change explicit: an analyst opens the tool and sees only what is new since
yesterday - new insights, new quarantines, sources that went quiet. All
inputs exist (insights and runs are timestamped per run), so this is a
diff over two days of already-verified rows, no new model calls.

**Revisit when:** immediately - this is the first post-review feature.

## Category-aware digest ranking and release roll-up

**Deferred.** The digest already sinks marketing content below product and
security events, but within a band every verified event gets equal billing.
Observed cost (2026-08-17): three consecutive cloudsmith-cli patch releases
(v1.21-v1.23) each took a full digest card. The next rung is a deterministic
roll-up - consecutive releases of the same repo collapse into one line with
the latest release on top - plus per-category weights in the sort.

**Revisit when:** a digest day carries more than a handful of same-repo
release items; the roll-up rule is a pure function over rows the digest
already has.

## Usage measurement

**Deferred.** Two counters per week: digest items marked reviewed or
flagged, and corrections submitted. Corrections double as new eval labels,
so usage directly grows the labelled set. If review counts hit zero the
tool is dead and the run report should say so.

**Revisit when:** the tool has a second regular user - measurement of one
person's own usage proves nothing.

## Grounded Q&A over the verified archive ("ask the archive")

**Deferred.** A chat interface over insights the pipeline has already
verified - "what has Sonatype shipped on SBOM this year?" - under the same
rules as the digest: the model may only compose answers from retrieved
insight rows, every claim keeps its verbatim quote and link, and a question
the archive cannot support gets "not in the archive", not an improvisation.
Retrieval starts deterministic (SQL over category, competitor, theme,
date - the corpus is hundreds of rows, not millions); embeddings enter only
under the promotion condition below.

**Revisit when:** the archive spans months and analysts ask historical
questions (QBR prep is the concrete trigger). Until then the timeline view
answers the same questions by eye.

## MCP server over the corpus

**Deferred.** Expose the verified corpus (insights, items, provenance,
quarantine) as MCP tools, so assistants and internal agents query verified,
quote-backed competitor facts instead of the raw web. The schema already
carries what a consuming agent needs to stay honest: quote, source URL,
computed confidence, prompt version. This is the integration shape JFrog
itself ships for its platform, applied to the CI corpus.

**Revisit when:** anything other than the Streamlit UI wants programmatic
access - a second consumer is the trigger.

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
