# tests/test_integration.py
"""End-to-end test: load real seed data, run all operations."""
import pytest
from pathlib import Path
from canon.graph import KnowledgeGraph
from canon.confidence import calculate_confidence, needs_review
from canon.drift import detect_drift
from canon.generate import generate_asset_dry_run
from canon.audit import AuditLogger


DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture
def graph():
    g = KnowledgeGraph()
    g.load(DATA_DIR)
    return g


class TestIntegration:
    def test_graph_loads_seed_data(self, graph):
        assert len(graph.entities) >= 20

    def test_can_traverse_from_concept(self, graph):
        deps = graph.dependencies("tool_use")
        assert len(deps) > 0

    def test_can_get_dependents(self, graph):
        deps = graph.dependents("tool_use")
        assert len(deps) > 0

    def test_impact_of_evidence(self, graph):
        impacted = graph.impact_of("anthropic_tool_use_docs")
        assert len(impacted) > 0

    def test_can_generate_dry_run(self, graph):
        result = generate_asset_dry_run(
            graph=graph,
            template_name="setup_guide",
            concept_ids=["tool_use"],
            audience_id="enterprise_developer",
        )
        assert len(result["content"]) > 100
        assert result["generation_method"] == "dry_run"
        assert "tool_use" in result["teaches"]

    def test_can_generate_facilitator_guide(self, graph):
        result = generate_asset_dry_run(
            graph=graph,
            template_name="facilitator_guide",
            concept_ids=["tool_use", "system_prompt"],
            audience_id="enterprise_developer",
        )
        assert len(result["content"]) > 100
        assert "tool_use" in result["teaches"]
        assert "system_prompt" in result["teaches"]

    def test_drift_detection_finds_impact(self, graph):
        report = detect_drift(graph, "anthropic_tool_use_docs", "Tool use API changed")
        assert report.evidence_id == "anthropic_tool_use_docs"
        affected_ids = [a.id for a in report.affected_assets]
        assert "tool_use_facilitator_guide" in affected_ids

    def test_drift_finds_stale_facts(self, graph):
        report = detect_drift(graph, "anthropic_tool_use_docs", "Max tools changed")
        stale_ids = [f.id for f in report.stale_facts]
        assert "tool_use_max_tools" in stale_ids

    def test_confidence_calculation(self):
        score = calculate_confidence(
            asset_teaches=["c1", "c2"],
            concepts_with_evidence={"c1", "c2"},
            fresh_evidence_count=2,
            total_evidence_count=2,
            structural_checks_passed=6,
            structural_checks_total=6,
            generation_method="dry_run",
        )
        assert score.overall == 1.0
        assert not needs_review(score)

    def test_confidence_below_threshold(self):
        score = calculate_confidence(
            asset_teaches=["c1", "c2", "c3"],
            concepts_with_evidence={"c1"},
            fresh_evidence_count=1,
            total_evidence_count=3,
            structural_checks_passed=2,
            structural_checks_total=6,
            generation_method="llm_multi",
        )
        assert score.overall < 0.70
        assert needs_review(score)

    def test_audit_log_works(self, tmp_path):
        logger = AuditLogger(tmp_path / "test_audit.jsonl")
        logger.log(operation="test", input={"x": 1}, result="ok")
        assert (tmp_path / "test_audit.jsonl").exists()
