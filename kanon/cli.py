"""Kanon CLI — graph, status, generate, and drift commands."""
from __future__ import annotations

import webbrowser
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
    """Generate docs/graph.html and open it in the default browser."""
    from kanon.visualize import generate_graph_html

    html_path = generate_graph_html(
        g, Path(__file__).parent.parent / "docs" / "graph.html"
    )
    webbrowser.open(f"file://{html_path.resolve()}")


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
    g = _get_graph()
    assets = [e for e in g._entities.values() if isinstance(e, Asset)]

    if not assets:
        click.echo("No assets found.")
        return

    click.echo("=== Asset Status ===\n")
    for asset in sorted(assets, key=lambda a: a.name):
        score = asset.confidence.overall
        indicator = "🟢" if score >= 0.70 else "🔴"
        click.echo(f"{indicator} {asset.name}")
        click.echo(f"   Confidence: {score:.2f}  |  State: {asset.lifecycle_state}")
        click.echo()


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
      kanon generate --type facilitator_guide --concepts tool_use,system_prompt --audience support_engineer --dry-run
    """
    g = _get_graph()
    logger = _get_logger()

    concept_ids = [c.strip() for c in concepts.split(",") if c.strip()]

    try:
        result = generate_asset_dry_run(
            graph=g,
            template_name=template_type,
            concept_ids=concept_ids,
            audience_id=audience,
        )
    except ValueError as exc:
        click.echo(f"Error: {exc}")
        return

    click.echo(f"=== Generated Asset ===")
    click.echo(f"Name: {result['name']}")
    click.echo(f"Type: {result['delivery_format']}  |  State: {result['lifecycle_state']}")
    click.echo(f"\n--- Content Preview ---")
    # Print first 1000 chars of content
    content = result.get("content", "")
    click.echo(content[:1000])
    if len(content) > 1000:
        click.echo("... (truncated)")

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
    webbrowser.open(f"file://{html_path.resolve()}")


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
    webbrowser.open(f"file://{html_path.resolve()}")
