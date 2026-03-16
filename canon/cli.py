"""Canon CLI — graph, status, generate, and drift commands."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import click

from canon.audit import AuditLogger
from canon.drift import detect_drift
from canon.generate import generate_asset_dry_run
from canon.graph import KnowledgeGraph
from canon.models.entities import Asset, Concept, Task

DATA_DIR = Path(__file__).parent.parent / "data"
LOG_PATH = Path(__file__).parent.parent / "logs" / "audit.jsonl"


def _get_graph() -> KnowledgeGraph:
    return KnowledgeGraph(data_dir=DATA_DIR)


def _get_logger() -> AuditLogger:
    return AuditLogger(log_path=LOG_PATH)


@click.group()
def cli() -> None:
    """Canon — ontology-driven knowledge management CLI."""


# ---------------------------------------------------------------------------
# graph
# ---------------------------------------------------------------------------


@cli.command("graph")
@click.option("--concept", default=None, help="Show details for a specific concept ID.")
@click.option("--gaps", is_flag=True, default=False, help="Find gaps (entities without assets).")
def graph_cmd(concept: str | None, gaps: bool) -> None:
    """Explore the knowledge graph."""
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


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@cli.command("status")
def status_cmd() -> None:
    """Show confidence and lifecycle status of all assets."""
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
    """Generate an asset from a template."""
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


# ---------------------------------------------------------------------------
# drift
# ---------------------------------------------------------------------------


@cli.command("drift")
@click.option("--evidence", "evidence_id", required=True, help="Evidence ID to check drift for.")
@click.option("--change", "change_description", required=True, help="Description of the change.")
def drift_cmd(evidence_id: str, change_description: str) -> None:
    """Detect drift caused by an evidence change."""
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
