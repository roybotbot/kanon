"""Review conditions for generated assets.

Hard failure conditions that determine whether an asset needs review.
These are binary pass/fail — not confidence scores. An asset either
passes all conditions or it fails with specific, actionable reasons.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

import yaml

from kanon.citations import validate_citations
from kanon.graph import KnowledgeGraph
from kanon.models.entities import Asset, Evidence, Fact


@dataclass
class ReviewResult:
    """Result of reviewing an asset against hard failure conditions."""

    asset_id: str
    asset_name: str
    lifecycle_state: str
    failures: list[str] = field(default_factory=list)
    stale_citations: list[str] = field(default_factory=list)
    evidence_changed: list[str] = field(default_factory=list)

    @property
    def passes(self) -> bool:
        return len(self.failures) == 0


def review_asset(asset: Asset, graph: KnowledgeGraph) -> ReviewResult:
    """Check an asset against hard failure conditions.

    Conditions:
    1. Any cited fact is superseded → fail
    2. Any cited fact is retracted → fail
    3. Any cited fact ID doesn't exist → fail
    4. Any evidence source was verified after asset was last updated → fail
       (evidence may have changed since the asset was generated)
    """
    result = ReviewResult(
        asset_id=asset.id,
        asset_name=asset.name,
        lifecycle_state=asset.lifecycle_state,
    )

    # 1-3: Citation validation
    if asset.content:
        citation_report = validate_citations(asset.content, graph)
        for fid in citation_report.superseded:
            result.stale_citations.append(fid)
            fact = graph.get(fid)
            claim = fact.claim if isinstance(fact, Fact) else fid
            result.failures.append(
                f"Cites superseded fact '{fid}' ({claim})"
            )
        for fid in citation_report.retracted:
            result.stale_citations.append(fid)
            fact = graph.get(fid)
            claim = fact.claim if isinstance(fact, Fact) else fid
            result.failures.append(
                f"Cites retracted fact '{fid}' ({claim})"
            )
        for fid in citation_report.missing_from_graph:
            result.failures.append(
                f"Cites unknown fact '{fid}' (not in knowledge graph)"
            )

    # 4: Evidence freshness
    for evidence_id in asset.evidence_links:
        evidence = graph.get(evidence_id)
        if not isinstance(evidence, Evidence):
            continue
        # Compare evidence.last_verified against asset.last_updated
        asset_date = asset.last_updated.date() if isinstance(asset.last_updated, datetime) else asset.last_updated
        if evidence.last_verified > asset_date:
            result.evidence_changed.append(evidence_id)
            result.failures.append(
                f"Evidence '{evidence_id}' was verified on {evidence.last_verified}, "
                f"after asset was last updated on {asset_date}"
            )

    return result


def review_all_assets(graph: KnowledgeGraph) -> list[ReviewResult]:
    """Review all assets in the graph."""
    results: list[ReviewResult] = []
    for entity in graph.entities.values():
        if isinstance(entity, Asset):
            results.append(review_asset(entity, graph))
    return sorted(results, key=lambda r: (r.passes, r.asset_id))


def approve_asset(asset_id: str, assets_dir: Path) -> None:
    """Set asset lifecycle_state to 'approved' and update last_updated."""
    path = assets_dir / f"{asset_id}.yaml"
    if not path.exists():
        raise ValueError(f"Asset file not found: {path}")

    data = yaml.safe_load(path.read_text())
    data["lifecycle_state"] = "approved"
    data["last_updated"] = datetime.now(UTC).isoformat()
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))


def reject_asset(asset_id: str, assets_dir: Path) -> None:
    """Set asset lifecycle_state to 'needs_review'."""
    path = assets_dir / f"{asset_id}.yaml"
    if not path.exists():
        raise ValueError(f"Asset file not found: {path}")

    data = yaml.safe_load(path.read_text())
    data["lifecycle_state"] = "needs_review"
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
