"""Data contracts. Everything downstream (providers, filters, db, ui) builds
against these models; change them here or not at all."""

import hashlib
import re
import tomllib
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


class SourceConfig(BaseModel):
    id: str
    provider: str
    trust_tier: int = 3
    competitor: str | None = None
    url: str | None = None
    repo: str | None = None
    query: str | None = None


class CompetitorConfig(BaseModel):
    id: str
    name: str
    tier: int
    aliases: list[str] = Field(default_factory=list)


class Settings(BaseModel):
    recency_days: int = 14
    cluster_window_days: int = 90
    raw_dir: str = "data/raw"
    db_path: str = "data/ci.db"


class LLMConfig(BaseModel):
    provider: Literal["groq", "gemini"] = "groq"
    # pinned model IDs, never "latest" (governance: MODEL-GOVERNANCE.md)
    groq_model: str = "openai/gpt-oss-120b"
    gemini_model: str = "gemini-2.5-flash"

    @property
    def model(self) -> str:
        return {"groq": self.groq_model, "gemini": self.gemini_model}[self.provider]


class AppConfig(BaseModel):
    settings: Settings
    competitors: list[CompetitorConfig]
    sources: list[SourceConfig]
    llm: LLMConfig = LLMConfig()

    def aliases(self) -> list[str]:
        return [a for c in self.competitors for a in c.aliases]


def load_config(path: str | Path) -> AppConfig:
    with open(path, "rb") as f:
        return AppConfig.model_validate(tomllib.load(f))


class RawItem(BaseModel):
    """One ingested item, before any model involvement."""

    source_id: str
    trust_tier: int
    competitor: str | None = None
    url: str
    title: str
    text: str = ""
    published_at: datetime | None = None
    fetched_at: datetime
    raw_ref: str  # cache file this item was parsed from (provenance)

    def content_hash(self) -> str:
        """Identity is content, not URL: the same story at two URLs is one item."""
        return hashlib.sha256(f"{_norm(self.title)}\n{_norm(self.text)}".encode()).hexdigest()


# Fixed, code-defined taxonomy. The model selects from these; it never invents
# categories or themes (determinism principle, DECISIONS D7).
Category = Literal[
    "product_release", "security_research", "funding", "acquisition",
    "partnership", "pricing", "leadership", "marketing_content", "other",
]
Theme = Literal[
    "agentic_supply_chain", "fly", "apptrust", "agentic_remediation",
    "ai_catalog", "mlops_models", "github_partnership",
]


class InsightExtraction(BaseModel):
    """The LLM's entire output surface. Anything outside this schema is a
    validation error, and validation errors fail closed to quarantine."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=600)
    category: Category
    themes: list[Theme] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    numbers: list[str] = Field(default_factory=list)
    quote: str = Field(min_length=1)
