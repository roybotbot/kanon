"""Kanon PoC Validation Tests

These tests encode the validation criteria from VALIDATION.md.
Run with: pytest tests/test_validation.py -v

Tests are organized by stage:
  Stage 1: Generation — can we produce training materials from the graph?
  Stage 2: Review — can we trace claims and score confidence?
  Stage 3: Drift — can we detect changes and trace impact?
"""
from __future__ import annotations

import os
import tempfile
from datetime import date, UTC, datetime
from pathlib import Path

import pytest
import yaml

from kanon.confidence import calculate_confidence, needs_review
from kanon.drift import detect_drift
from kanon.generate import generate_asset_dry_run
from kanon.graph import KnowledgeGraph
from kanon.models.entities import (
    Asset, Audience, Concept, ConfidenceScore, Evidence, Fact, Task,
)

DATA_DIR = Path(__file__).parent.parent / "data"

# ── Fixtures ─────────────────────────────────────────────────────────

FOOD_ENTITIES = {
    "concepts": [
        {
            "id": "knife_skills",
            "name": "Knife Skills",
            "description": "Fundamental cutting techniques for food preparation",
            "supports": [],
            "prerequisites": [],
            "content_block": (
                "Knife skills are the foundation of efficient cooking.\n"
                "Proper technique reduces prep time and ensures even cooking.\n"
                "The three core cuts are dice, julienne, and chiffonade."
            ),
        },
        {
            "id": "pasta_cooking",
            "name": "Pasta Cooking",
            "description": "Techniques for cooking dried and fresh pasta",
            "supports": [],
            "prerequisites": ["knife_skills"],
            "content_block": (
                "Cook pasta in a large pot with 1 gallon of water per pound.\n"
                "Salt the water generously before adding pasta.\n"
                "Test for doneness 2 minutes before package time."
            ),
        },
        {
            "id": "sauce_making",
            "name": "Sauce Making",
            "description": "Preparing sauces from scratch using base techniques",
            "supports": [],
            "prerequisites": ["knife_skills"],
            "content_block": (
                "A good sauce starts with a flavor base — mirepoix or soffritto.\n"
                "Build layers: sweat aromatics, deglaze, add liquid, reduce.\n"
                "Season at the end to account for reduction concentrating flavors."
            ),
        },
    ],
    "tasks": [
        {
            "id": "dice_an_onion",
            "name": "Dice an Onion",
            "description": "Cut an onion into uniform small cubes",
            "targets": ["knife_skills"],
            "steps": [
                "Cut onion in half through the root end",
                "Peel the skin from each half",
                "Make horizontal cuts parallel to the cutting board",
                "Make vertical cuts perpendicular to the root",
                "Slice across to produce dice",
            ],
            "content_block": (
                "A properly diced onion has uniform pieces that cook evenly.\n"
                "Keep the root end intact to hold the onion together while cutting.\n"
                "Use a sharp chef's knife — a dull knife is more dangerous."
            ),
        },
        {
            "id": "cook_pasta_al_dente",
            "name": "Cook Pasta Al Dente",
            "description": "Cook dried pasta to firm-to-the-bite texture",
            "targets": ["pasta_cooking"],
            "steps": [
                "Bring water to a rolling boil",
                "Add salt — approximately 1 tablespoon per gallon",
                "Add pasta and stir immediately to prevent sticking",
                "Start testing 2 minutes before package directions",
                "Drain when pasta is firm to the bite with a thin white center",
            ],
            "content_block": (
                "Al dente pasta has a slight resistance when bitten.\n"
                "Residual heat continues cooking after draining.\n"
                "Reserve pasta water — the starch helps sauces adhere."
            ),
        },
    ],
    "audiences": [
        {
            "id": "home_cook",
            "name": "Home Cook",
            "description": "Amateur cooks preparing meals at home with basic equipment",
            "assumed_knowledge": [],
            "tone": "friendly",
            "preferred_formats": ["setup_guide"],
        },
        {
            "id": "professional_chef",
            "name": "Professional Chef",
            "description": "Trained culinary professionals working in commercial kitchens",
            "assumed_knowledge": ["knife_skills"],
            "tone": "technical",
            "preferred_formats": ["facilitator_guide", "reference_document"],
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
            "value": "1 tablespoon per gallon of water",
            "status": "active",
            "concept": "pasta_cooking",
            "evidence": ["serious_eats_pasta"],
            "effective_date": "2025-01-01",
            "recorded_date": "2025-01-15",
        },
        {
            "id": "knife_angle_for_dice",
            "claim": "Knife angle for uniform dice",
            "value": "Perpendicular to the cutting board for vertical cuts",
            "status": "active",
            "concept": "knife_skills",
            "evidence": ["atk_knife_guide"],
            "effective_date": "2025-02-01",
            "recorded_date": "2025-02-10",
        },
    ],
    "evidence": [
        {
            "id": "serious_eats_pasta",
            "name": "Serious Eats: How to Cook Pasta",
            "description": "Comprehensive guide to cooking dried pasta",
            "url": "https://www.seriouseats.com/how-to-cook-pasta",
            "source_type": "article",
            "last_verified": "2025-06-01",
        },
        {
            "id": "atk_knife_guide",
            "name": "America's Test Kitchen: Knife Skills",
            "description": "Step-by-step knife technique guide",
            "url": "https://www.americastestkitchen.com/knife-skills",
            "source_type": "article",
            "last_verified": "2025-06-01",
        },
    ],
    "assets": [
        {
            "id": "pasta_cooking_setup_guide_dry_run",
            "name": "Pasta Cooking Setup Guide",
            "asset_type": "guide",
            "delivery_format": "setup_guide",
            "lifecycle_state": "draft",
            "teaches": ["pasta_cooking"],
            "targets": ["home_cook"],
            "evidence_links": ["serious_eats_pasta"],
            "generation_method": "dry_run",
            "generated_at": "2025-06-01T00:00:00",
            "last_updated": "2025-06-01T00:00:00",
            "confidence": {
                "evidence": 1.0,
                "freshness": 1.0,
                "structural": 1.0,
                "transformation": 1.0,
                "overall": 1.0,
            },
            "content": "Pasta cooking guide content",
        },
    ],
}


