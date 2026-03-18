"""Citation validation for generated assets.

Implements {{fact:ID}} inline citation tags that trace every factual claim
in a generated asset back to a source fact in the ontology.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from kanon.graph import KnowledgeGraph
from kanon.models.entities import Fact

CITATION_PATTERN = re.compile(r"\{\{fact:([a-zA-Z0-9_]+)\}\}")


@dataclass
class CitationReport:
    """Result of validating citations in generated content."""

    total_citations: int = 0
    valid: list[str] = field(default_factory=list)
    missing_from_graph: list[str] = field(default_factory=list)
    superseded: list[str] = field(default_factory=list)
    retracted: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Pass if all citations reference active facts and none are missing."""
        return (
            not self.missing_from_graph
            and not self.superseded
            and not self.retracted
        )

    @property
    def failures(self) -> list[str]:
        """Human-readable list of all failures."""
        problems: list[str] = []
        for fid in self.missing_from_graph:
            problems.append("{{fact:" + fid + "}}: not found in knowledge graph")
        for fid in self.superseded:
            problems.append("{{fact:" + fid + "}}: fact is superseded")
        for fid in self.retracted:
            problems.append("{{fact:" + fid + "}}: fact is retracted")
        return problems


def extract_citations(content: str) -> list[str]:
    """Extract all {{fact:ID}} tags from content, preserving order."""
    return CITATION_PATTERN.findall(content)


def validate_citations(content: str, graph: KnowledgeGraph) -> CitationReport:
    """Validate all {{fact:ID}} citations in content against the knowledge graph.

    Checks:
    - Each cited fact ID exists in the graph
    - Each cited fact is active (not superseded or retracted)

    Returns a CitationReport with categorized results.
    """
    fact_ids = extract_citations(content)
    report = CitationReport(total_citations=len(fact_ids))

    seen: set[str] = set()
    for fid in fact_ids:
        if fid in seen:
            continue
        seen.add(fid)

        entity = graph.get(fid)
        if entity is None or not isinstance(entity, Fact):
            report.missing_from_graph.append(fid)
        elif entity.status == "superseded":
            report.superseded.append(fid)
        elif entity.status == "retracted":
            report.retracted.append(fid)
        else:
            report.valid.append(fid)

    return report


def strip_citations(content: str) -> str:
    """Remove all {{fact:ID}} tags from content for clean output.

    Handles tags with optional surrounding whitespace so the output
    reads naturally.
    """
    # Remove citation with any single leading space
    cleaned = re.sub(r" ?\{\{fact:[a-zA-Z0-9_]+\}\}", "", content)
    return cleaned
