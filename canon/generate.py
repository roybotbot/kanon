from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any
import yaml

from canon.graph import KnowledgeGraph
from canon.models.entities import Concept, Capability, Task, Audience, Fact

TEMPLATES_DIR = Path(__file__).parent / "templates"


def load_template(name: str) -> dict:
    path = TEMPLATES_DIR / f"{name}.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def generate_asset_dry_run(
    graph: KnowledgeGraph,
    template_name: str,
    concept_ids: list[str],
    audience_id: str,
) -> dict[str, Any]:
    template = load_template(template_name)

    # Validate concepts exist
    concepts = []
    for cid in concept_ids:
        entity = graph.get(cid)
        if not isinstance(entity, Concept):
            raise ValueError(f"Concept '{cid}' not found in graph")
        concepts.append(entity)

    # Validate audience exists
    audience = graph.get(audience_id)
    if not isinstance(audience, Audience):
        raise ValueError(f"Audience '{audience_id}' not found in graph")

    # Resolve subgraph
    subgraph = graph.subgraph(concept_ids)

    # Build sections
    sections = {}
    for section_name in template["sections"]:
        sections[section_name] = _build_section(section_name, concepts, subgraph, audience)

    # Assemble content
    title_concepts = ", ".join(c.name for c in concepts)
    content_parts = [f"# {title_concepts} - {template_name.replace('_', ' ').title()}\n"]
    for section_name, section_content in sections.items():
        content_parts.append(f"## {section_name.replace('_', ' ').title()}\n")
        content_parts.append(section_content + "\n")

    content = "\n".join(content_parts)
    now = datetime.utcnow()

    return {
        "name": f"{title_concepts} {template_name.replace('_', ' ').title()}",
        "asset_type": "guide",
        "delivery_format": template_name,
        "lifecycle_state": "draft",
        "teaches": concept_ids,
        "targets": [audience_id],
        "evidence_links": _collect_evidence(subgraph),
        "generation_method": "dry_run",
        "generated_at": now.isoformat(),
        "last_updated": now.isoformat(),
        "content": content,
        "content_blocks": sections,
    }


def _build_section(section_name, concepts, subgraph, audience):
    parts = []
    if section_name == "overview":
        for c in concepts:
            parts.append(f"**{c.name}:** {c.description}")
    elif section_name == "key_concepts":
        for entity in subgraph:
            if isinstance(entity, Concept) and entity.content_block:
                parts.append(f"### {entity.name}\n{entity.content_block}")
    elif section_name == "prerequisites":
        for c in concepts:
            for prereq_id in c.prerequisites:
                parts.append(f"- {prereq_id}")
    elif section_name in ("procedure", "demonstration_walkthrough"):
        for entity in subgraph:
            if isinstance(entity, Task) and entity.content_block:
                parts.append(f"### {entity.name}\n{entity.content_block}")
            elif isinstance(entity, Task) and entity.steps:
                steps = "\n".join(f"{i+1}. {s}" for i, s in enumerate(entity.steps))
                parts.append(f"### {entity.name}\n{steps}")
    else:
        for c in concepts:
            if c.content_block:
                parts.append(c.content_block)
    return "\n\n".join(parts) if parts else f"*{section_name.replace('_', ' ').title()} content to be added.*"


def _collect_evidence(subgraph):
    evidence_ids = set()
    for entity in subgraph:
        if isinstance(entity, Fact):
            evidence_ids.update(entity.evidence)
    return list(evidence_ids)
