"""LLM seam: two providers behind one function. Responses are cached in the
raw cache keyed by (provider, model, prompt hash), so identical prompts are
never paid for twice and replay runs need no keys at all."""

import hashlib
import os

from ci_tool import http
from ci_tool.cache import RawCache, SourceUnavailable

# Groq strict json_schema rejects validation-only keywords; Pydantic still
# enforces them after decode, so stripping here loses nothing.
_SCHEMA_KEYWORDS_TO_STRIP = {"minLength", "maxLength", "default"}


class LLMUnavailable(Exception):
    """No API key for the configured provider. A replay cache miss raises
    SourceUnavailable instead; analyze treats both as skip, not failure."""


def strict_schema(model_cls) -> dict:
    """Pydantic JSON schema shaped for strict constrained decoding: every
    object closed and fully required."""

    def walk(node):
        if isinstance(node, dict):
            for key in _SCHEMA_KEYWORDS_TO_STRIP:
                node.pop(key, None)
            if node.get("type") == "object":
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    schema = model_cls.model_json_schema()
    walk(schema)
    return schema


def _require_key(name: str) -> str:
    key = os.environ.get(name)
    if not key:
        raise LLMUnavailable(f"{name} not set")
    return key


def _groq(prompt: str, model: str, schema: dict) -> str:
    data = http.post_json(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {_require_key('GROQ_API_KEY')}"},
        json_body={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "extraction", "strict": True, "schema": schema},
            },
        },
    )
    return data["choices"][0]["message"]["content"]


def _gemini(prompt: str, model: str, schema: dict) -> str:
    # no strict decode on this path; schema enforcement is Pydantic-only,
    # which is the documented enforcement difference between the providers
    data = http.post_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": _require_key("GEMINI_API_KEY")},
        json_body={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
        },
    )
    return data["candidates"][0]["content"]["parts"][0]["text"]


PROVIDERS = {"groq": _groq, "gemini": _gemini}


def complete_json(
    prompt: str, *, provider: str, model: str, schema: dict, cache: RawCache, live: bool
) -> str:
    cache_key = f"{provider}:{model}:{hashlib.sha256(prompt.encode()).hexdigest()}"
    cached = cache.latest("llm", cache_key)
    if cached is not None:
        return cached[0]
    if not live:
        raise SourceUnavailable(f"no cached LLM response for {cache_key[:48]}")
    text = PROVIDERS[provider](prompt, model, schema)
    cache.put("llm", cache_key, text)
    return text
