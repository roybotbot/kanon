"""Tests for Experiment 01: Claim-Level Traceability.

Tests citation extraction, validation, and stripping.
LLM generation tests that require API calls are marked with pytest.mark.llm.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kanon.citations import (
    CitationReport,
    extract_citations,
    strip_citations,
    validate_citations,
)
from kanon.graph import KnowledgeGraph
from kanon.models.entities import Fact

DATA_DIR = Path(__file__).parent.parent / "data"


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def claude_graph():
    return KnowledgeGraph(data_dir=DATA_DIR)


@pytest.fixture
def food_graph(tmp_path):
    """Minimal food graph with active, superseded, and retracted facts."""
    entities = {
        "concepts": [
            {
                "id": "pasta_cooking",
                "name": "Pasta Cooking",
                "description": "Techniques for cooking pasta",
                "supports": [],
                "prerequisites": [],
                "content_block": "Cook pasta in boiling salted water.",
            },
        ],
        "facts": [
            {
                "id": "pasta_water_ratio",
                "claim": "Water ratio for cooking pasta",
                "value": "1 gallon per pound of pasta",
                "status": "active",
                "concept": "pasta_cooking",
                "evidence": ["serious_eats_pasta"],
                "effective_date": "2025-01-01",
                "recorded_date": "2025-01-15",
            },
            {
                "id": "pasta_salt_amount",
                "claim": "Salt amount for pasta water",
                "value": "1 tablespoon per gallon",
                "status": "active",
                "concept": "pasta_cooking",
                "evidence": ["serious_eats_pasta"],
                "effective_date": "2025-01-01",
                "recorded_date": "2025-01-15",
            },
            {
                "id": "pasta_old_water_ratio",
                "claim": "Water ratio for cooking pasta",
                "value": "6 quarts per pound",
                "status": "superseded",
                "concept": "pasta_cooking",
                "evidence": ["serious_eats_pasta"],
                "effective_date": "2024-01-01",
                "recorded_date": "2024-01-15",
                "superseded_date": "2025-01-01",
                "superseded_by": "pasta_water_ratio",
            },
            {
                "id": "pasta_rinse_after",
                "claim": "Rinse pasta after cooking",
                "value": "Always rinse with cold water",
                "status": "retracted",
                "concept": "pasta_cooking",
                "evidence": ["serious_eats_pasta"],
                "effective_date": "2023-01-01",
                "recorded_date": "2023-01-15",
                "superseded_date": "2024-06-01",
            },
        ],
        "evidence": [
            {
                "id": "serious_eats_pasta",
                "name": "Serious Eats: How to Cook Pasta",
                "source_type": "article",
                "last_verified": "2025-06-01",
            },
        ],
        "audiences": [
            {
                "id": "home_cook",
                "name": "Home Cook",
                "description": "Amateur cooks",
            },
        ],
    }

    for entity_type, items in entities.items():
        entity_dir = tmp_path / entity_type
        entity_dir.mkdir()
        for item in items:
            (entity_dir / f"{item['id']}.yaml").write_text(
                yaml.dump(item, default_flow_style=False)
            )

    for subdir in ["tasks", "capabilities", "constraints", "objectives", "assets"]:
        (tmp_path / subdir).mkdir(exist_ok=True)

    return KnowledgeGraph(data_dir=tmp_path)


# ── Extract ──────────────────────────────────────────────────────────


class TestExtractCitations:
    def test_extracts_single_citation(self):
        text = "The max is 128 {{fact:tool_use_max_tools}}."
        assert extract_citations(text) == ["tool_use_max_tools"]

    def test_extracts_multiple_citations(self):
        text = (
            "Water ratio is 1 gallon {{fact:pasta_water_ratio}} "
            "and salt is 1 tbsp {{fact:pasta_salt_amount}}."
        )
        assert extract_citations(text) == ["pasta_water_ratio", "pasta_salt_amount"]

    def test_extracts_none_when_absent(self):
        text = "This is a plain sentence with no citations."
        assert extract_citations(text) == []

    def test_extracts_duplicate_citations(self):
        text = "Max is 128 {{fact:tool_use_max_tools}} and again 128 {{fact:tool_use_max_tools}}."
        assert extract_citations(text) == ["tool_use_max_tools", "tool_use_max_tools"]

    def test_handles_underscores_in_ids(self):
        text = "Value {{fact:code_exec_container_memory}} here."
        assert extract_citations(text) == ["code_exec_container_memory"]


# ── Validate ─────────────────────────────────────────────────────────


class TestValidateCitations:
    def test_all_active_facts_valid(self, claude_graph):
        text = "Max tools is 128 {{fact:tool_use_max_tools}}."
        report = validate_citations(text, claude_graph)
        assert report.is_valid
        assert "tool_use_max_tools" in report.valid

    def test_missing_fact_flagged(self, claude_graph):
        text = "Something {{fact:nonexistent_fact}} here."
        report = validate_citations(text, claude_graph)
        assert not report.is_valid
        assert "nonexistent_fact" in report.missing_from_graph

    def test_superseded_fact_flagged(self, food_graph):
        text = "Old ratio was 6 quarts {{fact:pasta_old_water_ratio}}."
        report = validate_citations(text, food_graph)
        assert not report.is_valid
        assert "pasta_old_water_ratio" in report.superseded

    def test_retracted_fact_flagged(self, food_graph):
        text = "Rinse pasta after {{fact:pasta_rinse_after}}."
        report = validate_citations(text, food_graph)
        assert not report.is_valid
        assert "pasta_rinse_after" in report.retracted

    def test_mixed_valid_and_invalid(self, food_graph):
        text = (
            "Water ratio is 1 gallon {{fact:pasta_water_ratio}} "
            "and old ratio was 6 quarts {{fact:pasta_old_water_ratio}}."
        )
        report = validate_citations(text, food_graph)
        assert not report.is_valid
        assert "pasta_water_ratio" in report.valid
        assert "pasta_old_water_ratio" in report.superseded

    def test_no_citations_is_valid(self, claude_graph):
        text = "A descriptive sentence with no factual claims."
        report = validate_citations(text, claude_graph)
        assert report.is_valid
        assert report.total_citations == 0

    def test_duplicate_citations_counted_once(self, claude_graph):
        text = "128 {{fact:tool_use_max_tools}} and again 128 {{fact:tool_use_max_tools}}."
        report = validate_citations(text, claude_graph)
        assert report.total_citations == 2
        assert len(report.valid) == 1  # deduplicated

    def test_failures_property(self, food_graph):
        text = (
            "{{fact:pasta_old_water_ratio}} and {{fact:pasta_rinse_after}} "
            "and {{fact:totally_fake}}."
        )
        report = validate_citations(text, food_graph)
        failures = report.failures
        assert len(failures) == 3
        assert any("superseded" in f for f in failures)
        assert any("retracted" in f for f in failures)
        assert any("not found" in f for f in failures)


# ── Strip ────────────────────────────────────────────────────────────


class TestStripCitations:
    def test_strips_single_citation(self):
        text = "The max is 128 {{fact:tool_use_max_tools}}."
        assert strip_citations(text) == "The max is 128."

    def test_strips_multiple_citations(self):
        text = "Water {{fact:pasta_water_ratio}} and salt {{fact:pasta_salt_amount}}."
        assert strip_citations(text) == "Water and salt."

    def test_no_citations_unchanged(self):
        text = "Plain text with no citations."
        assert strip_citations(text) == "Plain text with no citations."

    def test_preserves_markdown(self):
        text = "## Overview\n\nMax tools is 128 {{fact:tool_use_max_tools}}.\n\n- Item one"
        expected = "## Overview\n\nMax tools is 128.\n\n- Item one"
        assert strip_citations(text) == expected


# ── Drift + Citations ────────────────────────────────────────────────


class TestDriftWithCitations:
    """Verify that drift detection + citation validation together
    identify which specific claims are stale."""

    def test_superseded_fact_fails_validation_after_drift(self, food_graph):
        """Content that was valid becomes invalid when a fact is superseded."""
        # Content citing active facts
        content = (
            "Use 1 gallon of water per pound {{fact:pasta_water_ratio}} "
            "with 1 tablespoon of salt {{fact:pasta_salt_amount}}."
        )

        # Initially valid
        report = validate_citations(content, food_graph)
        assert report.is_valid

        # Now supersede pasta_water_ratio by modifying the graph
        fact = food_graph.get("pasta_water_ratio")
        assert isinstance(fact, Fact)
        # Simulate supersession by directly modifying status
        object.__setattr__(fact, "status", "superseded")

        # Same content, now invalid
        report_after = validate_citations(content, food_graph)
        assert not report_after.is_valid
        assert "pasta_water_ratio" in report_after.superseded
        # The salt citation is still valid
        assert "pasta_salt_amount" in report_after.valid

    def test_stale_citations_identified_precisely(self, food_graph):
        """After drift, we can tell exactly which claims are stale."""
        content = (
            "## Procedure\n\n"
            "Use 1 gallon of water per pound {{fact:pasta_water_ratio}}.\n"
            "Add 1 tablespoon of salt per gallon {{fact:pasta_salt_amount}}.\n"
        )

        # Supersede the water ratio
        fact = food_graph.get("pasta_water_ratio")
        object.__setattr__(fact, "status", "superseded")

        report = validate_citations(content, food_graph)
        # We know exactly which claim is stale
        assert report.superseded == ["pasta_water_ratio"]
        # And which is still valid
        assert report.valid == ["pasta_salt_amount"]
        # The failures list gives human-readable output
        assert len(report.failures) == 1
        assert "superseded" in report.failures[0]
