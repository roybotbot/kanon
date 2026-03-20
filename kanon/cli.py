"""Kanon CLI — graph, status, generate, and drift commands."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

import click

from kanon.audit import AuditLogger
from kanon.drift import detect_drift
from kanon.generate import generate_asset_dry_run
from kanon.graph import KnowledgeGraph
from kanon.models.entities import Asset, Concept, Task

DATA_DIR = Path(__file__).parent.parent / "data"
LOG_PATH = Path(__file__).parent.parent / "logs" / "audit.jsonl"


def _get_graph() -> KnowledgeGraph:
    return KnowledgeGraph(data_dir=DATA_DIR)


def _get_logger() -> AuditLogger:
    return AuditLogger(log_path=LOG_PATH)


@click.group()
def cli() -> None:
    """Kanon — ontology-driven knowledge system for training content.

    Kanon models training knowledge as structured entities (concepts, facts,
    evidence, tasks, assets) connected through an ontology. It generates
    training materials from these knowledge objects and detects when source
    material changes make content stale.

    \b
    Quick start:
      kanon graph                     Browse all entities and open interactive visualization
      kanon graph --concept tool_use  Inspect a specific entity and its connections
      kanon graph --gaps              Find concepts and tasks without training assets
      kanon status                    See confidence scores for all assets
      kanon generate --type setup_guide --concepts tool_use --audience enterprise_developer --dry-run
                                      Generate a training asset from knowledge objects
      kanon drift --evidence anthropic_tool_use_docs --change "API format changed"
                                      Report a source change and see what's affected
    """


# ---------------------------------------------------------------------------
# graph
# ---------------------------------------------------------------------------


@cli.command("graph")
@click.option("--concept", default=None, help="Show details for a specific concept ID.")
@click.option("--gaps", is_flag=True, default=False, help="Find gaps (entities without assets).")
def graph_cmd(concept: str | None, gaps: bool) -> None:
    """Explore the knowledge graph.

    \b
    Examples:
      kanon graph                     List all entities, open HTML visualization
      kanon graph --concept tool_use  Show Tool Use and its connections
      kanon graph --gaps              Find concepts/tasks missing training assets
    """
    g = _get_graph()

    if concept:
        entity = g.get(concept)
        if entity is None:
            click.echo(f"Concept '{concept}' not found in the graph.")
            return
        click.echo(f"Entity: {entity.name} [{concept}]")  # type: ignore[attr-defined]
        click.echo(f"  Type: {type(entity).__name__}")
        if hasattr(entity, "description"):
            click.echo(f"  Description: {entity.description}")

        deps = g.dependencies(concept)
        if deps:
            click.echo("\nConnects to:")
            for dep in deps:
                name = getattr(dep, "name", dep.id)  # type: ignore[attr-defined]
                click.echo(f"  → {name} [{dep.id}]")  # type: ignore[attr-defined]
        else:
            click.echo("\nConnects to: (none)")

        revs = g.dependents(concept)
        if revs:
            click.echo("\nReferenced by:")
            for rev in revs:
                name = getattr(rev, "name", rev.id)  # type: ignore[attr-defined]
                click.echo(f"  ← {name} [{rev.id}]")  # type: ignore[attr-defined]
        else:
            click.echo("\nReferenced by: (none)")
        _open_graph_html(g)
        return

    if gaps:
        # Find entity IDs referenced by assets
        assets = [e for e in g._entities.values() if isinstance(e, Asset)]
        covered_concepts: set[str] = set()
        covered_tasks: set[str] = set()
        for asset in assets:
            covered_concepts.update(asset.teaches)
            covered_tasks.update(asset.supports_tasks)

        concept_gaps = [
            e for e in g._entities.values()
            if isinstance(e, Concept) and e.id not in covered_concepts
        ]
        task_gaps = [
            e for e in g._entities.values()
            if isinstance(e, Task) and e.id not in covered_tasks
        ]

        click.echo("=== Knowledge Gaps ===")
        if concept_gaps:
            click.echo(f"\nConcepts without assets ({len(concept_gaps)}):")
            for c in concept_gaps:
                click.echo(f"  - {c.name} [{c.id}]")
        else:
            click.echo("\nAll concepts have associated assets.")

        if task_gaps:
            click.echo(f"\nTasks without assets ({len(task_gaps)}):")
            for t in task_gaps:
                click.echo(f"  - {t.name} [{t.id}]")
        else:
            click.echo("\nAll tasks have associated assets.")
        _open_graph_html(g)
        return

    # Default: overview
    by_type: dict[str, list] = defaultdict(list)
    for entity in g._entities.values():
        by_type[type(entity).__name__].append(entity)

    total = len(g._entities)
    click.echo(f"=== Knowledge Graph ===")
    click.echo(f"Total entities: {total}\n")

    for type_name in sorted(by_type):
        entities = sorted(by_type[type_name], key=lambda e: getattr(e, "name", e.id))
        click.echo(f"{type_name} ({len(entities)}):")
        for entity in entities:
            name = getattr(entity, "name", entity.id)  # type: ignore[attr-defined]
            click.echo(f"  - {name} [{entity.id}]")  # type: ignore[attr-defined]
        click.echo()

    _open_graph_html(g)


# ---------------------------------------------------------------------------
# _open_graph_html  (shared helper)
# ---------------------------------------------------------------------------


def _open_graph_html(g: KnowledgeGraph) -> None:
    """Generate docs/graph.html and print the path."""
    from kanon.visualize import generate_graph_html

    html_path = generate_graph_html(
        g, Path(__file__).parent.parent / "docs" / "graph.html"
    )
    click.echo(f"\n  Graph: file://{html_path.resolve()}")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@cli.command("status")
def status_cmd() -> None:
    """Show confidence and lifecycle status of all assets.

    \b
    Example:
      kanon status
    """
    from kanon.models.entities import Fact

    g = _get_graph()

    # Count by type
    type_counts: dict[str, int] = {}
    facts: list[Fact] = []
    assets: list[Asset] = []
    for entity in g._entities.values():
        tname = type(entity).__name__
        type_counts[tname] = type_counts.get(tname, 0) + 1
        if isinstance(entity, Fact):
            facts.append(entity)
        elif isinstance(entity, Asset):
            assets.append(entity)

    total = len(g._entities)
    superseded = sum(1 for f in facts if f.status == "superseded")
    retracted = sum(1 for f in facts if f.status == "retracted")

    click.echo(f"=== Kanon Status ===\n")
    click.echo(f"Entities: {total}")
    click.echo(
        f"  Concepts: {type_counts.get('Concept', 0)}  |  "
        f"Capabilities: {type_counts.get('Capability', 0)}  |  "
        f"Tasks: {type_counts.get('Task', 0)}  |  "
        f"Facts: {type_counts.get('Fact', 0)}"
    )
    click.echo(
        f"  Evidence: {type_counts.get('Evidence', 0)}  |  "
        f"Audiences: {type_counts.get('Audience', 0)}  |  "
        f"Objectives: {type_counts.get('LearningObjective', 0)}  |  "
        f"Constraints: {type_counts.get('Constraint', 0)}"
    )

    click.echo(f"\nAssets ({len(assets)}):")
    if assets:
        for asset in sorted(assets, key=lambda a: a.name):
            score = asset.confidence.overall
            indicator = "🟢" if score >= 0.70 else "🔴"
            click.echo(f"  {indicator} {asset.name}  |  confidence: {score:.2f}  |  state: {asset.lifecycle_state}")
    else:
        click.echo("  (none)")

    click.echo(f"\nFacts ({len(facts)}):")
    flags = []
    if superseded:
        flags.append(f"⚠️  {superseded} superseded")
    if retracted:
        flags.append(f"⚠️  {retracted} retracted")
    if flags:
        click.echo(f"  {'  |  '.join(flags)}")
    else:
        click.echo("  ✅ All facts active")


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------


@cli.command("generate")
@click.option("--type", "template_type", required=True, help="Template name (e.g. setup_guide).")
@click.option("--concepts", required=True, help="Comma-separated concept IDs.")
@click.option("--audience", required=True, help="Audience ID.")
@click.option("--dry-run", "dry_run", is_flag=True, default=False, help="Dry-run (preview only).")
def generate_cmd(template_type: str, concepts: str, audience: str, dry_run: bool) -> None:
    """Generate a training asset from knowledge objects using a template.

    \b
    Templates available: setup_guide, facilitator_guide

    \b
    Examples:
      kanon generate --type setup_guide --concepts tool_use --audience enterprise_developer --dry-run
      kanon generate --type setup_guide --concepts tool_use --audience enterprise_developer
      kanon generate --type facilitator_guide --concepts tool_use,system_prompt --audience support_engineer --dry-run
    """
    g = _get_graph()
    logger = _get_logger()

    concept_ids = [c.strip() for c in concepts.split(",") if c.strip()]

    try:
        if dry_run:
            result = generate_asset_dry_run(
                graph=g,
                template_name=template_type,
                concept_ids=concept_ids,
                audience_id=audience,
            )
        else:
            from kanon.generate import generate_asset_llm

            click.echo("Generating with Claude... ", nl=False)
            result = generate_asset_llm(
                graph=g,
                template_name=template_type,
                concept_ids=concept_ids,
                audience_id=audience,
            )
            click.echo("done.")
    except (ValueError, RuntimeError) as exc:
        click.echo(f"Error: {exc}")
        return

    # Save asset to file
    method = result["generation_method"]
    asset_id = "_".join(concept_ids) + f"_{template_type}_{method}"
    asset_path = Path(__file__).parent.parent / "data" / "assets" / f"{asset_id}.yaml"

    import yaml
    asset_data = {
        "id": asset_id,
        "name": result["name"],
        "asset_type": "guide",
        "delivery_format": result["delivery_format"],
        "lifecycle_state": result["lifecycle_state"],
        "teaches": result["teaches"],
        "targets": result["targets"],
        "evidence_links": result.get("evidence_links", []),
        "generation_method": result["generation_method"],
        "generated_at": result["generated_at"],
        "last_updated": result["last_updated"],
        "confidence": {
            "evidence": 1.0,
            "freshness": 1.0,
            "structural": 1.0,
            "transformation": 1.0 if result["generation_method"] == "dry_run" else 0.7,
            "overall": 1.0 if result["generation_method"] == "dry_run" else 0.94,
        },
        "content": result.get("content", ""),
    }
    asset_path.write_text(yaml.dump(asset_data, default_flow_style=False, sort_keys=False))

    # Summary output
    click.echo(f"=== Generated Asset ===\n")
    click.echo(f"  Name:       {result['name']}")
    click.echo(f"  Template:   {result['delivery_format']}")
    click.echo(f"  Concepts:   {', '.join(concept_ids)}")
    click.echo(f"  Audience:   {audience}")
    click.echo(f"  Method:     {result['generation_method']}")
    if result.get("model"):
        click.echo(f"  Model:      {result['model']}")
    click.echo(f"  State:      {result['lifecycle_state']}")
    click.echo(f"\n  Saved to:   {asset_path}")
    click.echo(f"  Sections:   {', '.join(result.get('content_blocks', {}).keys())}")
    if result.get("input_tokens"):
        click.echo(f"  Tokens:     {result['input_tokens']} in / {result['output_tokens']} out")

    # Citation validation and reports (LLM-generated content only)
    if result["generation_method"] == "llm":
        from kanon.citations import validate_citations, strip_citations
        from kanon.citation_report import render_citation_markdown, render_citation_html

        content = result.get("content", "")
        report = validate_citations(content, g)
        if report.total_citations > 0:
            click.echo(f"\n  Citations:  {report.total_citations} total, {len(report.valid)} valid")
            if report.is_valid:
                click.echo(f"  Validation: ✅ all citations reference active facts")
            else:
                click.echo(f"  Validation: ❌ issues found")
                for failure in report.failures:
                    click.echo(f"    - {failure}")
        else:
            click.echo(f"\n  Citations:  none found in output")

        # Save citation report artifacts
        report_dir = Path(__file__).parent.parent / "docs"
        report_base = f"{asset_id}"

        md_report = render_citation_markdown(content, report, result["name"])
        md_path = report_dir / f"{report_base}-citations.md"
        md_path.write_text(md_report)

        html_report = render_citation_html(content, report, g, result["name"])
        html_path = report_dir / f"{report_base}-citations.html"
        html_path.write_text(html_report)

        click.echo(f"\n  Report MD:  file://{md_path.resolve()}")
        click.echo(f"  Report HTML: file://{html_path.resolve()}")

    logger.log(
        operation="generate",
        input={"template": template_type, "concepts": concept_ids, "audience": audience, "dry_run": dry_run},
        result=result["name"],
    )

    # Scoped visualization
    from kanon.visualize import generate_scoped_html

    involved = set(concept_ids)
    involved.add(audience)
    involved.update(result.get("evidence_links", []))
    for e in g.subgraph(concept_ids):
        involved.add(e.id)

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    scoped_path = Path(__file__).parent.parent / "docs" / f"generate-{timestamp}.html"
    html_path = generate_scoped_html(
        graph=g,
        entity_ids=list(involved),
        highlight_ids=concept_ids,
        title="Generate Result",
        subtitle=f"{result['name']} for {audience}",
        output_path=scoped_path,
    )
    click.echo(f"\n  Visualization: file://{html_path.resolve()}")


# ---------------------------------------------------------------------------
# drift
# ---------------------------------------------------------------------------


@cli.command("drift")
@click.option("--evidence", "evidence_id", required=True, help="Evidence ID to check drift for.")
@click.option("--change", "change_description", required=True, help="Description of the change.")
def drift_cmd(evidence_id: str, change_description: str) -> None:
    """Report an evidence source change and trace its impact.

    Finds stale facts backed by the changed evidence and any training
    assets that reference those facts or the affected concepts.

    \b
    Examples:
      kanon drift --evidence anthropic_tool_use_docs --change "Tool schema format updated"
      kanon drift --evidence anthropic_models_page --change "Context window increased to 500K"
    """
    g = _get_graph()
    logger = _get_logger()

    report = detect_drift(g, evidence_id=evidence_id, change_description=change_description)

    click.echo(f"=== Drift Report ===")
    click.echo(f"Evidence: {report.evidence_id}")
    click.echo(f"Change:   {report.change_description}")

    if report.stale_facts:
        click.echo(f"\nStale Facts ({len(report.stale_facts)}):")
        for fact in report.stale_facts:
            click.echo(f"  - [{fact.id}] {fact.claim}: {fact.value}")
    else:
        click.echo("\nStale Facts: (none)")

    if report.affected_assets:
        click.echo(f"\nAffected Assets ({len(report.affected_assets)}):")
        for asset in report.affected_assets:
            score = asset.confidence.overall
            click.echo(f"  - {asset.name}  (confidence: {score:.2f})")
    else:
        click.echo("\nAffected Assets: (none)")

    trace = {
        "stale_facts": [f.id for f in report.stale_facts],
        "affected_assets": [a.id for a in report.affected_assets],
    }
    logger.log(
        operation="drift",
        input={"evidence_id": evidence_id, "change": change_description},
        result=f"{len(report.stale_facts)} stale facts, {len(report.affected_assets)} affected assets",
        trace=trace,
    )

    # Scoped visualization
    from kanon.visualize import generate_scoped_html

    involved = set([evidence_id])
    for f in report.stale_facts:
        involved.add(f.id)
        involved.add(f.concept)
    for a in report.affected_assets:
        involved.add(a.id)
        involved.update(a.teaches)

    highlight = [evidence_id] + [f.id for f in report.stale_facts] + [a.id for a in report.affected_assets]

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    scoped_path = Path(__file__).parent.parent / "docs" / f"drift-{timestamp}.html"
    html_path = generate_scoped_html(
        graph=g,
        entity_ids=list(involved),
        highlight_ids=highlight,
        title="Drift Report",
        subtitle=f"Evidence changed: {evidence_id} — {change_description}",
        output_path=scoped_path,
    )
    click.echo(f"\n  Visualization: file://{html_path.resolve()}")


# ---------------------------------------------------------------------------
# review
# ---------------------------------------------------------------------------


@cli.command("review")
@click.option("--approve", "approve_id", default=None, help="Approve an asset by ID.")
@click.option("--reject", "reject_id", default=None, help="Reject an asset by ID.")
def review_cmd(approve_id: str | None, reject_id: str | None) -> None:
    """Review assets against hard failure conditions.

    Without options, lists all assets with their review status.
    With --approve or --reject, updates the asset's lifecycle state.

    \b
    Hard failure conditions:
      - Any cited fact is superseded or retracted
      - Any cited fact ID doesn't exist in the graph
      - Evidence was verified after the asset was last updated

    \b
    Examples:
      kanon review                              Show review status of all assets
      kanon review --approve tool_use_setup_guide_llm    Approve an asset
      kanon review --reject tool_use_setup_guide_llm     Reject an asset
    """
    from kanon.review import approve_asset, reject_asset, review_all_assets

    g = _get_graph()
    logger = _get_logger()

    if approve_id:
        assets_dir = DATA_DIR / "assets"
        try:
            approve_asset(approve_id, assets_dir)
            click.echo(f"✅ Approved: {approve_id} → lifecycle_state = approved")
            logger.log(operation="review_approve", input={"asset_id": approve_id}, result="approved")
        except ValueError as e:
            click.echo(f"Error: {e}")
        return

    if reject_id:
        assets_dir = DATA_DIR / "assets"
        try:
            reject_asset(reject_id, assets_dir)
            click.echo(f"❌ Rejected: {reject_id} → lifecycle_state = needs_review")
            logger.log(operation="review_reject", input={"asset_id": reject_id}, result="needs_review")
        except ValueError as e:
            click.echo(f"Error: {e}")
        return

    # Default: review all assets
    results = review_all_assets(g)

    click.echo("=== Asset Review ===\n")

    passing = [r for r in results if r.passes]
    failing = [r for r in results if not r.passes]

    if failing:
        click.echo(f"Needs Review ({len(failing)}):")
        for r in failing:
            click.echo(f"\n  ❌ {r.asset_name} [{r.asset_id}]")
            click.echo(f"     State: {r.lifecycle_state}")
            for failure in r.failures:
                click.echo(f"     • {failure}")
        click.echo()

    if passing:
        click.echo(f"Passing ({len(passing)}):")
        for r in passing:
            click.echo(f"  ✅ {r.asset_name} [{r.asset_id}]  ({r.lifecycle_state})")
        click.echo()

    click.echo(f"Summary: {len(passing)} pass, {len(failing)} fail")


# ---------------------------------------------------------------------------
# crawl
# ---------------------------------------------------------------------------


@cli.command("crawl")
def crawl_cmd() -> None:
    """Crawl evidence source URLs and detect meaningful changes.

    Fetches each evidence source URL, compares against stored baselines,
    and reports changes. First run saves baselines. Subsequent runs detect
    content changes and can trigger drift detection.

    \b
    Examples:
      kanon crawl                     Check all evidence sources for changes
    """
    from kanon.crawl import crawl_evidence

    g = _get_graph()
    logger = _get_logger()

    click.echo("Crawling evidence sources... ", nl=False)
    report = crawl_evidence(g, DATA_DIR)
    click.echo("done.\n")

    click.echo(f"=== Crawl Report ===\n")

    if report.new:
        click.echo(f"New baselines ({len(report.new)}):")
        for r in report.new:
            click.echo(f"  📥 {r.evidence_id}: {r.url}")
        click.echo()

    if report.changed:
        click.echo(f"Changed ({len(report.changed)}):")
        for r in report.changed:
            click.echo(f"  ⚠️  {r.evidence_id}: {r.diff_summary}")
            click.echo(f"     {r.url}")
        click.echo()

    if report.unchanged:
        click.echo(f"Unchanged ({len(report.unchanged)}):")
        for r in report.unchanged:
            click.echo(f"  ✅ {r.evidence_id}")
        click.echo()

    if report.errors:
        click.echo(f"Errors ({len(report.errors)}):")
        for r in report.errors:
            click.echo(f"  ❌ {r.evidence_id}: {r.error}")
        click.echo()

    click.echo(f"Summary: {len(report.new)} new, {len(report.changed)} changed, "
               f"{len(report.unchanged)} unchanged, {len(report.errors)} errors")

    # Auto-trigger drift for changed evidence
    if report.changed:
        click.echo(f"\n--- Drift Detection ---\n")
        for r in report.changed:
            drift_report = detect_drift(g, r.evidence_id, r.diff_summary or "Content changed")
            if drift_report.stale_facts or drift_report.affected_assets:
                click.echo(f"  {r.evidence_id}:")
                for fact in drift_report.stale_facts:
                    click.echo(f"    Stale fact: [{fact.id}] {fact.claim}: {fact.value}")
                for asset in drift_report.affected_assets:
                    click.echo(f"    Affected: {asset.name}")
            else:
                click.echo(f"  {r.evidence_id}: no downstream impact")

    logger.log(
        operation="crawl",
        input={"evidence_count": len(report.results)},
        result=f"{len(report.new)} new, {len(report.changed)} changed, "
               f"{len(report.unchanged)} unchanged, {len(report.errors)} errors",
    )
