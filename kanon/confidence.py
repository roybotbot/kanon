"""Confidence scoring engine for Canon assets."""
from __future__ import annotations

from kanon.models.entities import ConfidenceScore

TRANSFORMATION_SCORES: dict[str, float] = {
    "dry_run": 1.0,
    "manual": 1.0,
    "llm_single": 0.7,
    "llm_adapted": 0.6,
    "llm_multi": 0.5,
}

WEIGHTS = {
    "evidence": 0.30,
    "freshness": 0.30,
    "structural": 0.20,
    "transformation": 0.20,
}

REVIEW_THRESHOLD = 0.70


def calculate_confidence(
    asset_teaches: list[str],
    concepts_with_evidence: set[str],
    fresh_evidence_count: int,
    total_evidence_count: int,
    structural_checks_passed: int,
    structural_checks_total: int,
    generation_method: str,
) -> ConfidenceScore:
    """Calculate a confidence score for a Canon asset.

    Args:
        asset_teaches: List of concept IDs the asset teaches.
        concepts_with_evidence: Set of concept IDs that have supporting evidence.
        fresh_evidence_count: Number of evidence links considered fresh.
        total_evidence_count: Total number of evidence links.
        structural_checks_passed: Number of structural validation checks passed.
        structural_checks_total: Total number of structural validation checks.
        generation_method: How the asset was generated (dry_run, manual, llm_*).

    Returns:
        A ConfidenceScore with individual dimension scores and a weighted overall.
    """
    # Evidence score: fraction of taught concepts that have evidence
    if asset_teaches:
        evidence = len(concepts_with_evidence & set(asset_teaches)) / len(asset_teaches)
    else:
        evidence = 0.0

    # Freshness score: fraction of evidence links that are fresh
    if total_evidence_count > 0:
        freshness = fresh_evidence_count / total_evidence_count
    else:
        freshness = 0.0

    # Structural score: fraction of structural checks passed
    if structural_checks_total > 0:
        structural = structural_checks_passed / structural_checks_total
    else:
        structural = 0.0

    # Transformation score: fixed by generation method
    transformation = TRANSFORMATION_SCORES.get(generation_method, 0.0)

    # Weighted overall
    overall = (
        evidence * WEIGHTS["evidence"]
        + freshness * WEIGHTS["freshness"]
        + structural * WEIGHTS["structural"]
        + transformation * WEIGHTS["transformation"]
    )

    return ConfidenceScore(
        evidence=evidence,
        freshness=freshness,
        structural=structural,
        transformation=transformation,
        overall=overall,
    )


def needs_review(score: ConfidenceScore) -> bool:
    """Return True if the asset's confidence score is below the review threshold."""
    return score.overall < REVIEW_THRESHOLD
