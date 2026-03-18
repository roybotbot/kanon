from __future__ import annotations
import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any
import yaml

import httpx

from kanon.graph import KnowledgeGraph
from kanon.models.entities import Concept, Capability, Task, Audience, Fact, Evidence

TEMPLATES_DIR = Path(__file__).parent / "templates"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-6"


def _validate_inputs(
    graph: KnowledgeGraph,
    concept_ids: list[str],
    audience_id: str,
) -> tuple[list[Concept], Audience]:
    """Validate that concept and audience IDs exist in the graph.

    Returns the resolved Concept and Audience entities.
    Raises ValueError if any ID is missing or the wrong type.
    """
    concepts = []
    for cid in concept_ids:
        entity = graph.get(cid)
        if not isinstance(entity, Concept):
            raise ValueError(f"Concept '{cid}' not found in graph")
        concepts.append(entity)

    audience = graph.get(audience_id)
    if not isinstance(audience, Audience):
        raise ValueError(f"Audience '{audience_id}' not found in graph")

    return concepts, audience


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
    concepts, audience = _validate_inputs(graph, concept_ids, audience_id)

    # Resolve subgraph (forward edges from concepts)
    subgraph = graph.subgraph(concept_ids)

    # Also include facts that reference these concepts (reverse relationship)
    concept_id_set = {c.id for c in concepts}
    for entity in graph.entities.values():
        if isinstance(entity, Fact) and entity.concept in concept_id_set:
            if entity not in subgraph:
                subgraph.append(entity)

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
    now = datetime.now(UTC)

    return {
        "name": f"{title_concepts} {template_name.replace('_', ' ').title()}",
        "asset_type": "guide",
        "delivery_format": template_name,
        "lifecycle_state": "draft",
        "teaches": concept_ids,
        "targets": [audience_id],
        "evidence_links": _collect_evidence(subgraph, graph),
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
    elif section_name == "learning_objectives":
        from kanon.models.entities import LearningObjective
        for entity in subgraph:
            if isinstance(entity, LearningObjective):
                parts.append(f"- {entity.description}")
    elif section_name == "verification":
        # Gather facts as verifiable claims
        facts = [e for e in subgraph if isinstance(e, Fact) and e.status == "active"]
        if facts:
            parts.append("Verify the following hold true:")
            for f in facts:
                line = f"- **{f.claim}**: {f.value}"
                if f.condition:
                    line += f" ({f.condition})"
                parts.append(line)
        # Add task completion checks
        tasks = [e for e in subgraph if isinstance(e, Task)]
        if tasks:
            parts.append("\nConfirm these tasks complete successfully:")
            for t in tasks:
                parts.append(f"- [ ] {t.name}: {t.description}")
    elif section_name == "troubleshooting":
        # Derive troubleshooting from tasks and their steps
        tasks = [e for e in subgraph if isinstance(e, Task)]
        if tasks:
            for t in tasks:
                parts.append(f"### {t.name}")
                if t.steps:
                    parts.append(f"If {t.name.lower()} fails, check each step:")
                    for i, step in enumerate(t.steps, 1):
                        parts.append(f"  {i}. Verify: {step}")
                elif t.content_block:
                    parts.append(t.content_block)
    elif section_name == "exercises":
        # Generate exercise prompts from tasks
        tasks = [e for e in subgraph if isinstance(e, Task)]
        if tasks:
            for i, t in enumerate(tasks, 1):
                parts.append(f"**Exercise {i}: {t.name}**")
                parts.append(f"Objective: {t.description}")
                if t.steps:
                    parts.append("Steps:")
                    for j, step in enumerate(t.steps, 1):
                        parts.append(f"  {j}. {step}")
    elif section_name == "common_questions":
        # Derive Q&A from facts
        facts = [e for e in subgraph if isinstance(e, Fact) and e.status == "active"]
        if facts:
            for f in facts:
                parts.append(f"**Q: What is the {f.claim.lower()}?**")
                answer = f"A: {f.value}"
                if f.condition:
                    answer += f" ({f.condition})"
                parts.append(answer)
    else:
        for c in concepts:
            if c.content_block:
                parts.append(c.content_block)
    return "\n\n".join(parts) if parts else f"*{section_name.replace('_', ' ').title()} content to be added.*"


def _collect_evidence(subgraph, graph: KnowledgeGraph) -> list[str]:
    """Collect evidence IDs from facts in the subgraph.

    The subgraph follows forward edges from concepts, but facts point
    *to* concepts (via fact.concept), so they aren't in the forward
    subgraph. This also finds facts that reference concepts in the
    subgraph via reverse edges.
    """
    evidence_ids: set[str] = set()

    # Collect from facts already in the subgraph
    for entity in subgraph:
        if isinstance(entity, Fact):
            evidence_ids.update(entity.evidence)

    # Also find facts that point to concepts in the subgraph
    concept_ids = {e.id for e in subgraph if isinstance(e, Concept)}
    for entity in graph.entities.values():
        if isinstance(entity, Fact) and entity.concept in concept_ids:
            evidence_ids.update(entity.evidence)

    return list(evidence_ids)


# ---------------------------------------------------------------------------
# LLM generation
# ---------------------------------------------------------------------------


def _build_knowledge_context(
    graph: KnowledgeGraph,
    concepts: list[Concept],
    subgraph: list,
    audience: Audience,
    template: dict,
) -> str:
    """Assemble the knowledge graph context into a structured prompt section."""
    parts: list[str] = []

    # Concepts
    parts.append("## Concepts")
    for c in concepts:
        parts.append(f"### {c.name} ({c.id})")
        parts.append(f"Description: {c.description}")
        if c.prerequisites:
            parts.append(f"Prerequisites: {', '.join(c.prerequisites)}")
        if c.content_block:
            parts.append(f"Content:\n{c.content_block}")
        parts.append("")

    # Facts (with IDs for citation)
    facts = [e for e in subgraph if isinstance(e, Fact) and e.status == "active"]
    if facts:
        parts.append("## Facts")
        parts.append("Each fact has an ID. When you use a fact in the output, cite it inline as {{fact:ID}}.")
        parts.append("")
        for f in facts:
            line = f"- **{f.id}**: {f.claim}: {f.value}"
            if f.condition:
                line += f" (condition: {f.condition})"
            parts.append(line)
        parts.append("")

    # Tasks
    tasks = [e for e in subgraph if isinstance(e, Task)]
    if tasks:
        parts.append("## Tasks")
        for t in tasks:
            parts.append(f"### {t.name}")
            parts.append(f"Description: {t.description}")
            if t.steps:
                for i, step in enumerate(t.steps, 1):
                    parts.append(f"  {i}. {step}")
            if t.content_block:
                parts.append(f"Content:\n{t.content_block}")
            parts.append("")

    # Evidence sources
    evidence_ids = _collect_evidence(subgraph, graph)
    evidence_entities = [graph.get(eid) for eid in evidence_ids]
    evidence_entities = [e for e in evidence_entities if isinstance(e, Evidence)]
    if evidence_entities:
        parts.append("## Evidence Sources")
        for ev in evidence_entities:
            line = f"- {ev.name}"
            if ev.url:
                line += f" ({ev.url})"
            if ev.description:
                line += f": {ev.description}"
            parts.append(line)
        parts.append("")

    # Audience
    parts.append("## Target Audience")
    parts.append(f"Name: {audience.name}")
    parts.append(f"Description: {audience.description}")
    if audience.assumed_knowledge:
        parts.append(f"Assumed knowledge: {', '.join(audience.assumed_knowledge)}")
    if audience.tone:
        parts.append(f"Tone: {audience.tone}")
    if audience.preferred_formats:
        parts.append(f"Preferred formats: {', '.join(audience.preferred_formats)}")

    return "\n".join(parts)


def generate_asset_llm(
    graph: KnowledgeGraph,
    template_name: str,
    concept_ids: list[str],
    audience_id: str,
) -> dict[str, Any]:
    """Generate a training asset using Claude via the Anthropic API.

    Authenticates via pi's OAuth token or ANTHROPIC_API_KEY env var.
    """
    from kanon.auth import get_credential

    credential = get_credential()
    if credential is None:
        raise RuntimeError(
            "No Anthropic credential found. "
            "Set ANTHROPIC_API_KEY or authenticate via pi (oauth)."
        )

    template = load_template(template_name)
    concepts, audience = _validate_inputs(graph, concept_ids, audience_id)

    # Resolve subgraph
    subgraph = graph.subgraph(concept_ids)

    # Build knowledge context
    knowledge_context = _build_knowledge_context(
        graph, concepts, subgraph, audience, template
    )

    title_concepts = ", ".join(c.name for c in concepts)
    section_list = ", ".join(template["sections"])

    system_prompt = (
        "You are a training content generator for the Kanon knowledge system. "
        "You produce well-structured training materials using ONLY the knowledge "
        "context provided below. This is a strict constraint:\n\n"
        "- Do NOT add code examples, URLs, API snippets, or technical details "
        "that are not explicitly present in the knowledge context.\n"
        "- Do NOT draw on your own knowledge of APIs, products, or tools.\n"
        "- If a section cannot be filled with the provided context, write: "
        "\"[Insufficient knowledge graph coverage — add more entities to populate this section.]\"\n"
        "- Your job is to organize, clarify, and adapt the provided content for "
        "the target audience — not to supplement it.\n\n"
        "CITATION REQUIREMENT:\n"
        "- The knowledge context includes a Facts section with IDs like "
        "tool_use_max_tools, pasta_water_ratio, etc.\n"
        "- When you use information from a fact, cite it inline as {{fact:FACT_ID}}.\n"
        "- ONLY use IDs from the Facts section. Do NOT cite concept IDs or task IDs.\n"
        "- Place the citation immediately after the claim.\n"
        "- Example: 'The maximum number of tools per request is 128 {{fact:tool_use_max_tools}}.'\n"
        "- Procedural steps and descriptions from concepts/tasks do NOT get citations.\n"
        "- Only specific, verifiable claims from the Facts section get citations.\n"
        "- If no facts are relevant to a section, that's fine — not every sentence needs a citation.\n\n"
        "Write in Markdown format. Adapt tone and structure to the target audience."
    )

    user_prompt = (
        f"Generate a **{template_name.replace('_', ' ')}** for: **{title_concepts}**\n\n"
        f"Target audience: **{audience.name}** — {audience.description}\n\n"
        f"The document should have these sections: {section_list}\n\n"
        f"---\n\n"
        f"# Knowledge Context\n\n"
        f"{knowledge_context}"
    )

    # Call Anthropic API
    headers = {
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
        **credential.auth_headers(),
    }

    body = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 4096,
        "system": credential.wrap_system_prompt(system_prompt),
        "messages": [{"role": "user", "content": user_prompt}],
    }

    response = httpx.post(
        ANTHROPIC_API_URL,
        headers=headers,
        json=body,
        timeout=120,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Anthropic API error ({response.status_code}): {response.text}"
        )

    result = response.json()
    content = result["content"][0]["text"]

    now = datetime.now(UTC)

    return {
        "name": f"{title_concepts} {template_name.replace('_', ' ').title()}",
        "asset_type": "guide",
        "delivery_format": template_name,
        "lifecycle_state": "draft",
        "teaches": concept_ids,
        "targets": [audience_id],
        "evidence_links": _collect_evidence(subgraph, graph),
        "generation_method": "llm",
        "generated_at": now.isoformat(),
        "last_updated": now.isoformat(),
        "content": content,
        "content_blocks": {s: "" for s in template["sections"]},
        "model": ANTHROPIC_MODEL,
        "input_tokens": result.get("usage", {}).get("input_tokens"),
        "output_tokens": result.get("usage", {}).get("output_tokens"),
    }
