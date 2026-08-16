import json
from datetime import UTC, datetime

import pytest

from ci_tool import db, llm
from ci_tool.analyze import analyze
from ci_tool.models import RawItem

NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)

VALID_JSON = json.dumps({
    "summary": "Cloudsmith raised $72M in Series C funding.",
    "category": "funding",
    "themes": [],
    "entities": ["Cloudsmith"],
    "numbers": ["$72M"],
    "quote": "Cloudsmith raised $72M in Series C funding led by TCV.",
})
UNGROUNDED_JSON = json.dumps({
    "summary": "Cloudsmith acquired JFrog.",
    "category": "acquisition",
    "themes": [],
    "entities": ["Cloudsmith"],
    "numbers": [],
    "quote": "This sentence appears nowhere in the source.",
})


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "config.toml").write_text(
        "sources = []\n"
        '[settings]\nraw_dir = "data/raw"\ndb_path = "data/ci.db"\n'
        "[[competitors]]\nid = \"cloudsmith\"\nname = \"Cloudsmith\"\n"
        "aliases = [\"cloudsmith\"]\n",
        encoding="utf-8",
    )
    conn = db.connect(tmp_path / "data" / "ci.db")
    item = RawItem(
        source_id="cloudsmith-blog", trust_tier=1, competitor="cloudsmith",
        url="https://example.com/series-c",
        title="Cloudsmith raises Series C",
        text="Cloudsmith raised $72M in Series C funding led by TCV.",
        published_at=NOW, fetched_at=NOW, raw_ref="x.json",
    )
    with conn:
        db.insert_item(conn, item, "", item.content_hash(), "testrun")
    conn.close()
    return tmp_path


def fake_llm(responses: list[str]):
    calls = []

    def complete_json(prompt, **kwargs):
        calls.append(prompt)
        return responses[min(len(calls) - 1, len(responses) - 1)]

    return complete_json, calls


def test_valid_extraction_lands_in_insights(repo, monkeypatch):
    fake, calls = fake_llm([VALID_JSON])
    monkeypatch.setattr(llm, "complete_json", fake)
    report = analyze(live=True, config_path=str(repo / "config.toml"))
    assert report["counters"]["extracted"] == 1
    assert len(calls) == 1
    conn = db.connect(repo / "data" / "ci.db")
    row = conn.execute("SELECT * FROM insights").fetchone()
    assert row["category"] == "funding"
    assert row["confidence"] == "high"
    assert row["prompt_version"] == report["prompt_version"]
    conn.close()


def test_reask_recovers_from_ungrounded_first_answer(repo, monkeypatch):
    fake, calls = fake_llm([UNGROUNDED_JSON, VALID_JSON])
    monkeypatch.setattr(llm, "complete_json", fake)
    counters = analyze(live=True, config_path=str(repo / "config.toml"))["counters"]
    assert (counters["extracted"], counters["reasked"], counters["quarantined"]) == (1, 1, 0)
    assert len(calls) == 2
    assert "rejected by mechanical verification" in calls[1]


def test_double_failure_quarantines_and_is_not_retried(repo, monkeypatch):
    fake, _ = fake_llm([UNGROUNDED_JSON, UNGROUNDED_JSON])
    monkeypatch.setattr(llm, "complete_json", fake)
    report = analyze(live=True, config_path=str(repo / "config.toml"))
    assert report["counters"]["quarantined"] == 1
    assert report["counters"]["extracted"] == 0
    conn = db.connect(repo / "data" / "ci.db")
    q = conn.execute("SELECT * FROM quarantine").fetchone()
    assert q["stage"] == "extract"
    assert "quote" in q["error"]
    conn.close()
    # a second analyze run must not re-ask for the quarantined cluster
    fake2, calls2 = fake_llm([VALID_JSON])
    monkeypatch.setattr(llm, "complete_json", fake2)
    report2 = analyze(live=True, config_path=str(repo / "config.toml"))
    assert report2["counters"]["clusters"] == 0
    assert not calls2


def test_invalid_schema_is_rejected(repo, monkeypatch):
    bad = json.dumps({"summary": "x", "category": "not_a_category", "themes": [],
                      "entities": [], "numbers": [], "quote": "y"})
    fake, _ = fake_llm([bad, bad])
    monkeypatch.setattr(llm, "complete_json", fake)
    report = analyze(live=True, config_path=str(repo / "config.toml"))
    assert report["counters"]["quarantined"] == 1


def test_replay_without_cache_skips(repo, monkeypatch):
    def raises(prompt, **kwargs):
        raise llm.LLMUnavailable("no key")

    monkeypatch.setattr(llm, "complete_json", raises)
    report = analyze(live=False, config_path=str(repo / "config.toml"))
    assert report["counters"]["skipped_unavailable"] == 1
    assert report["counters"]["quarantined"] == 0
