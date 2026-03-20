# Kanon

> Exploring an ontology-driven knowledge system for training content

Kanon models training knowledge as structured entities connected through an ontology rather than managing it as standalone documents. Concepts, facts, evidence, tasks, and audiences are first-class objects in a knowledge graph. Training assets like facilitator guides, demos, and exercises are generated from these objects, so when the underlying knowledge changes, the system knows what's affected and what needs updating.

The goal is to explore whether this approach actually keeps training content accurate in fast-changing technical environments. Kanon combines ontology-driven content modeling, confidence-based governance, and AI-assisted generation to make knowledge maintainable rather than disposable.

## Quick Start

```bash
git clone https://github.com/roybotbot/kanon.git
cd kanon
pip install -e ".[dev]"

kanon graph                        # browse the knowledge graph + interactive visualization
kanon graph --concept tool_use     # inspect a concept and its connections
kanon graph --gaps                 # find concepts and tasks without training assets
kanon status                       # see confidence scores for all assets
kanon generate --type setup_guide --concepts tool_use --audience enterprise_developer --dry-run
                                   # generate a training asset from knowledge objects
kanon generate --type setup_guide --concepts tool_use --audience enterprise_developer
                                   # generate with Claude + inline fact citations
kanon drift --evidence anthropic_tool_use_docs --change "API format changed"
                                   # report a source change and see what's affected
kanon review                       # review assets against hard failure conditions
kanon review --approve <id>        # approve an asset
kanon crawl                        # fetch evidence URLs, detect changes, auto-trigger drift
kanon ingest --file doc.txt --source "Doc Name" --save
                                   # decompose unstructured text into ontology entities
```

The `graph` command generates an interactive HTML visualization at `docs/graph.html` showing all entities and their relationships. The `generate` and `drift` commands produce scoped visualizations highlighting the entities involved. LLM-generated assets include `{{fact:ID}}` inline citations with markdown and HTML validation reports.

## What It Does

**Generates training assets from structured knowledge.** You specify which concepts to cover and who the audience is. Kanon walks the ontology, gathers the relevant concepts, capabilities, tasks, facts, and evidence, then assembles a training asset using a template. In dry-run mode this uses pre-written content blocks on each entity. In LLM mode, it sends the structured context to Claude for generation — constrained to only use knowledge graph content, with `{{fact:ID}}` inline citations on every factual claim.

**Detects drift when source material changes.** Evidence sources can be crawled automatically (`kanon crawl`) or changes reported manually. Kanon traces the impact through the knowledge graph: which facts are backed by that evidence, which concepts those facts belong to, which assets teach those concepts. It reports exactly what's stale, not just "something changed."

**Reviews with hard failure conditions.** Beyond confidence scores, `kanon review` applies binary pass/fail rules: any cited fact that's superseded or retracted → fail. Any evidence verified after the asset was last updated → fail. The reviewer sees exactly which claims are stale and why.

**Ingests unstructured content.** `kanon ingest` feeds a document to Claude and extracts structured ontology entities (concepts, facts, tasks, evidence) that validate against the Pydantic models and load into the graph. Existing entities are never overwritten.

**Scores confidence.** Every asset has a confidence score calculated from four dimensions: evidence coverage (do the concepts have sources?), freshness (is the evidence current?), structural completeness (are ontology relationships filled in?), and transformation risk (how much AI was involved?). Assets below the threshold are flagged for review.

**Visualizes the knowledge graph.** Every command generates an interactive HTML visualization. The full graph shows all entities in a hierarchical layout with color-coded types, different shapes, trail highlighting, and a detail panel. Generate and drift commands produce scoped views showing only the entities involved in that operation.

## The Ontology

Kanon's knowledge graph is built from nine entity types:

| Entity | Purpose |
|--------|---------|
| **Concept** | An idea a learner must understand (e.g., "Context Window") |
| **Capability** | Something the system can do (e.g., "Structured Data Extraction") |
| **Task** | An action a user performs (e.g., "Configure Tool Definitions") |
| **Audience** | Who the training targets (e.g., "Enterprise Developer") |
| **Fact** | A versioned, verifiable claim attached to a concept (e.g., "Max tokens = 200,000 on Pro plan") |
| **Evidence** | A source backing factual claims (e.g., Anthropic documentation page) |
| **LearningObjective** | A measurable outcome a learner should achieve |
| **Asset** | A generated training artifact (guide, demo, exercise) |
| **Constraint** | A rule training materials must respect |

Facts are the atomic unit of truth. They have a lifecycle (active, superseded, retracted), can be backed by multiple evidence sources, and carry timestamps for when they became true and when they were recorded. When a fact is superseded, the old version is preserved with a link to its replacement.

## Proof of Concept

The current implementation validates the core idea with a minimal stack:

