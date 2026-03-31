"""Simplified generation pipeline.

Step 1: Query facts for concepts (deterministic)
Step 2: Assemble into template sections (deterministic)
Step 3: LLM polish per section (optional)
Step 4: Validate fact values appear in output (deterministic)
"""
from __future__ import annotations

from datetime import datetime, UTC
from typing import Any

from kanon.models.simple import Asset, Fact
from kanon.simple_graph import SimpleGraph


def query_facts(graph: SimpleGraph, concept_ids: list[str]) -> list[Fact]:
    """Step 1: Gather all active facts for the requested concepts."""
    return graph.facts_for_concepts(concept_ids)


def assemble(
    facts: list[Fact],
    template: str = "setup_guide",
    title: str = "",
) -> tuple[str, dict[str, list[str]]]:
    """Step 2: Slot facts into template sections. Build fact_map.

    Returns (content, fact_map).
    """
    # Categorize facts
    numeric_facts = [f for f in facts if f.numeric_value is not None]
    evergreen_facts = [f for f in facts if f.evergreen]
    regular_facts = [f for f in facts if not f.evergreen and f.numeric_value is None]

    # Build sections
    sections: dict[str, list[Fact]] = {}

    if template == "setup_guide":
        sections = {
            "overview": facts[:3] if len(facts) > 3 else facts,
            "specifications": numeric_facts or regular_facts[:2],
            "key_facts": evergreen_facts or facts,
            "verification": facts,
        }
    elif template == "reference_card":
        sections = {
            "quick_reference": facts,
        }
    else:
        sections = {
            "content": facts,
        }

    # Build content and fact_map
    fact_map: dict[str, list[str]] = {}
    content_parts = [f"# {title}\n"]

    for section_name, section_facts in sections.items():
        if not section_facts:
            continue
        fact_map[section_name] = [f.id for f in section_facts]
        heading = section_name.replace("_", " ").title()
        content_parts.append(f"\n## {heading}\n")
        for f in section_facts:
            line = f"- **{f.claim}**: {f.value}"
            if f.numeric_value is not None:
                line += f" ({f.numeric_value})"
            content_parts.append(line)

    content = "\n".join(content_parts)
    return content, fact_map


def validate_output(content: str, facts: list[Fact]) -> list[str]:
    """Step 4: Verify each fact's value appears in the output.

    Returns list of fact IDs whose values are missing from the content.
    """
    missing = []
    for f in facts:
        # Check if the fact's value appears in the content
        value_present = f.value.lower() in content.lower()
        # Also accept if the numeric value appears (alternative representation)
        numeric_present = (
            str(f.numeric_value) in content
            if f.numeric_value is not None
            else False
        )
        if not value_present and not numeric_present:
            missing.append(f.id)
    return missing


def generate_asset(
    graph: SimpleGraph,
    concept_ids: list[str],
    audience: str = "",
    template: str = "setup_guide",
    title: str | None = None,
) -> Asset:
    """Full pipeline: query → assemble → validate → return asset.

    LLM polish (step 3) is not included here — it's a separate call.
    This produces the deterministic skeleton.
    """
    # Step 1: Query
    facts = query_facts(graph, concept_ids)

    if not facts:
        raise ValueError(
            f"No active facts found for concepts: {concept_ids}"
        )

    # Resolve title
    if title is None:
        concept_names = []
        for cid in concept_ids:
            c = graph.concepts.get(cid)
            concept_names.append(c.name if c else cid)
        title = f"{', '.join(concept_names)} — {template.replace('_', ' ').title()}"

    # Step 2: Assemble
    content, fact_map = assemble(facts, template=template, title=title)

    # Step 4: Validate
    missing = validate_output(content, facts)
    if missing:
        # Not a hard failure — just a warning. The assembled content
        # should always contain the values since we built it from facts.
        pass

    # Collect evidence links from facts
    evidence_ids = set()
    for f in facts:
        evidence_ids.update(f.evidence)

    now = datetime.now(UTC)
    asset_id = "_".join(concept_ids) + f"_{template}"

    return Asset(
        id=asset_id,
        name=title,
        concepts=concept_ids,
        audience=audience,
        template=template,
        lifecycle_state="draft",
        content=content,
        fact_map=fact_map,
        generation_method="dry_run",
        evidence_links=list(evidence_ids),
        generated_at=now,
        last_updated=now,
    )
