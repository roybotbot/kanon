"""Tests for Experiment 03: Governance Workflow.

Tests hard failure conditions, review command, approve/reject actions,
and drift + citation integration.
"""
from __future__ import annotations

from datetime import date, datetime, UTC
from pathlib import Path

import pytest
import yaml

from kanon.graph import KnowledgeGraph
from kanon.models.entities import Asset, ConfidenceScore, Fact


# ── Fixtures ─────────────────────────────────────────────────────────


REVIEW_ENTITIES = {
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
            "id": "pasta_old_ratio",
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
            "id": "pasta_rinse",
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
    "assets": [
        {
            "id": "pasta_guide_good",
            "name": "Pasta Guide (Good)",
            "asset_type": "guide",
            "delivery_format": "setup_guide",
            "lifecycle_state": "draft",
            "teaches": ["pasta_cooking"],
            "targets": ["home_cook"],
            "evidence_links": ["serious_eats_pasta"],
            "generation_method": "llm",
            "generated_at": "2025-07-01T00:00:00",
            "last_updated": "2025-07-01T00:00:00",
            "confidence": {
                "evidence": 1.0,
                "freshness": 1.0,
                "structural": 1.0,
                "transformation": 0.7,
                "overall": 0.94,
            },
            "content": "Use 1 gallon of water per pound {{fact:pasta_water_ratio}}.",
        },
        {
            "id": "pasta_guide_stale",
            "name": "Pasta Guide (Stale)",
            "asset_type": "guide",
            "delivery_format": "setup_guide",
            "lifecycle_state": "draft",
            "teaches": ["pasta_cooking"],
            "targets": ["home_cook"],
            "evidence_links": ["serious_eats_pasta"],
            "generation_method": "llm",
            "generated_at": "2024-06-01T00:00:00",
            "last_updated": "2024-06-01T00:00:00",
            "confidence": {
                "evidence": 1.0,
                "freshness": 1.0,
                "structural": 1.0,
                "transformation": 0.7,
                "overall": 0.94,
            },
            "content": "Use 6 quarts of water {{fact:pasta_old_ratio}} and rinse after {{fact:pasta_rinse}}.",
        },
        {
            "id": "pasta_guide_nocitations",
            "name": "Pasta Guide (No Citations)",
            "asset_type": "guide",
            "delivery_format": "setup_guide",
            "lifecycle_state": "reviewed",
            "teaches": ["pasta_cooking"],
            "targets": ["home_cook"],
            "evidence_links": ["serious_eats_pasta"],
            "generation_method": "dry_run",
            "generated_at": "2025-07-01T00:00:00",
            "last_updated": "2025-07-01T00:00:00",
            "confidence": {
                "evidence": 1.0,
                "freshness": 1.0,
                "structural": 1.0,
                "transformation": 1.0,
                "overall": 1.0,
            },
            "content": "Cook pasta in boiling water.",
        },
        {
            "id": "pasta_guide_old_evidence",
            "name": "Pasta Guide (Old Evidence)",
            "asset_type": "guide",
            "delivery_format": "setup_guide",
            "lifecycle_state": "approved",
            "teaches": ["pasta_cooking"],
            "targets": ["home_cook"],
            "evidence_links": ["serious_eats_pasta"],
            "generation_method": "llm",
            "generated_at": "2025-01-01T00:00:00",
            "last_updated": "2025-01-01T00:00:00",
            "confidence": {
                "evidence": 1.0,
                "freshness": 1.0,
                "structural": 1.0,
                "transformation": 0.7,
                "overall": 0.94,
            },
            "content": "Use 1 gallon of water per pound {{fact:pasta_water_ratio}}.",
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


@pytest.fixture
def review_graph(tmp_path):
    """Graph with assets in various review states."""
    for entity_type, items in REVIEW_ENTITIES.items():
        entity_dir = tmp_path / entity_type
        entity_dir.mkdir()
        for item in items:
            (entity_dir / f"{item['id']}.yaml").write_text(
                yaml.dump(item, default_flow_style=False)
            )

    for subdir in ["tasks", "capabilities", "constraints", "objectives"]:
        (tmp_path / subdir).mkdir(exist_ok=True)

    return KnowledgeGraph(data_dir=tmp_path), tmp_path


# ══════════════════════════════════════════════════════════════════════
# Review Conditions
# ══════════════════════════════════════════════════════════════════════


class TestReviewConditions:
    def test_superseded_fact_cited_fails(self, review_graph):
        """Asset citing a superseded fact should fail review."""
        from kanon.review import review_asset

        g, _ = review_graph
        asset = g.get("pasta_guide_stale")
        result = review_asset(asset, g)
        assert not result.passes
        assert "pasta_old_ratio" in result.stale_citations

    def test_retracted_fact_cited_fails(self, review_graph):
        """Asset citing a retracted fact should fail review."""
        from kanon.review import review_asset

        g, _ = review_graph
        asset = g.get("pasta_guide_stale")
        result = review_asset(asset, g)
        assert not result.passes
        assert "pasta_rinse" in result.stale_citations

    def test_evidence_changed_since_generation_fails(self, review_graph):
        """Asset generated before evidence was last verified should fail."""
        from kanon.review import review_asset

        g, _ = review_graph
        # pasta_guide_old_evidence: generated 2025-01-01, evidence verified 2025-06-01
        asset = g.get("pasta_guide_old_evidence")
        result = review_asset(asset, g)
        assert not result.passes
        assert "serious_eats_pasta" in result.evidence_changed

    def test_all_active_facts_passes(self, review_graph):
        """Asset with all active citations passes review."""
        from kanon.review import review_asset

        g, _ = review_graph
        asset = g.get("pasta_guide_good")
        result = review_asset(asset, g)
        assert result.passes

    def test_asset_without_citations_passes(self, review_graph):
        """Asset with no citations (dry-run) passes review."""
        from kanon.review import review_asset

        g, _ = review_graph
        asset = g.get("pasta_guide_nocitations")
        result = review_asset(asset, g)
        assert result.passes

    def test_multiple_failures_reported(self, review_graph):
        """Asset with multiple issues reports all of them."""
        from kanon.review import review_asset

        g, _ = review_graph
        asset = g.get("pasta_guide_stale")
        result = review_asset(asset, g)
        assert not result.passes
        # Should have both stale citations and evidence changed
        assert len(result.failures) >= 2


# ══════════════════════════════════════════════════════════════════════
# Approve / Reject
# ══════════════════════════════════════════════════════════════════════


class TestApproveReject:
    def test_approve_updates_lifecycle_state(self, review_graph):
        """Approving an asset sets lifecycle_state to 'approved'."""
        from kanon.review import approve_asset

        _, tmp_path = review_graph
        approve_asset("pasta_guide_good", tmp_path / "assets")
        data = yaml.safe_load((tmp_path / "assets" / "pasta_guide_good.yaml").read_text())
        assert data["lifecycle_state"] == "approved"

    def test_reject_updates_lifecycle_state(self, review_graph):
        """Rejecting an asset sets lifecycle_state to 'needs_review'."""
        from kanon.review import reject_asset

        _, tmp_path = review_graph
        reject_asset("pasta_guide_stale", tmp_path / "assets")
        data = yaml.safe_load((tmp_path / "assets" / "pasta_guide_stale.yaml").read_text())
        assert data["lifecycle_state"] == "needs_review"

    def test_approve_updates_last_updated(self, review_graph):
        """Approval updates the last_updated timestamp."""
        from kanon.review import approve_asset

        _, tmp_path = review_graph
        before = yaml.safe_load((tmp_path / "assets" / "pasta_guide_good.yaml").read_text())
        approve_asset("pasta_guide_good", tmp_path / "assets")
        after = yaml.safe_load((tmp_path / "assets" / "pasta_guide_good.yaml").read_text())
        assert after["last_updated"] != before["last_updated"]


# ══════════════════════════════════════════════════════════════════════
# Drift → Review Integration
# ══════════════════════════════════════════════════════════════════════


class TestDriftReviewIntegration:
    def test_drift_then_review_catches_stale_citations(self, review_graph):
        """After drift, review should flag affected assets with stale citations."""
        from kanon.drift import detect_drift
        from kanon.review import review_asset

        g, _ = review_graph

        # Detect drift
        report = detect_drift(g, "serious_eats_pasta", "Water ratio updated")
        assert len(report.stale_facts) > 0

        # Review affected assets — at least one should fail
        failing = []
        for asset in report.affected_assets:
            result = review_asset(asset, g)
            if not result.passes:
                failing.append(result)

        assert len(failing) > 0, "At least one drift-affected asset should fail review"
        # The stale guide should be among the failures
        stale_ids = {r.asset_id for r in failing}
        assert "pasta_guide_stale" in stale_ids

    def test_full_cycle_evidence_to_review(self, review_graph):
        """Evidence change → drift → review surfaces exact failures."""
        from kanon.drift import detect_drift
        from kanon.review import review_asset, review_all_assets

        g, _ = review_graph

        # Review all — some should already fail
        results = review_all_assets(g)
        failing = [r for r in results if not r.passes]
        assert len(failing) > 0

        # Each failure has specific, actionable information
        for result in failing:
            assert result.asset_id
            assert result.asset_name
            assert len(result.failures) > 0
