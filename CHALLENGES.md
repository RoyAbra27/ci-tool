# Challenges

Honest notes from building the pipeline: what broke, why, and what changed.

## Groq 429 burn on the first live run

The first live run against the LLM stage burned 25 API calls, all 429s,
before the extraction call was routed through the shared HTTP layer.
`ci_tool/http.py` already existed for ingest sources (RSS, GitHub releases)
with bounded retries and `Retry-After` handling, but the Groq call was
written as its own thing and didn't use it - so instead of backing off, it
kept firing the retry loop straight into the rate limit.

Fix: `_groq` and `_gemini` now go through `http.post_json`, which reads
`Retry-After` off a 429 and sleeps that long, capped at 90s, before the
next attempt - see `ci_tool/http.py:_retry_delay`.

Lesson: a shared retry-aware HTTP layer only helps if it's the *only* way
anything in the package talks to the network, from the first line of a new
call site - not something migrated to after burning quota on the first
live run.

## The `.env` comment gotcha

`.env.example` ships every key commented out, e.g. `#NEWSDATA_API_KEY=`.
Keys got pasted in after the `=` but the leading `#` was never removed:
`#NEWSDATA_API_KEY=actualkeyvalue`. `ci_tool/env.py` is a deliberately tiny
loader - skip blanks and comment lines, nothing else - so a line starting
with `#` is a comment, full stop, and the key never reached `os.environ`.

A live NewsData fetch ran, returned nothing, and there was no error to
chase: a missing key is treated as "skip this optional source," which is
correct for a genuinely absent key but looks identical to a malformed one.
The cause was only found later, by checking stderr for the skip line.

Lesson: silent-skip logic for optional config is right, but it means
misconfiguration doesn't surface as an error - it surfaces as inexplicably
empty output on a run that otherwise looks healthy. The loader now warns
on stderr at startup for exactly these shapes (commented-out line carrying
a value, empty assignment, comment-shaped value) instead of leaving them
to be inferred from an empty result set.

## The Snyk feed that never gets shorter

`snyk-blog` is RSS, and RSS feeds are supposed to be "recent entries only."
Snyk's returns the full blog archive on every fetch. Two things handle it
together: `recency_days` in `run_chain` (`ci_tool/filters.py`) drops
anything older than the cutoff before dedup ever sees it, and `trust_tier =
3` on the source routes it through the entity matcher, so even a fresh
Snyk post that doesn't mention a tracked competitor gets gated out.

That works, but it leans on `trust_tier` for two different jobs at once:
how much we trust a source's claims, and whether a source needs topic
filtering because it isn't scoped to us. A full-archive feed from an
otherwise-trusted source still needs the topic gate, and the current tier
field can't say that without also saying "trust this less." See ROADMAP.

## NULL competitor crash in the daily digest

A review pass surfaced a crash in the daily digest: any insight with a
NULL `competitor` (industry news not tied to a tracked competitor) took
the UI down. Root cause, in `ui/app.py`: `groupby("competitor",
dropna=False)` turns SQL NULL into pandas NaN, and the sort key used `k or
""` to handle it - but `NaN or ""` evaluates to `NaN` (NaN is truthy), so a
float sort key ended up compared against string competitor names, which
raises.

Fixed in `716f7f3`: name the NaN before sorting
(`insights["competitor"].fillna("")`) instead of special-casing it inline
during comparison.

Lesson: `competitor` is nullable by design - not every insight is about a
tracked competitor. Every downstream reader of that column, including
derived views like the digest, has to handle every nullable value the
schema allows, not just the happy path.
