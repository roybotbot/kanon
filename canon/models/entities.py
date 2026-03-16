"""Pydantic v2 models for all Canon ontology entity types."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Concept(BaseModel):
    id: str
    name: str
    description: str
    supports: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    content_block: Optional[str] = None


class Capability(BaseModel):
    id: str
    name: str
    description: str
    enables: list[str] = Field(default_factory=list)
    content_block: Optional[str] = None


class Task(BaseModel):
    id: str
    name: str
    description: str
    targets: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    content_block: Optional[str] = None


class Audience(BaseModel):
    id: str
    name: str
    description: str
    assumed_knowledge: list[str] = Field(default_factory=list)
    tone: Optional[str] = None
    preferred_formats: list[str] = Field(default_factory=list)


class LearningObjective(BaseModel):
    id: str
    name: str
    description: str
    verb: Optional[str] = None
    concepts: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)


class Fact(BaseModel):
    id: str
    claim: str
    value: str
    numeric_value: Optional[float] = None
    condition: Optional[str] = None
    status: Literal["active", "superseded", "retracted"]
    concept: str
    evidence: list[str]
    effective_date: date
    recorded_date: date
    superseded_date: Optional[date] = None
    superseded_by: Optional[str] = None


class ChangeEntry(BaseModel):
    date: date
    description: str
    detected_by: str


class Evidence(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    url: Optional[str] = None
    source_type: str
    last_verified: date
    version: Optional[str] = None
    change_log: list[ChangeEntry] = Field(default_factory=list)


class ConfidenceScore(BaseModel):
    evidence: float
    freshness: float
    structural: float
    transformation: float
    overall: float


class Asset(BaseModel):
    id: str
    name: str
    asset_type: str
    asset_subtype: Optional[str] = None
    delivery_format: str
    lifecycle_stage: Optional[str] = None
    lifecycle_state: str
    teaches: list[str]
    demonstrates: list[str] = Field(default_factory=list)
    supports_tasks: list[str] = Field(default_factory=list)
    targets: list[str]
    references: list[str] = Field(default_factory=list)
    evidence_links: list[str]
    constrained_by: list[str] = Field(default_factory=list)
    learning_objectives: list[str] = Field(default_factory=list)
    generation_method: str
    generated_at: datetime
    last_updated: datetime
    confidence: ConfidenceScore
    content: str
    content_blocks: Optional[dict] = None


class Constraint(BaseModel):
    id: str
    name: str
    description: str
    scope: Optional[str] = None
    severity: str
