from __future__ import annotations
from dataclasses import dataclass, field
from kanon.graph import KnowledgeGraph
from kanon.models.entities import Asset, Fact


@dataclass
class DriftReport:
    evidence_id: str
    change_description: str
    stale_facts: list[Fact] = field(default_factory=list)
    affected_assets: list[Asset] = field(default_factory=list)


def detect_drift(graph: KnowledgeGraph, evidence_id: str, change_description: str) -> DriftReport:
    report = DriftReport(evidence_id=evidence_id, change_description=change_description)
    impacted = graph.impact_of(evidence_id)
    for entity in impacted:
        if isinstance(entity, Fact):
            report.stale_facts.append(entity)
        elif isinstance(entity, Asset):
            report.affected_assets.append(entity)
    return report
