from eval.run_eval import (
    classification_metrics,
    dedup_metrics,
    gate_metrics,
    quote_back_metrics,
)


def label(url, relevant="y", category="product_release", dup_of=None, id=None):
    return {"url": url, "relevant": relevant, "category": category,
            "dup_of": dup_of, "id": id or url}


def test_gate_counts_precision_and_misses():
    labels = [
        label("a"), label("b", relevant="n"),
        label("c", relevant="y"), label("d", relevant="n"),
        label("e"),  # stale: excluded from gate metrics
    ]
    verdicts = {"a": "passed", "b": "passed",
                "c": "irrelevant", "d": "irrelevant", "e": "stale"}
    m = gate_metrics(labels, verdicts)
    assert m == {"passed": 2, "passed_relevant": 1, "precision": 0.5,
                 "irrelevant_rejects": 2, "missed_relevant": ["c"]}


def test_dedup_catches_pairs_and_flags_false_positives():
    labels = [label("kept"), label("copy", dup_of="kept"),
              label("missed", dup_of="kept"), label("wrongly_flagged")]
    verdicts = {"kept": "passed", "copy": "dup_batch",
                "missed": "passed", "wrongly_flagged": "dup_batch"}
    m = dedup_metrics(labels, verdicts)
    assert m == {"labelled_dups": 2, "caught": 1,
                 "false_dups": ["wrongly_flagged"]}


def test_classification_joins_on_id_and_lists_mismatches():
    labels = [label("a", category="product_release"),
              label("b", category="security_research"),
              label("c"),  # no insight for c
              label("a2", dup_of="a", id="a")]  # dup mirror: same id, skipped
    m = classification_metrics(
        labels, {"a": "product_release", "b": "marketing_content"})
    assert m["judged"] == 2 and m["matches"] == 1 and m["accuracy"] == 0.5
    assert m["mismatches"] == [
        {"url": "b", "label": "security_research", "model": "marketing_content"}]


def test_quote_back_normalizes_whitespace_and_case():
    m = quote_back_metrics([
        ("released  Version\n1.2", "Today we RELEASED version 1.2 of the tool"),
        ("not in the text", "something else entirely"),
    ])
    assert m == {"insights": 2, "quote_in_source": 1, "rate": 0.5}


def test_label_missing_from_sample_does_not_crash():
    labels = [label("edited-by-hand")]
    assert gate_metrics(labels, {})["passed"] == 0
    assert dedup_metrics(labels, {})["false_dups"] == []


def test_empty_inputs_yield_none_rates():
    assert gate_metrics([], {})["precision"] is None
    assert classification_metrics([], {})["accuracy"] is None
    assert quote_back_metrics([])["rate"] is None
