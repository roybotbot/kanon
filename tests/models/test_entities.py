"""Tests for Canon ontology entity models."""
from datetime import date, datetime

import pytest
from pydantic import ValidationError

from kanon.models.entities import (
    Asset,
    Audience,
    Capability,
    ChangeEntry,
    Concept,
    ConfidenceScore,
    Constraint,
    Evidence,
    Fact,
    LearningObjective,
    Task,
)


# ---------------------------------------------------------------------------
# Concept
# ---------------------------------------------------------------------------

class TestConcept:
    def test_minimal(self):
        c = Concept(id="c1", name="Gradient Descent", description="Optimization algorithm")
        assert c.id == "c1"
        assert c.name == "Gradient Descent"
        assert c.description == "Optimization algorithm"
        assert c.supports == []
        assert c.prerequisites == []
        assert c.content_block is None

    def test_full(self):
        c = Concept(
            id="c2",
            name="Backpropagation",
            description="Computes gradients",
            supports=["c3", "c4"],
            prerequisites=["c1"],
            content_block="## Backprop\nDetails here.",
        )
        assert c.supports == ["c3", "c4"]
        assert c.prerequisites == ["c1"]
        assert c.content_block == "## Backprop\nDetails here."

    def test_required_fields_enforced(self):
        with pytest.raises(ValidationError):
            Concept(name="Missing id and description")

    def test_lists_default_to_empty(self):
        c = Concept(id="x", name="X", description="desc")
        assert isinstance(c.supports, list)
        assert isinstance(c.prerequisites, list)


# ---------------------------------------------------------------------------
# Capability
# ---------------------------------------------------------------------------

class TestCapability:
    def test_minimal(self):
        cap = Capability(id="cap1", name="Train a model", description="Can train ML models")
        assert cap.enables == []
        assert cap.content_block is None

    def test_with_enables(self):
        cap = Capability(
            id="cap2",
            name="Deploy a model",
            description="Can deploy",
            enables=["cap3"],
        )
        assert cap.enables == ["cap3"]

    def test_required_fields_enforced(self):
        with pytest.raises(ValidationError):
            Capability(id="cap1")


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class TestTask:
    def test_minimal(self):
        t = Task(id="t1", name="Fine-tune LLM", description="Fine-tuning workflow")
        assert t.targets == []
        assert t.steps == []
        assert t.content_block is None

    def test_with_steps(self):
        t = Task(
            id="t2",
            name="Evaluate model",
            description="Run evals",
            targets=["aud1"],
            steps=["Load dataset", "Run inference", "Compute metrics"],
        )
        assert t.targets == ["aud1"]
        assert t.steps == ["Load dataset", "Run inference", "Compute metrics"]

    def test_required_fields_enforced(self):
        with pytest.raises(ValidationError):
            Task(id="t1", name="No description")


# ---------------------------------------------------------------------------
# Audience
# ---------------------------------------------------------------------------

class TestAudience:
    def test_minimal(self):
        a = Audience(id="aud1", name="ML Engineers", description="Experienced practitioners")
        assert a.assumed_knowledge == []
        assert a.tone is None
        assert a.preferred_formats == []

    def test_full(self):
        a = Audience(
            id="aud2",
            name="Students",
            description="University students",
            assumed_knowledge=["c1", "c2"],
            tone="formal",
            preferred_formats=["slides", "video"],
        )
        assert a.assumed_knowledge == ["c1", "c2"]
        assert a.tone == "formal"
        assert a.preferred_formats == ["slides", "video"]

    def test_required_fields_enforced(self):
        with pytest.raises(ValidationError):
            Audience(id="a1")


# ---------------------------------------------------------------------------
# LearningObjective
# ---------------------------------------------------------------------------

class TestLearningObjective:
    def test_minimal(self):
        lo = LearningObjective(id="lo1", name="Understand GD", description="Explain gradient descent")
        assert lo.verb is None
        assert lo.concepts == []
        assert lo.tasks == []

    def test_full(self):
        lo = LearningObjective(
            id="lo2",
            name="Apply backprop",
            description="Implement backpropagation",
            verb="apply",
            concepts=["c1", "c2"],
            tasks=["t1"],
        )
        assert lo.verb == "apply"
        assert lo.concepts == ["c1", "c2"]
        assert lo.tasks == ["t1"]

    def test_required_fields_enforced(self):
        with pytest.raises(ValidationError):
            LearningObjective(id="lo1", name="Missing description")


# ---------------------------------------------------------------------------
# Fact
# ---------------------------------------------------------------------------

class TestFact:
    def _base(self, **overrides):
        defaults = dict(
            id="f1",
            claim="Transformer attention is O(n²)",
            value="O(n²)",
            status="active",
            concept="c1",
            evidence=["ev1"],
            effective_date=date(2024, 1, 1),
            recorded_date=date(2024, 1, 2),
        )
        defaults.update(overrides)
        return Fact(**defaults)

    def test_active_status(self):
        f = self._base(status="active")
        assert f.status == "active"

    def test_superseded_status(self):
        f = self._base(status="superseded", superseded_by="f2", superseded_date=date(2025, 1, 1))
        assert f.status == "superseded"

    def test_retracted_status(self):
        f = self._base(status="retracted")
        assert f.status == "retracted"

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            self._base(status="unknown")

    def test_multiple_evidence_sources(self):
        f = self._base(evidence=["ev1", "ev2", "ev3"])
        assert f.evidence == ["ev1", "ev2", "ev3"]

    def test_numeric_value_optional(self):
        f = self._base()
        assert f.numeric_value is None

    def test_numeric_value_set(self):
        f = self._base(numeric_value=42.0)
        assert f.numeric_value == 42.0

    def test_optional_fields_default_to_none(self):
        f = self._base()
        assert f.condition is None
        assert f.superseded_date is None
        assert f.superseded_by is None

    def test_required_fields_enforced(self):
        with pytest.raises(ValidationError):
            Fact(id="f1", claim="Missing fields")


