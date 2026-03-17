# Kanon PoC Validation Plan

## What we're validating

The PoC tests one core hypothesis: **structuring training knowledge as ontology-connected entities makes it easier to keep content accurate and generate useful training materials.**

This breaks down into three stages, each building on the previous one. Each stage has specific pass/fail criteria. Scenarios and data can be artificial, but the mechanisms that detect, score, and generate must be real.

---

## Stage 1: Can we generate training materials from the knowledge graph?

**Question:** Given structured knowledge entities, can the system produce usable training documents that are traceable back to their source entities?

### Tests

1. **Dry-run generation** — assembles content blocks from the graph into a template. Output should contain only content present in the graph entities. Every section should be populated (no repeated fallback text).

2. **LLM generation** — Claude organizes and adapts graph content for a target audience. Output must not contain information absent from the knowledge context. Missing coverage should be flagged explicitly, not filled with LLM knowledge.

3. **Audience adaptation** — generate the same asset for two different audiences. Output should differ in tone, assumed knowledge, and structure while drawing from the same source entities.

4. **Multi-concept assets** — generate an asset covering multiple related concepts. The output should reflect the relationships between concepts, not just concatenate them.

5. **Second domain** — repeat tests 1-4 using a food/recipe ontology (from ~/Projects/learnings/crash-courses/ontology/). If the system only works for the Claude/AI training domain, the ontology model isn't general enough.

### Pass criteria

- [ ] Dry-run output has no repeated/fallback sections (fix the current bug)
- [ ] LLM output contains zero information not traceable to the knowledge graph
- [ ] Two audience variants of the same asset differ meaningfully in presentation
- [ ] Multi-concept asset reflects entity relationships
- [ ] Food domain generates successfully with no code changes (only new data)

---

## Stage 2: Can we review generated materials for accuracy?

**Question:** Given a generated asset, can the system trace every claim back to its source entity and evidence, and flag claims that lack backing?

### Tests

1. **Traceability** — for a generated asset, identify which facts, concepts, and evidence sources contributed to each section. The system should be able to answer: "where did this claim come from?"

2. **Confidence scoring** — an asset built from fresh, well-evidenced entities should score higher than one built from stale or poorly-evidenced entities. Scores should reflect actual content quality, not just exist as numbers.

3. **Coverage gaps** — the system should identify when an asset's template requires content the graph doesn't have. This is the "[Insufficient knowledge graph coverage]" signal.

4. **Staleness detection** — mark a fact as superseded. The asset's confidence score should drop. The system should flag the asset for review.

### Pass criteria

- [ ] Given an asset, the system can list every source entity that contributed
- [ ] Confidence scores change meaningfully when underlying entities change
- [ ] Assets built from stale facts score lower than assets built from fresh facts
- [ ] Coverage gaps are surfaced, not silently ignored

---

## Stage 3: Can we detect drift and trace impact?

**Question:** When source material changes, can the system identify what's affected and what needs to be updated?

### Tests

1. **Evidence change → stale facts** — report a change to an evidence source. The system should identify all facts backed by that evidence and mark them for review.

2. **Stale facts → affected assets** — from the stale facts, trace forward to find all assets that teach concepts containing those facts.

3. **Cascading impact** — change evidence that affects a foundational concept. The system should trace impact through prerequisites and dependent concepts, not just direct references.

4. **Confidence recalculation** — after drift is detected, confidence scores for affected assets should decrease. After review/update, they should recover.

5. **Before/after comparison** — regenerate an affected asset after updating the stale facts. Compare the new version against the old to verify the content actually changed where expected.

### Pass criteria

- [ ] Evidence change correctly identifies all backed facts
- [ ] Stale facts correctly propagate to affected assets
- [ ] Impact traces through concept dependencies, not just direct links
- [ ] Confidence scores reflect drift (drop on detection, recover on update)
- [ ] Regenerated asset incorporates updated facts

---

## Second domain: Food/Recipe ontology

To validate that the system generalizes beyond the Claude/AI training domain, we'll create a parallel knowledge graph using a food/recipe domain based on the FoodKB ontology example.

### Entities to create

| Type | Examples |
|------|----------|
| Concepts | Knife Skills, Sauce Making, Pasta Cooking |
| Capabilities | Can prepare mise en place, Can make a roux |
| Tasks | Dice an onion, Make tomato sauce, Cook pasta al dente |
| Audiences | Home cook, Professional chef |
| Facts | "Pasta should be cooked in 1 gallon of water per pound" (with evidence) |
| Evidence | Serious Eats article, America's Test Kitchen guide |
| Assets | Pasta Cooking Setup Guide, Knife Skills Facilitator Guide |

### What this validates

- Entity models are domain-agnostic (no Claude-specific fields)
- Relationships (prerequisites, supports, teaches) work across domains
- Templates produce coherent output for non-technical content
- Drift detection works when a cooking technique or food safety guideline changes

---

## What's out of scope for the PoC

- Ingestion (manually creating entities is fine)
- Web frontend
- Database storage
- Multi-user workflows
- Real evidence crawling (we simulate evidence changes)
- Production-quality generated content

---

## Current status

| Stage | Status | Notes |
|-------|--------|-------|
| Stage 1: Generation | Partially done | LLM generation works, dry-run has bugs, audience adaptation untested, second domain not started |
| Stage 2: Review | Not started | Confidence scoring exists as code but hasn't been validated against real scenarios |
| Stage 3: Drift | Partially done | Drift detection works mechanically, but no end-to-end lifecycle test |
| Second domain | Not started | Food/recipe entities need to be created |

---

## Order of work

1. Fix dry-run generation bugs (verification/troubleshooting fallback)
2. Create food/recipe knowledge graph entities
3. Run Stage 1 tests across both domains
4. Build traceability tooling for Stage 2
5. Run full drift lifecycle for Stage 3
6. Document results — what worked, what didn't, what the PoC proves