@pytest.fixture
def food_graph(tmp_path):
    """Create a food domain knowledge graph from FOOD_ENTITIES."""
    for entity_type, entities in FOOD_ENTITIES.items():
        entity_dir = tmp_path / entity_type
        entity_dir.mkdir()
        for entity in entities:
            path = entity_dir / f"{entity['id']}.yaml"
            path.write_text(yaml.dump(entity, default_flow_style=False))

    # Create empty dirs for entity types not in food domain
    for subdir in ["capabilities", "constraints", "objectives"]:
        (tmp_path / subdir).mkdir(exist_ok=True)

    g = KnowledgeGraph(data_dir=tmp_path)
    return g, tmp_path


@pytest.fixture
def claude_graph():
    """Load the existing Claude/AI training domain graph."""
    return KnowledgeGraph(data_dir=DATA_DIR)


# ══════════════════════════════════════════════════════════════════════
# STAGE 1: Can we generate training materials from the knowledge graph?
# ══════════════════════════════════════════════════════════════════════


class TestStage1Generation:
    """Stage 1: Generation tests."""

    def test_dry_run_no_repeated_sections(self, claude_graph):
        """1.1 — Dry-run should populate each section with distinct content.

        Catches the bug where verification and troubleshooting fall back
        to the same concept content_block.
        """
        result = generate_asset_dry_run(
            graph=claude_graph,
            template_name="setup_guide",
            concept_ids=["tool_use"],
            audience_id="enterprise_developer",
        )

        sections = result["content_blocks"]
        section_values = list(sections.values())

        # No two sections should have identical content
        for i, (name_a, content_a) in enumerate(sections.items()):
            for name_b, content_b in list(sections.items())[i + 1:]:
                assert content_a != content_b, (
                    f"Sections '{name_a}' and '{name_b}' have identical content — "
                    f"this indicates a fallback bug in _build_section"
                )

    def test_dry_run_all_sections_populated(self, claude_graph):
        """1.1b — Every template section should have real content, not a placeholder."""
        result = generate_asset_dry_run(
            graph=claude_graph,
            template_name="setup_guide",
            concept_ids=["tool_use"],
            audience_id="enterprise_developer",
        )

        for section_name, content in result["content_blocks"].items():
            assert content.strip(), f"Section '{section_name}' is empty"
            assert "content to be added" not in content.lower(), (
                f"Section '{section_name}' has placeholder text"
            )

    def test_audience_adaptation_dry_run(self, claude_graph):
        """1.3 — Same asset for two audiences should produce different output."""
        result_dev = generate_asset_dry_run(
            graph=claude_graph,
            template_name="setup_guide",
            concept_ids=["tool_use"],
            audience_id="enterprise_developer",
        )
        result_eng = generate_asset_dry_run(
            graph=claude_graph,
            template_name="setup_guide",
            concept_ids=["tool_use"],
            audience_id="support_engineer",
        )

        # At minimum, the targets should differ
        assert result_dev["targets"] != result_eng["targets"]

    def test_multi_concept_generation(self, claude_graph):
        """1.4 — Multi-concept asset should include content from all concepts."""
        result = generate_asset_dry_run(
            graph=claude_graph,
            template_name="facilitator_guide",
            concept_ids=["tool_use", "system_prompt"],
            audience_id="enterprise_developer",
        )

        content = result["content"]
        assert "Tool Use" in content
        assert "System Prompt" in content
        assert len(result["teaches"]) == 2

    def test_food_domain_generation(self, food_graph):
        """1.5 — Food domain generates with no code changes."""
        g, _ = food_graph

        result = generate_asset_dry_run(
            graph=g,
            template_name="setup_guide",
            concept_ids=["pasta_cooking"],
            audience_id="home_cook",
        )

        assert result["name"] == "Pasta Cooking Setup Guide"
        assert result["teaches"] == ["pasta_cooking"]
        assert result["targets"] == ["home_cook"]
        assert "pasta" in result["content"].lower()

    def test_food_domain_multi_concept(self, food_graph):
        """1.5b — Food domain multi-concept asset."""
        g, _ = food_graph

        result = generate_asset_dry_run(
            graph=g,
            template_name="facilitator_guide",
            concept_ids=["knife_skills", "pasta_cooking"],
            audience_id="home_cook",
        )

        content = result["content"]
        assert "Knife Skills" in content
        assert "Pasta Cooking" in content

    def test_food_domain_prerequisites_resolved(self, food_graph):
        """1.5c — Pasta cooking should list knife_skills as prerequisite."""
        g, _ = food_graph

        result = generate_asset_dry_run(
            graph=g,
            template_name="setup_guide",
            concept_ids=["pasta_cooking"],
            audience_id="home_cook",
        )

        assert "knife_skills" in result["content"]


