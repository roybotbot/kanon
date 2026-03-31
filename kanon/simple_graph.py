"""Simplified knowledge graph for the 4-type entity model.

Loads Evidence, Fact, Concept, Asset from YAML directories.
Facts belong to multiple concepts. Concepts are just labels.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Optional

import yaml

from kanon.models.simple import Asset, Concept, Evidence, Fact


class SimpleGraph:
    """Knowledge graph for the simplified entity model."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.evidence: dict[str, Evidence] = {}
        self.facts: dict[str, Fact] = {}
        self.concepts: dict[str, Concept] = {}
        self.assets: dict[str, Asset] = {}

        if data_dir is not None:
            self.load(data_dir)

    def load(self, data_dir: Path) -> None:
        """Load all entities from YAML directories."""
        self.evidence = self._load_type(data_dir / "evidence", Evidence)
        self.facts = self._load_type(data_dir / "facts", Fact)
        self.concepts = self._load_type(data_dir / "concepts", Concept)
        self.assets = self._load_type(data_dir / "assets", Asset)

    def _load_type(self, directory: Path, model_class) -> dict:
        """Load all YAML files in a directory as a given model type."""
        entities = {}
        if not directory.exists():
            return entities
        for path in sorted(directory.glob("*.yaml")):
            data = yaml.safe_load(path.read_text())
            if data:
                entity = model_class(**data)
                entities[entity.id] = entity
        return entities

    # ── Queries ──────────────────────────────────────────────────

    def facts_for_concept(self, concept_id: str) -> list[Fact]:
        """Get all active facts belonging to a concept."""
        return [
            f for f in self.facts.values()
            if concept_id in f.concepts and f.status == "active"
        ]

    def facts_for_concepts(self, concept_ids: list[str]) -> list[Fact]:
        """Get all active facts belonging to any of the given concepts."""
        id_set = set(concept_ids)
        return [
            f for f in self.facts.values()
            if id_set & set(f.concepts) and f.status == "active"
        ]

    def facts_by_evidence(self, evidence_id: str) -> list[Fact]:
        """Get all facts backed by a specific evidence source."""
        return [
            f for f in self.facts.values()
            if evidence_id in f.evidence
        ]

    def evidence_for_fact(self, fact: Fact) -> list[Evidence]:
        """Get all evidence sources backing a fact."""
        return [
            self.evidence[eid]
            for eid in fact.evidence
            if eid in self.evidence
        ]

    def max_trust_for_fact(self, fact: Fact) -> float:
        """Get the highest trust score among a fact's evidence sources."""
        sources = self.evidence_for_fact(fact)
        if not sources:
            return 0.0
        return max(e.trust for e in sources)

    def contradictions_for_concept(self, concept_id: str) -> list[tuple[Fact, Fact, str]]:
        """Find active facts with the same claim but different values.

        Returns list of (fact_a, fact_b, claim) tuples.
        """
        facts = self.facts_for_concept(concept_id)
        by_claim: dict[str, list[Fact]] = defaultdict(list)
        for f in facts:
            by_claim[f.claim].append(f)

        conflicts = []
        for claim, group in by_claim.items():
            if len(group) > 1:
                for i, a in enumerate(group):
                    for b in group[i + 1:]:
                        if a.value != b.value:
                            conflicts.append((a, b, claim))
        return conflicts

    # ── Drift ────────────────────────────────────────────────────

    def affected_by_evidence(self, evidence_id: str) -> dict:
        """Trace impact of an evidence change.

        Returns {facts: [...], concepts: [...], assets: [...]}.
        """
        stale_facts = self.facts_by_evidence(evidence_id)
        affected_concepts = set()
        for f in stale_facts:
            affected_concepts.update(f.concepts)

        affected_assets = [
            a for a in self.assets.values()
            if set(a.concepts) & affected_concepts
        ]

        return {
            "facts": stale_facts,
            "concepts": list(affected_concepts),
            "assets": affected_assets,
        }
