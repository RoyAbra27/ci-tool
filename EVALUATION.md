# Evaluation

Deterministic, reproducible scoring of the pipeline against a hand-labelled
sample. No LLM judges anything here; every metric is computed by
`eval/run_eval.py` from frozen inputs.

> Label status: drafted 2026-08-14, independently reviewed and frozen
> 2026-08-15 (all 11 pipeline disagreements upheld on review). Numbers below
> regenerate with `python eval/run_eval.py` after any label edit.
>
> Gate update 2026-08-15: the product-alias fix this eval motivated (see
> "before and after" below) has been applied; labels were not touched.
> Prompt update 2026-08-15: category calibration v2 (see "Prompt v2"
> below); labels still untouched.

## Method

- Sample: 40 items frozen in `eval/sample.json`, drawn by `eval/build_sample.py`
  from the committed raw cache: all 31 items that passed the 2026-08-14 filter
  chain, all 5 of its entity-matcher rejections, both batch duplicates, and
  the 2 newest recency-window rejections.
- Labels: `eval/labels.json` records ground truth per item: relevant y/n
  (content-based, independent of recency), category from the fixed code
  taxonomy, and dup pairs. Labelling was done blind to the LLM's output but
  with the pipeline verdict visible, by the same person who built the
  pipeline - a bias worth naming.
- Reproduce: `python eval/run_eval.py` (replay mode, no API keys needed).
  Reproducibility is clock-independent: the sample generator pins its NOW
  and the pipeline's replay recency window anchors to the same instant
  (`replay_anchor` in config.toml), so a database rebuilt from the cache on
  any date yields these numbers exactly.
  The sample's *composition* is frozen from the 2026-08-14 cache; the live
  feeds have since rolled, so `build_sample.py` against today's cache yields
  a different item set. When the gate changed on 2026-08-15 the frozen
  items' verdicts were recomputed with the same code over the full cached
  text, keeping the before/after comparison on identical items.

## Results: before and after the product-alias fix

The 2026-08-14 numbers measured the gate with company-name aliases only.
Their headline finding (relevant Snyk posts that only say "Evo" slip past
the tier-3 gate) motivated a one-line config fix: `evo` added to Snyk's
alias list. Both measurements, same 40 items, same labels:

| Metric | Before (2026-08-14) | After alias fix (2026-08-15) |
|---|---|---|
| Ingest gate precision | 0.74 (23 of 31 passed) | 0.76 (25 of 33 passed) |
| Gate misses (false negatives) | 3 of 5 rejects | 1 of 3 rejects |
| Dedup correctness | 2/2 caught, 0 false | unchanged |
| Classification accuracy | 0.90 (27 of 30) | 0.84 (27 of 32) |
| Quote-back faithfulness | 1.00 | 1.00 |
| Quarantined | 1 | 1 |

The fix recovered 2 of the 3 misses and introduced no false positives. The
residual miss (the keyv npm compromise research) contains neither "snyk"
nor "evo" anywhere in its full cached text; catching it needs full-text
retrieval or semantics, not another alias (ROADMAP.md). Classification
accuracy *dropped* because both recovered posts were then misclassified by
the model - two new taxonomy-boundary cases, discussed below. That is the
honest trade: the gate fix surfaced harder items for the next stage.

## Prompt v2: category calibration

All five post-alias mismatches traced to the same cause: the prompt's
calibration block covered only 3 of the 9 categories. `partnership` was
never mentioned, lifecycle changes (deprecations) had no home, and nothing
separated event recaps or vendor case studies from original research.
Prompt v2 (`0d7fc218bf8e`, was `55bea48e75b4`) adds three calibration
rules for exactly those gaps; every cluster was re-extracted live and
re-scored against the same 40 items and unchanged labels:

| Metric | Prompt v1 | Prompt v2 |
|---|---|---|
| Classification accuracy | 0.84 (27 of 32) | 0.91 (29 of 32) |
| Quote-back faithfulness | 1.00 | 1.00 |
| Quarantined | 1 | 1 (same cluster, same invented date) |

