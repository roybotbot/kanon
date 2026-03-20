# Kanon

Ontology-driven knowledge system for fact-traceable maintenance of training content.

## Project

- **Repo:** /Users/roy/Projects/kanon
- **Language:** Python 3.11+
- **Venv:** .venv (activate with `.venv/bin/python`)
- **Entry point:** `kanon` CLI (installed via `pip install -e .`)
- **Planning docs (source of truth):** ~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Brain II/Projects/Kanon/

## Commands

```bash
.venv/bin/python -m pytest tests/ -q          # all tests (197)
.venv/bin/python -m pytest tests/test_validation.py -v  # validation suite (20)
.venv/bin/kanon graph                          # browse knowledge graph
.venv/bin/kanon generate --type setup_guide --concepts tool_use --audience enterprise_developer --dry-run
.venv/bin/kanon generate --type setup_guide --concepts tool_use --audience enterprise_developer
.venv/bin/kanon drift --evidence anthropic_tool_use_docs --change "API format changed"
.venv/bin/kanon review                         # hard failure conditions on all assets
.venv/bin/kanon crawl                          # fetch evidence URLs, detect changes
.venv/bin/kanon ingest --file doc.txt --source "Name" --save  # decompose text into entities
```

## Architecture

- `kanon/models/entities.py` — Pydantic entity definitions (Concept, Fact, Evidence, Asset, etc.)
- `kanon/graph.py` — KnowledgeGraph with forward/reverse indexes, BFS traversal
- `kanon/generate.py` — dry-run + LLM asset generation from knowledge graph context
- `kanon/citations.py` — {{fact:ID}} citation extraction, validation, stripping
- `kanon/citation_report.py` — markdown + HTML citation reports
- `kanon/review.py` — hard failure conditions, approve/reject lifecycle actions
- `kanon/crawl.py` — evidence URL fetching, HTML stripping, baseline diffing
- `kanon/ingest.py` — LLM decomposition of unstructured text into ontology entities
- `kanon/confidence.py` — scoring engine (evidence, freshness, structural, transformation)
- `kanon/drift.py` — detect evidence changes, trace impact to facts and assets
- `kanon/auth.py` — Anthropic API auth (OAuth from ~/.pi/agent/auth.json or ANTHROPIC_API_KEY)
- `kanon/cli.py` — Click CLI
- `kanon/visualize.py` — HTML graph visualization
- `data/` — YAML knowledge graph (concepts, facts, evidence, tasks, audiences, assets)
- `kanon/templates/` — asset templates (setup_guide, facilitator_guide)

## Conventions

- **Tests first.** Run all tests before and after changes. Never commit with failing tests.
- **Commit as you go.** Each logical change gets its own commit with a descriptive message.
- **Git signing may fail.** Use `git -c commit.gpgsign=false commit` if 1Password agent errors.
- **LLM generation constraint.** Generated assets use ONLY knowledge graph content. No LLM supplementation. See docs/raw/llm-generation-constraints.md.
- **OAuth for Claude API.** OAuth tokens require Claude Code identity prefix in system prompt for Sonnet/Opus models. See kanon/auth.py.

## Current state

- All 6 experiments complete, merged to main
- 197 tests (192 unit + 5 LLM), all passing
- See VALIDATION.md for PoC results, EXPERIMENT_FRAMEWORK.md in Obsidian for full experiment findings

## Domains

Two knowledge graph domains exist:
1. **Claude/AI training** — in `data/` (7 concepts, 8 facts, 4 evidence sources)
2. **Food/recipe** — in test fixtures only (`tests/test_validation.py::FOOD_ENTITIES`)
