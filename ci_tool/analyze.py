"""LLM stage: one bounded extraction per cluster, deterministically grounded,
fail-closed to quarantine. Replay runs read cached LLM responses; the re-ask
prompt is deterministic, so a replayed run replays the re-ask too."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from ci_tool import db, grounding, llm
from ci_tool.cache import RawCache, SourceUnavailable
from ci_tool.models import InsightExtraction, load_config

MAX_ITEMS_PER_CLUSTER = 4
MAX_CHARS_PER_ITEM = 4000

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "extract.md"


def load_prompt() -> tuple[str, str]:
    text = _PROMPT_PATH.read_text(encoding="utf-8")
    return text, hashlib.sha256(text.encode()).hexdigest()[:12]


def _source_block(rows) -> str:
    return "\n\n".join(
        f"SOURCE (feed: {r['source_id']}, url: {r['url']}, published: {r['published_at']})\n"
        f"TITLE: {r['title']}\n{r['text'][:MAX_CHARS_PER_ITEM]}"
        for r in rows
    )


def _validate(raw: str, source_text: str) -> tuple[InsightExtraction | None, list[str]]:
    try:
        extraction = InsightExtraction.model_validate_json(raw)
    except ValidationError as e:
        return None, [f"schema validation failed: {e}"[:500]]
    return extraction, grounding.verify(extraction, source_text)


def analyze(*, live: bool, config_path: str = "config.toml") -> dict:
    cfg = load_config(config_path)
    root = Path(config_path).resolve().parent
    cache = RawCache(root / cfg.settings.raw_dir)
    provider = cfg.llm.provider
    model = cfg.llm.model
    template, prompt_version = load_prompt()
    schema = llm.strict_schema(InsightExtraction)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-analyze"
    counters = {"clusters": 0, "extracted": 0, "reasked": 0, "quarantined": 0,
                "skipped_unavailable": 0, "llm_errors": 0}
    error_detail: dict[str, str] = {}

    def ask(prompt: str) -> str:
        return llm.complete_json(
            prompt, provider=provider, model=model, schema=schema, cache=cache, live=live
        )

    conn = db.connect(root / cfg.settings.db_path)
    try:
        clusters = db.unanalyzed_clusters(conn)
        counters["clusters"] = len(clusters)
        with conn:
            for cluster_id, rows in clusters.items():
                sent = rows[:MAX_ITEMS_PER_CLUSTER]
                source_text = " ".join(f"{r['title']} {r['text']}" for r in sent)
                prompt = template.replace("{sources}", _source_block(sent))

                try:
                    raw = ask(prompt)
                    extraction, errors = _validate(raw, source_text)
                    if errors:
                        counters["reasked"] += 1
                        raw = ask(
                            prompt
                            + "\n\nYour previous answer was rejected by mechanical verification:\n- "
                            + "\n- ".join(errors)
                            + "\nReturn corrected JSON. Copy quote, entities and numbers verbatim from the sources."
                        )
                        extraction, errors = _validate(raw, source_text)
                except (SourceUnavailable, llm.LLMUnavailable):
                    counters["skipped_unavailable"] += 1
                    continue
                except Exception as e:  # noqa: BLE001 - counted as llm_errors, the run continues
                    counters["llm_errors"] += 1
                    error_detail[cluster_id[:12]] = f"{type(e).__name__}: {e}"[:160]
                    continue

                if errors:
                    db.quarantine_add(conn, cluster_id, "extract", "; ".join(errors)[:1000], raw)
                    counters["quarantined"] += 1
                    continue

                db.add_insight(
                    conn,
                    cluster_id=cluster_id,
                    run_id=run_id,
                    provider=provider,
                    model=model,
                    prompt_version=prompt_version,
                    summary=extraction.summary,
                    category=extraction.category,
                    themes=json.dumps(extraction.themes),
                    entities=json.dumps(extraction.entities),
                    numbers=json.dumps(extraction.numbers),
                    quote=extraction.quote,
                    confidence=grounding.confidence(min(r["trust_tier"] for r in rows), len(rows)),
                    competitor=next((r["competitor"] for r in rows if r["competitor"]), None),
                    item_count=len(rows),
                )
                counters["extracted"] += 1
            db.add_run(conn, run_id, "live" if live else "replay", counters)
    finally:
        conn.close()

    return {"run_id": run_id, "mode": "live" if live else "replay",
            "provider": provider, "model": model, "prompt_version": prompt_version,
            "counters": counters, "errors": error_detail}
