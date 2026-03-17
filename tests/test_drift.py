# tests/test_drift.py
import pytest
from kanon.graph import KnowledgeGraph
from kanon.drift import detect_drift, DriftReport


@pytest.fixture
def graph_with_stale_evidence(tmp_path):
    """Build a minimal graph with one stale evidence source."""
    # concepts/
    concepts = tmp_path / "concepts"
    concepts.mkdir()
    (concepts / "ctx.yaml").write_text(
        "id: ctx\n"
        "name: Context Window\n"
        "description: The maximum token capacity of a model's context.\n"
    )

    # evidence/
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "ctx_docs.yaml").write_text(
        "id: ctx_docs\n"
        "name: Context Window Documentation\n"
        "source_type: docs\n"
        "last_verified: 2026-03-10\n"
        "change_log:\n"
        "  - date: 2026-03-10\n"
        "    description: Context window increased to 200k tokens\n"
        "    detected_by: manual_review\n"
    )

    # facts/
    facts = tmp_path / "facts"
    facts.mkdir()
    (facts / "ctx_200k.yaml").write_text(
        "id: ctx_200k\n"
        "claim: Context window size\n"
        "value: '200000'\n"
        "numeric_value: 200000\n"
        "status: active\n"
        "concept: ctx\n"
        "evidence:\n  - ctx_docs\n"
        "effective_date: 2026-03-10\n"
        "recorded_date: 2026-03-10\n"
    )

    # assets/
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "ctx_guide.yaml").write_text(
        "id: ctx_guide\n"
        "name: Context Window Guide\n"
        "asset_type: guide\n"
        "delivery_format: markdown\n"
        "lifecycle_state: published\n"
        "teaches:\n  - ctx\n"
        "targets:\n  - dev\n"
        "references:\n  - ctx_200k\n"
        "evidence_links:\n  - ctx_docs\n"
        "generation_method: llm\n"
        "generated_at: '2026-02-01T00:00:00'\n"
        "last_updated: '2026-02-01T00:00:00'\n"
        "confidence:\n"
        "  evidence: 1.0\n"
        "  freshness: 1.0\n"
        "  structural: 1.0\n"
        "  transformation: 0.7\n"
        "  overall: 1.0\n"
        "content: Guide to context window usage.\n"
    )

    # audiences/
    audiences = tmp_path / "audiences"
    audiences.mkdir()
    (audiences / "dev.yaml").write_text(
        "id: dev\n"
        "name: Developer\n"
        "description: Software developers\n"
    )

    # empty dirs required by the loader
    for subdir in ("capabilities", "tasks", "objectives", "constraints"):
        (tmp_path / subdir).mkdir()

    return KnowledgeGraph(data_dir=tmp_path)


class TestDriftDetection:
    def test_detect_stale_assets(self, graph_with_stale_evidence):
        report = detect_drift(
            graph_with_stale_evidence,
            evidence_id="ctx_docs",
            change_description="Context window increased to 200k tokens",
        )
        asset_ids = {a.id for a in report.affected_assets}
        assert "ctx_guide" in asset_ids

    def test_detect_stale_facts(self, graph_with_stale_evidence):
        report = detect_drift(
            graph_with_stale_evidence,
            evidence_id="ctx_docs",
            change_description="Context window increased to 200k tokens",
        )
        fact_ids = {f.id for f in report.stale_facts}
        assert "ctx_200k" in fact_ids

    def test_report_has_evidence_id(self, graph_with_stale_evidence):
        report = detect_drift(
            graph_with_stale_evidence,
            evidence_id="ctx_docs",
            change_description="Context window increased to 200k tokens",
        )
        assert report.evidence_id == "ctx_docs"

    def test_report_has_change_description(self, graph_with_stale_evidence):
        description = "Context window increased to 200k tokens"
        report = detect_drift(
            graph_with_stale_evidence,
            evidence_id="ctx_docs",
            change_description=description,
        )
        assert report.change_description == description
