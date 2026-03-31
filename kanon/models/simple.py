"""Simplified Kanon entity models.

Four entity types: Evidence, Fact, Concept, Asset.
Facts are the atomic unit of truth. Concepts are labels.
Evidence carries authority. Assets are assembled from facts.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """A source document backing factual claims."""
    id: str
    name: str
    description: Optional[str] = None
    url: Optional[str] = None
    source_type: str  # documentation, article, internal_note
    trust: float = 0.7  # 0.0–1.0 authority score
    last_verified: date
    change_log: list[dict] = Field(default_factory=list)


class Fact(BaseModel):
    """A single verifiable claim — the atomic unit of truth."""
    id: str
    claim: str
    value: str
    numeric_value: Optional[float] = None
    status: Literal["active", "superseded", "retracted"]
    concepts: list[str] = Field(default_factory=list)  # multi-concept
    evidence: list[str] = Field(default_factory=list)
    evergreen: bool = False  # exempt from freshness decay
    effective_date: date
    recorded_date: date
    superseded_date: Optional[date] = None
    superseded_by: Optional[str] = None


class Concept(BaseModel):
    """A label that groups related facts. Nothing more."""
    id: str
    name: str
    description: str


class Asset(BaseModel):
    """Generated training content assembled from facts."""
    id: str
    name: str
    concepts: list[str] = Field(default_factory=list)
    audience: str = ""  # free text, not an entity
    template: str = ""
    lifecycle_state: str = "draft"  # draft, approved, needs_review
    content: str = ""
    fact_map: dict[str, list[str]] = Field(default_factory=dict)  # section → fact IDs
    generation_method: str = "dry_run"
    evidence_links: list[str] = Field(default_factory=list)
    generated_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None
