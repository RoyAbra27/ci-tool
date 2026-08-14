"""Score the pipeline against eval/labels.json. Reads the frozen sample
(eval/sample.json, produced by build_sample.py) for pipeline verdicts and
data/ci.db for LLM insights. Prints a metrics JSON to stdout.

Metrics: ingest-gate relevance (precision over passed, misses among
irrelevant rejects; stale rejects are a recency call, excluded), dedup
correctness (labelled dup pairs vs dup_batch verdicts), classification
accuracy (LLM category vs label), and quote-back faithfulness (each
insight's quote must appear verbatim in its source item text)."""

import json
import sqlite3
import sys


def gate_metrics(labels, verdicts):
    passed = [l for l in labels if verdicts.get(l["url"]) == "passed"]
    rejected = [l for l in labels if verdicts.get(l["url"]) == "irrelevant"]
    relevant_passed = sum(1 for l in passed if l["relevant"] == "y")
    return {
        "passed": len(passed),
        "passed_relevant": relevant_passed,
        "precision": round(relevant_passed / len(passed), 3) if passed else None,
        "irrelevant_rejects": len(rejected),
        "missed_relevant": [l["url"] for l in rejected if l["relevant"] == "y"],
    }


def dedup_metrics(labels, verdicts):
    dup_labelled = [l for l in labels if l["dup_of"]]
    caught = [l for l in dup_labelled if verdicts.get(l["url"]) == "dup_batch"]
    false_dups = [
        l["url"] for l in labels
        if not l["dup_of"] and verdicts.get(l["url"]) == "dup_batch"
    ]
    return {
        "labelled_dups": len(dup_labelled),
        "caught": len(caught),
        "false_dups": false_dups,
    }


def classification_metrics(labels, category_by_id):
    # dup mirrors share the original's content hash and would double-count it
    judged = [l for l in labels if l["id"] in category_by_id and not l["dup_of"]]
    mismatches = [
        {"url": l["url"], "label": l["category"], "model": category_by_id[l["id"]]}
        for l in judged if category_by_id[l["id"]] != l["category"]
    ]
    matches = len(judged) - len(mismatches)
    return {
        "judged": len(judged),
        "matches": matches,
        "accuracy": round(matches / len(judged), 3) if judged else None,
        "mismatches": mismatches,
    }


def quote_back_metrics(quotes_and_texts):
    def norm(s):
        return " ".join(s.split()).lower()
    grounded = sum(1 for quote, text in quotes_and_texts if norm(quote) in norm(text))
    total = len(quotes_and_texts)
    return {
        "insights": total,
        "quote_in_source": grounded,
        "rate": round(grounded / total, 3) if total else None,
    }


def main():
    labels = json.load(open("eval/labels.json", encoding="utf-8"))["items"]
    sample = json.load(open("eval/sample.json", encoding="utf-8"))
    verdicts = {x["url"]: x["pipeline_verdict"] for x in sample}

    conn = sqlite3.connect("data/ci.db")
    conn.row_factory = sqlite3.Row
    insights = conn.execute(
        "SELECT i.cluster_id, i.category, i.quote, it.title, it.text"
        " FROM insights i JOIN items it ON it.cluster_id = i.cluster_id"
    ).fetchall()
    quarantined = conn.execute("SELECT count(*) FROM quarantine").fetchone()[0]

    json.dump({
        "gate": gate_metrics(labels, verdicts),
        "dedup": dedup_metrics(labels, verdicts),
        "classification": classification_metrics(
            labels, {r["cluster_id"]: r["category"] for r in insights}
        ),
        "quote_back": quote_back_metrics(
            [(r["quote"], f"{r['title']} {r['text']}") for r in insights]
        ),
        "quarantined": quarantined,
    }, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
