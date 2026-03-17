# Design Decision: LLM Generation Constraints

## Decision

During the PoC stage, LLM-generated assets must use **only** the knowledge graph context provided in the prompt. Claude must not supplement output with its own training knowledge.

## Rationale

The point of the PoC is to validate whether structuring training knowledge as ontology-connected entities makes content easier to maintain and generate. If Claude silently fills gaps with its own knowledge, we can't tell whether the knowledge graph is sufficient or where it has holes.

Strict generation constraints give us:
- **Visibility into graph coverage** — missing sections expose gaps in the ontology
- **Traceability** — every claim in the output maps back to a knowledge graph entity
- **Honest confidence scores** — transformation confidence means something when the LLM can only transform, not invent

## What this means in practice

- The system prompt explicitly forbids adding code examples, URLs, or technical details not in the knowledge context
- If a template section can't be filled from the graph, the output says so: `[Insufficient knowledge graph coverage]`
- The LLM's job is to organize, clarify, and adapt — not to supplement

## When to revisit

Once the PoC validates the core model, a future "enrichment mode" could allow Claude to draw on external knowledge with clear attribution (e.g., `[from LLM knowledge, not verified]`). That belongs in the full system with guardrails, not the PoC.