# ══════════════════════════════════════════════════════════════════════
# STAGE 2: Can we review generated materials for accuracy?
# ══════════════════════════════════════════════════════════════════════


class TestStage2Review:
    """Stage 2: Review and traceability tests."""

    def test_asset_traceability(self, claude_graph):
        """2.1 — Generated asset should list all contributing evidence sources."""
        result = generate_asset_dry_run(
            graph=claude_graph,
            template_name="setup_guide",
            concept_ids=["tool_use"],
            audience_id="enterprise_developer",
        )

        # The subgraph for tool_use includes facts backed by evidence
        # evidence_links should capture those
        evidence = result["evidence_links"]
        assert isinstance(evidence, list)
        # tool_use facts reference anthropic_tool_use_docs
        assert "anthropic_tool_use_docs" in evidence

    def test_asset_traceability_food(self, food_graph):
        """2.1b — Food domain traceability."""
        g, _ = food_graph

        result = generate_asset_dry_run(
            graph=g,
            template_name="setup_guide",
            concept_ids=["pasta_cooking"],
            audience_id="home_cook",
        )

        evidence = result["evidence_links"]
        assert "serious_eats_pasta" in evidence

    def test_confidence_reflects_changes(self):
        """2.2 — Confidence should differ based on evidence coverage."""
        # All concepts have evidence
        score_good = calculate_confidence(
            asset_teaches=["concept_a", "concept_b"],
            concepts_with_evidence={"concept_a", "concept_b"},
            fresh_evidence_count=2,
            total_evidence_count=2,
            structural_checks_passed=3,
            structural_checks_total=3,
            generation_method="dry_run",
        )

        # One concept missing evidence
        score_partial = calculate_confidence(
            asset_teaches=["concept_a", "concept_b"],
            concepts_with_evidence={"concept_a"},
            fresh_evidence_count=1,
            total_evidence_count=2,
            structural_checks_passed=3,
            structural_checks_total=3,
            generation_method="dry_run",
        )

        assert score_good.overall > score_partial.overall
        assert score_good.evidence > score_partial.evidence

    def test_stale_facts_lower_confidence(self):
        """2.3 — Stale evidence should produce lower freshness scores."""
        score_fresh = calculate_confidence(
            asset_teaches=["concept_a"],
            concepts_with_evidence={"concept_a"},
            fresh_evidence_count=3,
            total_evidence_count=3,
            structural_checks_passed=2,
            structural_checks_total=2,
            generation_method="dry_run",
        )

        score_stale = calculate_confidence(
            asset_teaches=["concept_a"],
            concepts_with_evidence={"concept_a"},
            fresh_evidence_count=1,
            total_evidence_count=3,
            structural_checks_passed=2,
            structural_checks_total=2,
            generation_method="dry_run",
        )

        assert score_fresh.freshness > score_stale.freshness
        assert score_fresh.overall > score_stale.overall

    def test_needs_review_threshold(self):
        """2.3b — Assets below threshold should be flagged for review."""
        low_score = ConfidenceScore(
            evidence=0.5, freshness=0.3, structural=1.0,
            transformation=1.0, overall=0.55,
        )
        high_score = ConfidenceScore(
            evidence=1.0, freshness=1.0, structural=1.0,
            transformation=1.0, overall=1.0,
        )

        assert needs_review(low_score) is True
        assert needs_review(high_score) is False

    def test_coverage_gaps_surfaced(self, food_graph):
        """2.4 — Sections without graph content should show placeholder text."""
        g, _ = food_graph

        result = generate_asset_dry_run(
            graph=g,
            template_name="facilitator_guide",
            concept_ids=["sauce_making"],
            audience_id="home_cook",
        )

        # sauce_making has no tasks with content, so exercises and
        # common_questions sections should have placeholder text
        sections = result["content_blocks"]
        exercises = sections.get("exercises", "")
        common_q = sections.get("common_questions", "")

        # These sections should either have real content or an explicit
        # placeholder — not be silently empty
        for name in ["exercises", "common_questions"]:
            content = sections.get(name, "")
            assert content.strip(), f"Section '{name}' is silently empty"