# ---------------------------------------------------------------------------
# ChangeEntry + Evidence
# ---------------------------------------------------------------------------

class TestChangeEntry:
    def test_basic(self):
        ce = ChangeEntry(
            date=date(2024, 6, 1),
            description="Updated benchmark",
            detected_by="ev1",
        )
        assert ce.date == date(2024, 6, 1)
        assert ce.description == "Updated benchmark"
        assert ce.detected_by == "ev1"

    def test_required_fields_enforced(self):
        with pytest.raises(ValidationError):
            ChangeEntry(date=date(2024, 1, 1))


class TestEvidence:
    def test_minimal(self):
        e = Evidence(
            id="ev1",
            name="MMLU Paper",
            source_type="paper",
            last_verified=date(2024, 3, 1),
        )
        assert e.description is None
        assert e.url is None
        assert e.version is None
        assert e.change_log == []

    def test_with_change_log(self):
        entry = ChangeEntry(
            date=date(2024, 6, 1),
            description="New version released",
            detected_by="ev2",
        )
        e = Evidence(
            id="ev1",
            name="Benchmark",
            source_type="paper",
            last_verified=date(2024, 1, 1),
            change_log=[entry],
        )
        assert len(e.change_log) == 1
        assert e.change_log[0].description == "New version released"

    def test_required_fields_enforced(self):
        with pytest.raises(ValidationError):
            Evidence(id="ev1", name="Missing source_type and last_verified")


# ---------------------------------------------------------------------------
# ConfidenceScore
# ---------------------------------------------------------------------------

class TestConfidenceScore:
    def test_all_fields(self):
        cs = ConfidenceScore(
            evidence=0.9,
            freshness=0.8,
            structural=0.85,
            transformation=0.7,
            overall=0.81,
        )
        assert cs.evidence == 0.9
        assert cs.freshness == 0.8
        assert cs.structural == 0.85
        assert cs.transformation == 0.7
        assert cs.overall == 0.81

    def test_required_fields_enforced(self):
        with pytest.raises(ValidationError):
            ConfidenceScore(evidence=0.9)


# ---------------------------------------------------------------------------
# Asset
# ---------------------------------------------------------------------------

class TestAsset:
    def _confidence(self):
        return ConfidenceScore(
            evidence=0.9,
            freshness=0.8,
            structural=0.85,
            transformation=0.7,
            overall=0.81,
        )

    def _base(self, **overrides):
        defaults = dict(
            id="a1",
            name="Intro to Transformers",
            asset_type="lesson",
            delivery_format="markdown",
            lifecycle_state="draft",
            teaches=["c1"],
            targets=["aud1"],
            evidence_links=["ev1"],
            generation_method="llm",
            generated_at=datetime(2024, 1, 1, 12, 0),
            last_updated=datetime(2024, 1, 2, 12, 0),
            confidence=self._confidence(),
            content="# Intro\nContent here.",
        )
        defaults.update(overrides)
        return Asset(**defaults)

    def test_minimal(self):
        a = self._base()
        assert a.id == "a1"
        assert a.teaches == ["c1"]
        assert a.targets == ["aud1"]
        assert a.evidence_links == ["ev1"]
        assert a.demonstrates == []
        assert a.supports_tasks == []
        assert a.references == []
        assert a.constrained_by == []
        assert a.learning_objectives == []
        assert a.asset_subtype is None
        assert a.lifecycle_stage is None
        assert a.content_blocks is None

    def test_all_relationship_lists(self):
        a = self._base(
            demonstrates=["c2"],
            supports_tasks=["t1"],
            references=["ref1"],
            constrained_by=["con1"],
            learning_objectives=["lo1"],
        )
        assert a.demonstrates == ["c2"]
        assert a.supports_tasks == ["t1"]
        assert a.references == ["ref1"]
        assert a.constrained_by == ["con1"]
        assert a.learning_objectives == ["lo1"]

    def test_confidence_score_embedded(self):
        a = self._base()
        assert isinstance(a.confidence, ConfidenceScore)
        assert a.confidence.overall == 0.81

    def test_required_fields_enforced(self):
        with pytest.raises(ValidationError):
            Asset(id="a1", name="Missing most fields")

    def test_content_blocks_optional_dict(self):
        a = self._base(content_blocks={"intro": "Some intro", "body": "Main content"})
        assert a.content_blocks == {"intro": "Some intro", "body": "Main content"}


# ---------------------------------------------------------------------------
# Constraint
# ---------------------------------------------------------------------------

class TestConstraint:
    def test_minimal(self):
        c = Constraint(id="con1", name="No PII", description="Do not include PII", severity="high")
        assert c.scope is None
        assert c.severity == "high"

    def test_with_scope(self):
        c = Constraint(
            id="con2",
            name="Length limit",
            description="Max 2000 words",
            scope="lesson",
            severity="medium",
        )
        assert c.scope == "lesson"

    def test_required_fields_enforced(self):
        with pytest.raises(ValidationError):
            Constraint(id="con1", name="Missing description and severity")
