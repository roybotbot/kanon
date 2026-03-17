# Kanon PoC Validation

This document records the validation of Kanon's proof of concept. Each stage has automated tests (run with `pytest tests/test_validation.py -v`) and narrative findings.

For the full validation plan and criteria, see [docs/raw/poc-validation-plan.md](docs/raw/poc-validation-plan.md).

---

## Stage 1: Can we generate training materials from the knowledge graph?

**Hypothesis:** Given structured knowledge entities, the system produces usable training documents traceable to their source entities.

### Tests

| # | Test | Status | Evidence |
|---|------|--------|----------|
| 1.1 | Dry-run populates all sections without fallback repetition | ❌ | `test_validation.py::test_dry_run_no_repeated_sections` |
| 1.1b | All sections have content (no empty sections) | ✅ | `test_validation.py::test_dry_run_all_sections_populated` |
| 1.2 | LLM output contains only knowledge graph content | ⬜ | Manual review (requires API call) |
| 1.3 | Same asset generates differently for two audiences | ✅ | `test_validation.py::test_audience_adaptation_dry_run` |
| 1.4 | Multi-concept asset reflects relationships | ✅ | `test_validation.py::test_multi_concept_generation` |
| 1.5 | Food domain generates with no code changes | ✅ | `test_validation.py::test_food_domain_generation` |
| 1.5b | Food domain multi-concept | ✅ | `test_validation.py::test_food_domain_multi_concept` |
| 1.5c | Food domain prerequisites resolved | ✅ | `test_validation.py::test_food_domain_prerequisites_resolved` |

### Findings

**1.1 FAIL — Dry-run section repetition bug.** `_build_section` has no specific handler for `verification` or `troubleshooting` sections. Both fall through to the generic `else` clause which dumps the concept's `content_block`. Result: identical content in both sections. Needs section-specific handlers or a different fallback strategy.

**1.3 PASS (partial).** Audience adaptation at the dry-run level only changes the `targets` metadata — the actual content is identical for both audiences. The dry-run assembler doesn't use audience information to adapt tone or structure. LLM generation does handle this (confirmed by manual testing), but the dry-run path doesn't.

**1.5 PASS.** The food/recipe domain generates successfully with zero code changes. Entity models, graph loading, template rendering, and relationship traversal all work across domains. This validates that the ontology model is domain-agnostic.

---

## Stage 2: Can we review generated materials for accuracy?

**Hypothesis:** The system can trace every claim in a generated asset back to its source entity and flag claims that lack backing.

### Tests

| # | Test | Status | Evidence |
|---|------|--------|----------|
| 2.1 | Asset lists all contributing source entities | ❌ | `test_validation.py::test_asset_traceability` |
| 2.1b | Food domain traceability | ❌ | `test_validation.py::test_asset_traceability_food` |
| 2.2 | Confidence scores change when entities change | ✅ | `test_validation.py::test_confidence_reflects_changes` |
| 2.3 | Stale facts produce lower confidence than fresh facts | ✅ | `test_validation.py::test_stale_facts_lower_confidence` |
| 2.3b | Assets below threshold flagged for review | ✅ | `test_validation.py::test_needs_review_threshold` |
| 2.4 | Coverage gaps are surfaced, not silently ignored | ✅ | `test_validation.py::test_coverage_gaps_surfaced` |

### Findings

**2.1 FAIL — Evidence traceability broken.** `_collect_evidence` walks the forward-edge subgraph from concepts, but facts point *to* concepts (via `fact.concept`), not the other way around. The subgraph traversal only follows forward edges from the starting concept, so it never reaches facts, and therefore never finds their evidence links. The generated asset returns `evidence_links: []`. This is a real bug in the graph traversal — facts should be reachable from concepts via reverse edges.

**2.2, 2.3 PASS.** The confidence scoring engine correctly produces lower scores when evidence coverage is partial or evidence is stale. The math works.

**2.4 PASS.** Sections without matching graph content produce placeholder text rather than being silently empty.

---

## Stage 3: Can we detect drift and trace impact?

**Hypothesis:** When source material changes, the system identifies what's affected and what needs to be updated.

### Tests

| # | Test | Status | Evidence |
|---|------|--------|----------|
| 3.1 | Evidence change identifies all backed facts | ✅ | `test_validation.py::test_drift_finds_stale_facts` |
| 3.1b | Food domain drift detection | ✅ | `test_validation.py::test_drift_finds_stale_facts_food` |
| 3.2 | Stale facts propagate to affected assets | ✅ | `test_validation.py::test_drift_propagates_to_assets` |
| 3.2b | Food domain drift propagation to assets | ✅ | `test_validation.py::test_drift_propagates_to_assets_food` |
| 3.3 | Impact traces through concept dependencies | ✅ | `test_validation.py::test_drift_cascading_impact` |
| 3.4 | Confidence drops on drift, recovers on update | ✅ | `test_validation.py::test_confidence_drift_lifecycle` |
| 3.5 | Regenerated asset incorporates updated facts | ✅ | `test_validation.py::test_regeneration_after_drift` |

### Findings

**All Stage 3 tests PASS.** Drift detection works end-to-end across both domains:
- Evidence changes correctly identify all facts backed by that evidence
- Impact propagates from facts through concepts to affected assets
- Confidence scores drop when evidence becomes stale, recover when refreshed
- Regenerated assets pick up updated content from modified entities

The full lifecycle works: evidence changes → stale facts found → assets flagged → content updated → asset regenerated with new content.

---

## Second Domain: Food/Recipe

Tests 1.5, and stages 2-3 repeated against food domain entities confirm the system generalizes beyond the Claude/AI training domain.

---

## How to run

```bash
# All validation tests
pytest tests/test_validation.py -v

# Just one stage
pytest tests/test_validation.py -v -k "stage1"
pytest tests/test_validation.py -v -k "stage2"
pytest tests/test_validation.py -v -k "stage3"
```

---

## Summary

| Stage | Pass | Fail | Not Run | Notes |
|-------|------|------|---------|-------|
| Stage 1: Generation | 6 | 1 | 1 | Dry-run section repetition bug; LLM test requires API |
| Stage 2: Review | 4 | 2 | 0 | Evidence traceability broken — subgraph traversal doesn't reach facts |
| Stage 3: Drift | 7 | 0 | 0 | All pass across both domains |

### Bugs found

1. **`_build_section` fallback** — verification and troubleshooting sections repeat the concept content_block (Stage 1.1)
2. **`_collect_evidence` traversal** — subgraph follows forward edges only, never reaches facts that point back to concepts (Stage 2.1)

---

## Legend

- ⬜ Not yet run
- ✅ Pass
- ❌ Fail — see findings
