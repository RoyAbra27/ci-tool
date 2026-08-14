# Evaluation

Deterministic, reproducible scoring of the pipeline against a hand-labelled
sample. No LLM judges anything here; every metric is computed by
`eval/run_eval.py` from frozen inputs.

> Label status: drafted 2026-08-14, pending a second human review pass.
> Numbers below regenerate with `python eval/run_eval.py` after any label edit.

## Method

- Sample: 40 items frozen in `eval/sample.json`, drawn by `eval/build_sample.py`
  from the committed raw cache: all 31 items that passed the filter chain, all
  5 entity-matcher rejections, both batch duplicates, and the 2 newest
  recency-window rejections.
- Labels: `eval/labels.json` records ground truth per item: relevant y/n
  (content-based, independent of recency), category from the fixed code
  taxonomy, and dup pairs. Labelling was done blind to the LLM's output but
  with the pipeline verdict visible, by the same person who built the
  pipeline - a bias worth naming.
- Reproduce: `python eval/build_sample.py > eval/sample.json` then
  `python eval/run_eval.py` (replay mode, no API keys needed).

## Results (2026-08-14 sample)

| Metric | Value | Detail |
|---|---|---|
| Ingest gate precision | 0.74 | 23 of 31 passed items are CI-relevant |
| Gate misses (false negatives) | 3 of 5 rejects | all three are Snyk "Evo" posts |
| Dedup correctness | 2/2 caught, 0 false | ja-jp mirror URLs of GitLab patch notes |
| Classification accuracy | 0.90 | 27 of 30 insights match the labelled category |
| Quote-back faithfulness | 1.00 | every insight quote appears verbatim in its source |
| Quarantined | 1 | fail-closed grounding rejection, see below |

## Failure modes, honestly

**Tier 1-2 sources pass unconditionally, so marketing passes too.** The 8
false positives are all first-party blog posts (thought leadership, event
previews, an educational listicle). The gate deliberately trusts tier 1-2
feeds for recall; the extraction stage then categorized 7 of the 8 as
`marketing_content` or routine `product_release` (the eighth became `other`),
and the UI surfaces those categories as badges. Nothing demotes them yet -
category-aware digest ranking is a ROADMAP item. The precision number is the
honest cost of that recall-first choice.

**The entity matcher misses product names.** Three genuinely relevant Snyk
posts (an Evo case study, a rebuilt Evo risk-scoring capability, and keyv
compromise research) were rejected because their title and snippet never
contain the token "snyk" - only "Evo". Tier 3 sources are gated on tracked
entity names, and the alias list holds company names, not product names.
The one-line fix (add product aliases per competitor) is deliberately not
applied before publishing this eval; it is queued in ROADMAP.md.

**Classification mismatches are taxonomy-boundary cases, not hallucinations.**
All three: a Black Hat conference recap (model: `other`, label:
`marketing_content`), the Artifactory + Google Artifact Registry integration
(model: `product_release`, label: `partnership`), and a model-deprecation
notice (model: `marketing_content`, label: `product_release`). Each is
defensible either way; none invents facts.

**The quarantine caught a real grounding failure.** One extraction summarized
a Nexus release with the date "2026-08-06" written as separate numbers that do
not appear in the source text. The deterministic number-grounding check
rejected it after one bounded re-ask and quarantined it instead of publishing
a plausible-looking but unverifiable claim. This is the fail-closed path
working as designed, on real data.

## Limitations

- 40 items from one week of feed data; small enough that single labels move
  precision by 3 points.
- One labeller, who also wrote the filter chain. A second reviewer pass is
  planned before the labels are considered frozen.
- Dedup ground truth contains only exact-content mirrors; no cross-source
  paraphrase pairs occurred in the window, so SimHash clustering (as opposed
  to exact hashing) is untested by this sample.
- Summary faithfulness is measured by verbatim quote-back plus the grounding
  checks; it does not score summary completeness or emphasis.
