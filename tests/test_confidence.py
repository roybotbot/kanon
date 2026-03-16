"""Tests for the confidence scoring engine."""
import pytest

from canon.confidence import calculate_confidence, needs_review
from canon.models.entities import ConfidenceScore


class TestEvidenceScore:
    def test_all_concepts_have_evidence(self):
        score = calculate_confidence(
            asset_teaches=["concept:a", "concept:b"],
            concepts_with_evidence={"concept:a", "concept:b"},
            fresh_evidence_count=2,
            total_evidence_count=2,
            structural_checks_passed=1,
            structural_checks_total=1,
            generation_method="dry_run",
        )
        assert score.evidence == 1.0

    def test_partial_evidence(self):
        score = calculate_confidence(
            asset_teaches=["concept:a", "concept:b", "concept:c"],
            concepts_with_evidence={"concept:a", "concept:b"},
            fresh_evidence_count=2,
            total_evidence_count=2,
            structural_checks_passed=1,
            structural_checks_total=1,
            generation_method="dry_run",
        )
        assert round(score.evidence, 2) == 0.67

    def test_no_evidence(self):
        score = calculate_confidence(
            asset_teaches=["concept:a"],
            concepts_with_evidence=set(),
            fresh_evidence_count=0,
            total_evidence_count=0,
            structural_checks_passed=1,
            structural_checks_total=1,
            generation_method="dry_run",
        )
        assert score.evidence == 0.0


class TestFreshnessScore:
    def test_all_fresh(self):
        score = calculate_confidence(
            asset_teaches=["concept:a"],
            concepts_with_evidence={"concept:a"},
            fresh_evidence_count=3,
            total_evidence_count=3,
            structural_checks_passed=1,
            structural_checks_total=1,
            generation_method="dry_run",
        )
        assert score.freshness == 1.0

    def test_one_stale(self):
        score = calculate_confidence(
            asset_teaches=["concept:a"],
            concepts_with_evidence={"concept:a"},
            fresh_evidence_count=2,
            total_evidence_count=3,
            structural_checks_passed=1,
            structural_checks_total=1,
            generation_method="dry_run",
        )
        assert round(score.freshness, 2) == 0.67

    def test_no_evidence_links(self):
        score = calculate_confidence(
            asset_teaches=[],
            concepts_with_evidence=set(),
            fresh_evidence_count=0,
            total_evidence_count=0,
            structural_checks_passed=1,
            structural_checks_total=1,
            generation_method="dry_run",
        )
        assert score.freshness == 0.0


class TestTransformationScore:
    def test_dry_run(self):
        score = calculate_confidence(
            asset_teaches=["concept:a"],
            concepts_with_evidence={"concept:a"},
            fresh_evidence_count=1,
            total_evidence_count=1,
            structural_checks_passed=1,
            structural_checks_total=1,
            generation_method="dry_run",
        )
        assert score.transformation == 1.0

    def test_manual(self):
        score = calculate_confidence(
            asset_teaches=["concept:a"],
            concepts_with_evidence={"concept:a"},
            fresh_evidence_count=1,
            total_evidence_count=1,
            structural_checks_passed=1,
            structural_checks_total=1,
            generation_method="manual",
        )
        assert score.transformation == 1.0

    def test_llm_single(self):
        score = calculate_confidence(
            asset_teaches=["concept:a"],
            concepts_with_evidence={"concept:a"},
            fresh_evidence_count=1,
            total_evidence_count=1,
            structural_checks_passed=1,
            structural_checks_total=1,
            generation_method="llm_single",
        )
        assert score.transformation == 0.7

    def test_llm_adapted(self):
        score = calculate_confidence(
            asset_teaches=["concept:a"],
            concepts_with_evidence={"concept:a"},
            fresh_evidence_count=1,
            total_evidence_count=1,
            structural_checks_passed=1,
            structural_checks_total=1,
            generation_method="llm_adapted",
        )
        assert score.transformation == 0.6

    def test_llm_multi(self):
        score = calculate_confidence(
            asset_teaches=["concept:a"],
            concepts_with_evidence={"concept:a"},
            fresh_evidence_count=1,
            total_evidence_count=1,
            structural_checks_passed=1,
            structural_checks_total=1,
            generation_method="llm_multi",
        )
        assert score.transformation == 0.5


class TestOverallScore:
    def test_perfect_dry_run(self):
        score = calculate_confidence(
            asset_teaches=["concept:a"],
            concepts_with_evidence={"concept:a"},
            fresh_evidence_count=1,
            total_evidence_count=1,
            structural_checks_passed=1,
            structural_checks_total=1,
            generation_method="dry_run",
        )
        assert score.overall == 1.0

    def test_weighted_average(self):
        # evidence=0.5, freshness=0.5, structural=0.5, transform=0.7
        # (0.5*0.30) + (0.5*0.30) + (0.5*0.20) + (0.7*0.20) = 0.54
        score = calculate_confidence(
            asset_teaches=["concept:a", "concept:b"],
            concepts_with_evidence={"concept:a"},
            fresh_evidence_count=1,
            total_evidence_count=2,
            structural_checks_passed=1,
            structural_checks_total=2,
            generation_method="llm_single",
        )
        assert score.evidence == 0.5
        assert score.freshness == 0.5
        assert score.structural == 0.5
        assert score.transformation == 0.7
        assert round(score.overall, 2) == 0.54

    def test_below_threshold(self):
        score = calculate_confidence(
            asset_teaches=["concept:a", "concept:b"],
            concepts_with_evidence={"concept:a"},
            fresh_evidence_count=1,
            total_evidence_count=2,
            structural_checks_passed=1,
            structural_checks_total=2,
            generation_method="llm_single",
        )
        assert score.overall < 0.70


class TestNeedsReview:
    def test_above_threshold(self):
        score = ConfidenceScore(
            evidence=1.0,
            freshness=1.0,
            structural=1.0,
            transformation=0.7,
            overall=0.94,
        )
        assert needs_review(score) is False

    def test_below_threshold(self):
        score = ConfidenceScore(
            evidence=0.5,
            freshness=0.5,
            structural=0.5,
            transformation=0.7,
            overall=0.54,
        )
        assert needs_review(score) is True

    def test_at_threshold(self):
        score = ConfidenceScore(
            evidence=1.0,
            freshness=1.0,
            structural=1.0,
            transformation=1.0,
            overall=0.70,
        )
        assert needs_review(score) is False