| Layer | Tool |
|-------|------|
| Ontology | Pydantic models with typed relationship fields |
| Storage | YAML files (human-readable, git-versioned) |
| Graph | In-memory Python with forward/reverse indexes |
| Confidence | Weighted average across four dimensions |
| Generation | Dry-run (content blocks) + Claude API (OAuth or API key) |
| Visualization | Self-contained HTML with hierarchical layout |
| Audit | Structured JSON log per operation |
| Interface | CLI |

The knowledge graph ships pre-populated with Claude/AI training content: 7 concepts, 4 capabilities, 4 tasks, 8 facts, 4 evidence sources, and 1 pre-built asset.

## Validation

Kanon has been validated through 6 experiments, each testing a specific hypothesis. See [VALIDATION.md](VALIDATION.md) for PoC results.

| Experiment | What it proved | Tests |
|-----------|---------------|-------|
| 00 PoC validation | Ontology model works, generalizes across domains | 20 |
| 01 Claim traceability | `{{fact:ID}}` citations make every claim traceable | 19 |
| 02 Ingestion | LLM decomposes docs into valid ontology entities | 10 |
| 03 Governance workflow | Hard failure conditions catch what scores miss | 11 |
| 04 Evidence crawling | URL monitoring detects changes, auto-triggers drift | 21 |
| 05 End-to-end loop | Full maintenance cycle works without integration code | 2 |

A second domain (food/recipe ontology) validates that the system generalizes beyond the Claude/AI training content.

```bash
pytest tests/ -q                      # all 197 tests
pytest tests/test_validation.py -v    # PoC validation suite
pytest tests/test_e2e_maintenance.py -v  # end-to-end maintenance loop
```

## System Design (Full Version)

The full Kanon system extends the PoC with:

| Layer | Tool | Purpose |
|-------|------|---------|
| Ontology | Owlready2 / OWL | Formal reasoning and validation |
| Database | PostgreSQL + pgvector | Structured storage + vector embeddings |
| CMS | Directus | Editing, review workflows, permissions, version history |
| RAG | pgvector | Ontology-scoped retrieval against evidence |
| LLM | Claude API | Generation with inline fact citations and post-generation validation |
| Ingestion | Python + Claude API | Decompose docs, Slack, wikis into ontology objects |
| Evidence Crawler | Python | Monitor source URLs, trigger drift automatically |
| Governance | Directus + Python | Review routing, approval workflows, conflict resolution |
| Versioning | PostgreSQL | Immutable asset snapshots on publish, version pinning per cohort |
| API | FastAPI | Expose the system to frontends and integrations |
| Frontend | Next.js | Browse graph, inspect audit trail, manage review queue |
| Rendering | Pandoc | Export to PDF, slides, worksheets |
| Audit | PostgreSQL | Queryable trail for every pipeline decision — inputs, outputs, reasoning |
| Notifications | Webhooks / Slack / Email | Confidence-drop alerts, review assignments, drift reports |
| Auth / Roles | Directus | Multi-user with content author, reviewer, and admin roles |
| Automation | Python | Crawl, detect, score, notify pipelines |

## Project Structure

```
kanon/
├── kanon/
│   ├── models/entities.py    # Pydantic entity definitions
│   ├── graph.py              # KnowledgeGraph (load, index, traverse)
│   ├── generate.py           # Asset generation (dry-run + LLM)
│   ├── citations.py          # {{fact:ID}} extraction, validation, stripping
│   ├── citation_report.py    # Markdown + HTML citation reports
│   ├── review.py             # Hard failure conditions, approve/reject
│   ├── crawl.py              # Evidence URL fetching, baseline diffing
│   ├── ingest.py             # LLM decomposition of text into entities
│   ├── confidence.py         # Scoring engine
│   ├── drift.py              # Drift detection + impact tracing
│   ├── auth.py               # Anthropic API auth (OAuth + API key)
│   ├── visualize.py          # HTML graph visualization
│   ├── templates/            # Asset templates (setup_guide, facilitator_guide)
│   ├── audit.py              # Structured logging
│   └── cli.py                # CLI entry point
├── data/                     # YAML knowledge graph (concepts, facts, evidence, etc.)
├── docs/                     # Generated HTML visualizations and design docs
├── tests/                    # 197 tests across 6 experiments
├── VALIDATION.md             # PoC validation results and findings
├── AGENTS.md                 # Agent/session context
└── README.md
```

## Motivation

Knowledge systems and training have been recurring parts of my career. Over time I built personal runbooks and methods I rely on regularly, but they were not part of an explicit coherent system. Kanon is my attempt to unify those ideas into one structured knowledge system. With the emergence of agentic AI and the technical skills I've developed more recently, I now have the tools to build the kind of system I previously only approximated informally.
