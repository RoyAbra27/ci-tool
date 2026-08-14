import pytest

from ci_tool import llm
from ci_tool.cache import RawCache, SourceUnavailable
from ci_tool.models import InsightExtraction


def test_strict_schema_closes_objects_and_strips_validation_keywords():
    schema = llm.strict_schema(InsightExtraction)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert "minLength" not in str(schema)
    assert "default" not in str(schema)


def test_cached_response_short_circuits_provider(tmp_path, monkeypatch):
    cache = RawCache(tmp_path)
    calls = []
    monkeypatch.setitem(llm.PROVIDERS, "groq", lambda *a: calls.append(a) or '{"ok": 1}')
    first = llm.complete_json("prompt", provider="groq", model="m", schema={}, cache=cache, live=True)
    second = llm.complete_json("prompt", provider="groq", model="m", schema={}, cache=cache, live=True)
    assert first == second == '{"ok": 1}'
    assert len(calls) == 1  # second call served from cache, no double spend


def test_replay_cache_miss_fails_closed(tmp_path):
    with pytest.raises(SourceUnavailable):
        llm.complete_json("prompt", provider="groq", model="m", schema={},
                          cache=RawCache(tmp_path), live=False)


def test_replay_reads_cache_written_by_live_run(tmp_path, monkeypatch):
    cache = RawCache(tmp_path)
    monkeypatch.setitem(llm.PROVIDERS, "groq", lambda *a: '{"ok": 1}')
    llm.complete_json("prompt", provider="groq", model="m", schema={}, cache=cache, live=True)
    replayed = llm.complete_json("prompt", provider="groq", model="m", schema={},
                                 cache=cache, live=False)
    assert replayed == '{"ok": 1}'


def test_missing_key_raises_unavailable(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(llm.LLMUnavailable):
        llm.PROVIDERS["groq"]("p", "m", {})
