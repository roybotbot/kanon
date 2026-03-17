# Kanon
> Ontology-driven knowledge system for training content

Kanon is a governed knowledge system for training content. It treats training material not as standalone documents but as structured knowledge objects connected through an ontology of concepts, capabilities, tasks, audiences, and learning objectives. Training assets such as facilitator guides, demos, and exercises are built from this canonical knowledge rather than duplicating it, allowing the system to maintain a single source of truth as technology and best practices evolve.

The goal of Kanon is to explore how training knowledge can remain accurate and maintainable in fast-changing technical environments. The system combines ontology-driven content modeling, AI-assisted maintenance, and confidence-based governance so that knowledge can adapt to new contexts while still remaining trustworthy.

Kanon is composed of four main parts: an ontology layer that defines the structure and relationships of knowledge, a content layer that stores canonical knowledge objects and modular training assets, a governance layer that controls how knowledge is updated and reviewed, and a signal and confidence layer that tracks usage, evidence freshness, and content reliability.

## System Design

The planned full Canon system is composed of:

| Layer | Tool | Purpose |
|-------|------|---------|
| Ontology | Owlready2 / OWL | Formal knowledge modeling with reasoning and validation |
| Database | PostgreSQL + pgvector | Structured storage for entities, relationships, and vector embeddings |
| CMS | Directus | Editing interface, review workflows, permissions, version history |
| RAG | pgvector | Ontology-scoped retrieval against indexed evidence sources |
| LLM | Claude API | Asset generation, audience adaptation, drift analysis |
| Automation | Python | Orchestration of crawl → drift detect → score → notify pipelines |
| Ingestion | Python + Claude API | Decompose unstructured content (docs, Slack, wikis) into ontology objects |
| Evidence Crawler | Python | Monitor source URLs for changes, trigger drift detection |
| API | FastAPI | Expose the system to frontends and integrations |
| Frontend | Next.js | Browse the knowledge graph, manage review queues |
| Rendering | Pandoc | Export assets to PDF, slides, HTML, worksheets |
| Observability | Python / PostgreSQL | Audit trail for every pipeline decision — traceable inputs, outputs, reasoning |

The ontology defines structured relationships between concepts, capabilities, tasks, audiences, and evidence. Training assets are generated from these knowledge objects rather than written independently. When source material changes, the system traces the impact through the knowledge graph, recalculates confidence scores, and flags affected assets for review.

The full system includes a web interface for inspecting the knowledge graph and the operations performed on it. Users can browse entities and their relationships as an interactive graph, view the audit trail for any asset or fact, see what inputs were used and what decisions were made at each step, and monitor system health through confidence scores and review queues. The CLI remains available for all operations.

## Proof of Concept

The current implementation is a minimal but complete version of the system, focused on validating the core idea: does structuring training knowledge as ontology-connected entities actually make it easier to keep content accurate and generate useful training materials?

| Layer | Tool | Notes |
|-------|------|-------|
| Ontology | Pydantic | Entity models with typed relationship fields |
| Storage | YAML files | Human-readable, no database required |
| Confidence | Python | Scoring engine with evidence, freshness, structural, and transformation dimensions |
| Drift detection | Python | Graph traversal to trace impact of evidence changes |
| Asset generation | Dry-run + Claude API | Dry-run assembles from pre-written content blocks; LLM mode generates via API |
| Interface | CLI | Browse the graph, generate assets, report drift, review status |

No database, no CMS, no ingestion, no frontend. The knowledge graph ships pre-populated with Claude/AI training domain content. Clone the repo, run the CLI, and see the system work.

```bash
kanon graph              # list all entities, generate interactive visualization
kanon graph --concept tool_use   # inspect a specific entity and its connections
kanon status             # confidence scores and lifecycle state for all assets
kanon generate --type setup_guide --concepts tool_use --audience enterprise_developer --dry-run
kanon generate --type setup_guide --concepts tool_use --audience enterprise_developer
kanon drift --evidence anthropic_tool_use_docs --change "API format changed"
```

The `graph` command generates an interactive HTML visualization at `docs/graph.html` showing all entities and their relationships. The `generate` and `drift` commands produce scoped visualizations highlighting the entities involved.

## Validation

The PoC is validated against three stages with automated tests and documented findings. See [VALIDATION.md](VALIDATION.md) for full results.

| Stage | Tests | Status |
|-------|-------|--------|
| Generation — produce training materials from the knowledge graph | 7 pass | ✅ |
| Review — trace claims to source entities, score confidence | 6 pass | ✅ |
| Drift — detect evidence changes, trace impact, regenerate | 7 pass | ✅ |

A second domain (food/recipe ontology) validates that the system generalizes beyond the Claude/AI training content. Run the tests:

```bash
pytest tests/test_validation.py -v
```

## Motivation

Knowledge systems and training have been recurring parts of my career. Over time I built personal runbooks and methods I rely on regularly, but they were not part of a explicit coherent system. Kanon is my attempt to unify those ideas into one structured knowledge system. With the emergence of agentic AI and the technical skills I've developed more recently, I now have the tools to build the kind of system I previously only approximated informally. I hope others find it useful as well.