# ══════════════════════════════════════════════════════════════════════
# STAGE 3: Can we detect drift and trace impact?
# ══════════════════════════════════════════════════════════════════════


class TestStage3Drift:
    """Stage 3: Drift detection and impact tracing tests."""

    def test_drift_finds_stale_facts(self, claude_graph):
        """3.1 — Evidence change should identify all backed facts."""
        report = detect_drift(
            claude_graph,
            evidence_id="anthropic_tool_use_docs",
            change_description="Tool schema format updated",
        )

        stale_ids = {f.id for f in report.stale_facts}
        # tool_use_max_tools is backed by anthropic_tool_use_docs
        assert "tool_use_max_tools" in stale_ids
        assert len(report.stale_facts) > 0

    def test_drift_finds_stale_facts_food(self, food_graph):
        """3.1b — Food domain drift detection."""
        g, _ = food_graph

        report = detect_drift(
            g,
            evidence_id="serious_eats_pasta",
            change_description="Updated water ratio recommendation",
        )

        stale_ids = {f.id for f in report.stale_facts}
        assert "pasta_water_ratio" in stale_ids
        assert "pasta_salt_amount" in stale_ids

    def test_drift_propagates_to_assets(self, claude_graph):
        """3.2 — Stale facts should propagate to affected assets."""
        report = detect_drift(
            claude_graph,
            evidence_id="anthropic_tool_use_docs",
            change_description="Tool schema format updated",
        )

        affected_ids = {a.id for a in report.affected_assets}
        # Assets that teach tool_use should be affected
        assert len(report.affected_assets) > 0

    def test_drift_propagates_to_assets_food(self, food_graph):
        """3.2b — Food domain: evidence change reaches assets."""
        g, _ = food_graph

        report = detect_drift(
            g,
            evidence_id="serious_eats_pasta",
            change_description="Updated water ratio",
        )

        affected_ids = {a.id for a in report.affected_assets}
        assert "pasta_cooking_setup_guide_dry_run" in affected_ids

    def test_drift_cascading_impact(self, claude_graph):
        """3.3 — Impact should trace through concept dependencies."""
        report = detect_drift(
            claude_graph,
            evidence_id="anthropic_tool_use_docs",
            change_description="API change",
        )

        # The impact trace should reach beyond just direct evidence links.
        # anthropic_tool_use_docs → facts → tool_use concept → assets that teach it
        all_entity_ids = (
            {f.id for f in report.stale_facts}
            | {a.id for a in report.affected_assets}
        )
        assert len(all_entity_ids) > 1, "Impact should cascade beyond direct links"

    def test_confidence_drift_lifecycle(self):
        """3.4 — Confidence should drop on drift, recover on update."""
        # Before drift: all evidence fresh
        score_before = calculate_confidence(
            asset_teaches=["pasta_cooking"],
            concepts_with_evidence={"pasta_cooking"},
            fresh_evidence_count=2,
            total_evidence_count=2,
            structural_checks_passed=3,
            structural_checks_total=3,
            generation_method="dry_run",
        )

        # After drift: evidence is stale
        score_during = calculate_confidence(
            asset_teaches=["pasta_cooking"],
            concepts_with_evidence={"pasta_cooking"},
            fresh_evidence_count=0,
            total_evidence_count=2,
            structural_checks_passed=3,
            structural_checks_total=3,
            generation_method="dry_run",
        )

        # After update: evidence refreshed
        score_after = calculate_confidence(
            asset_teaches=["pasta_cooking"],
            concepts_with_evidence={"pasta_cooking"},
            fresh_evidence_count=2,
            total_evidence_count=2,
            structural_checks_passed=3,
            structural_checks_total=3,
            generation_method="dry_run",
        )

        assert score_before.overall > score_during.overall, "Drift should lower confidence"
        assert score_after.overall > score_during.overall, "Update should restore confidence"
        assert score_before.overall == score_after.overall, "Full update should fully restore"

    def test_regeneration_after_drift(self, food_graph):
        """3.5 — Regenerated asset should incorporate updated facts.

        Simulates: evidence changes → fact updated → asset regenerated →
        new content reflects the change.
        """
        g, tmp_path = food_graph

        # Generate before update
        result_before = generate_asset_dry_run(
            graph=g,
            template_name="setup_guide",
            concept_ids=["pasta_cooking"],
            audience_id="home_cook",
        )
        assert "1 gallon" in result_before["content"]

        # Update the concept content to reflect a changed fact
        concept_path = tmp_path / "concepts" / "pasta_cooking.yaml"
        updated_concept = yaml.safe_load(concept_path.read_text())
        updated_concept["content_block"] = (
            "Cook pasta in a large pot with 4 quarts of water per pound.\n"
            "Salt the water generously before adding pasta.\n"
            "Test for doneness 2 minutes before package time."
        )
        concept_path.write_text(yaml.dump(updated_concept, default_flow_style=False))

        # Reload graph
        g_updated = KnowledgeGraph(data_dir=tmp_path)

        # Regenerate
        result_after = generate_asset_dry_run(
            graph=g_updated,
            template_name="setup_guide",
            concept_ids=["pasta_cooking"],
            audience_id="home_cook",
        )

        assert "4 quarts" in result_after["content"]
        assert "1 gallon" not in result_after["content"]