Gate and dedup numbers are prompt-independent and did not move. Of the
five v1 mismatches, three fixed (the Black Hat recap, the Artifactory +
Google integration, the model-deprecation notice), two survived (both Evo
posts, discussed below), and the new partnership rule introduced one
regression: a Gemini-model-availability changelog inside GitHub Copilot
now reads as `partnership` (label: `product_release`) - the rule overshoots
when one company's model ships inside another company's product. Net 5
mismatches to 3. The same Nexus cluster quarantined again under v2 for the
same fabricated date, so the fail-closed path reproduces across prompt
versions.

**A v3 was attempted and reverted.** One added rule targeted the
partnership regression ("one vendor adding a third-party model to its own
product is product_release"). Measured on a full re-extraction: the
targeted item still classified as `partnership`, accuracy stayed flat
(28/31 judged), and quarantines tripled (1 to 3, two new paraphrased-quote
grounding failures) - the longer calibration made extraction noisier
without fixing its target. v3 was reverted; v2 is the shipped prompt. The
remaining three mismatches are boundary judgments, and further prompt
tuning against a 32-item labelled set would be fitting the test set, so
prompt iteration stops here.

## Failure modes, honestly

**Tier 1-2 sources pass unconditionally, so marketing passes too.** The 8
false positives are all first-party blog posts (thought leadership, event
previews, an educational listicle). The gate deliberately trusts tier 1-2
feeds for recall; the extraction stage then categorized 7 of the 8 as
`marketing_content` or routine `product_release` (the eighth became `other`),
and the UI surfaces those categories as badges and sinks `marketing_content`
and `other` to the bottom of each competitor's digest group (2026-08-15).
The precision number is the honest cost of that recall-first choice.

**The entity matcher missed product names (now fixed, partially).** Three
genuinely relevant Snyk posts (an Evo case study, a rebuilt Evo risk-scoring
capability, and keyv compromise research) were rejected because the alias
list held company names, not product names. Adding `evo` recovered the two
Evo posts; the keyv research names neither company nor product in its full
cached text and remains the measured cost of gating tier-3 sources on
entity mentions in the snippet the feed provides.

**Classification mismatches are taxonomy-boundary cases, not hallucinations.**
Under prompt v2, three remain. The two Evo posts resisted the calibration:
a customer case study built around security findings still reads as
`security_research` (label: `marketing_content`), and a rebuilt-capability
announcement still reads as `marketing_content` (label: `product_release`) -
Snyk's own framing genuinely blurs those lines. The third is the v2
regression named above (Gemini in Copilot as `partnership`). Each is
defensible either way; none invents facts. The five v1 mismatches and what
fixed them are in the prompt v2 section.

**The quarantine caught a real grounding failure.** One extraction summarized
a Nexus release with the date "2026-08-06" written as separate numbers that do
not appear in the source text. The deterministic number-grounding check
rejected it after one bounded re-ask and quarantined it instead of publishing
a plausible-looking but unverifiable claim. This is the fail-closed path
working as designed, on real data.

**A second, different failure class (2026-08-17 live run).** A newly fetched
Cloudsmith post passed the gate, but the model returned an empty extraction
(blank summary and quote); schema validation rejected it twice and it was
quarantined. The comparison tables above report quarantine counts at
measurement time (1); the shipped cache now replays 2 - the invented date
and the empty extraction - covering both failure shapes: fabrication and
refusal-shaped emptiness.

## Limitations

- 40 items from one week of feed data; small enough that single labels move
  precision by 3 points.
- The initial labels were drafted by one party close to the pipeline; a
  second reviewer then examined every disagreement with the pipeline and
  upheld all 11 before the freeze. Deeper mitigation (an independent
  labeller for the full set) remains future work.
- Dedup ground truth contains only exact-content mirrors; no cross-source
  paraphrase pairs occurred in the window, so SimHash clustering (as opposed
  to exact hashing) is untested by this sample.
- Summary faithfulness is measured by verbatim quote-back plus the grounding
  checks; it does not score summary completeness or emphasis.
