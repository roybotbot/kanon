# tests/test_graph.py
import pytest
from pathlib import Path
from canon.graph import KnowledgeGraph


@pytest.fixture
def sample_graph(tmp_path):
    """Create a minimal but complete graph fixture in tmp_path."""
    # concepts/
    concepts = tmp_path / "concepts"
    concepts.mkdir()
    (concepts / "tool_use.yaml").write_text(
        "id: tool_use\n"
        "name: Tool Use\n"
        "description: Call external functions\n"
        "supports:\n  - data_extraction\n"
        "prerequisites:\n  - api_auth\n"
    )
    (concepts / "api_auth.yaml").write_text(
        "id: api_auth\n"
        "name: API Authentication\n"
        "description: Authenticating API calls\n"
    )

    # capabilities/
    capabilities = tmp_path / "capabilities"
    capabilities.mkdir()
    (capabilities / "data_extraction.yaml").write_text(
        "id: data_extraction\n"
        "name: Data Extraction\n"
        "description: Extract structured data\n"
        "enables:\n  - configure_tools\n"
    )

    # tasks/
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "configure_tools.yaml").write_text(
        "id: configure_tools\n"
        "name: Configure Tools\n"
        "description: Set up tool definitions\n"
        "targets:\n  - dev\n"
    )

    # audiences/
    audiences = tmp_path / "audiences"
    audiences.mkdir()
    (audiences / "dev.yaml").write_text(
        "id: dev\n"
        "name: Developer\n"
        "description: Software developers\n"
    )

    # evidence/
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "tool_docs.yaml").write_text(
        "id: tool_docs\n"
        "name: Tool Documentation\n"
        "source_type: docs\n"
        "last_verified: 2024-01-01\n"
    )

    # facts/
    facts = tmp_path / "facts"
    facts.mkdir()
    (facts / "max_tools.yaml").write_text(
        "id: max_tools\n"
        "claim: Max tools per request\n"
        "value: '64'\n"
        "status: active\n"
        "concept: tool_use\n"
        "evidence:\n  - tool_docs\n"
        "effective_date: 2024-01-01\n"
        "recorded_date: 2024-01-02\n"
    )

    # assets/
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "tool_guide.yaml").write_text(
        "id: tool_guide\n"
        "name: Tool Use Guide\n"
        "asset_type: guide\n"
        "delivery_format: markdown\n"
        "lifecycle_state: draft\n"
        "teaches:\n  - tool_use\n"
        "demonstrates:\n  - data_extraction\n"
        "supports_tasks:\n  - configure_tools\n"
        "targets:\n  - dev\n"
        "references:\n  - max_tools\n"
        "evidence_links:\n  - tool_docs\n"
        "generation_method: llm\n"
        "generated_at: '2024-01-01T12:00:00'\n"
        "last_updated: '2024-01-02T12:00:00'\n"
        "confidence:\n"
        "  evidence: 0.9\n"
        "  freshness: 0.8\n"
        "  structural: 0.85\n"
        "  transformation: 0.7\n"
        "  overall: 0.81\n"
        "content: Guide content here.\n"
    )

    return KnowledgeGraph(data_dir=tmp_path)


class TestGraphLoad:
    def test_loads_all_entities(self, sample_graph):
        g = sample_graph
        assert g.get("tool_use") is not None
        assert g.get("api_auth") is not None
        assert g.get("data_extraction") is not None
        assert g.get("configure_tools") is not None
        assert g.get("dev") is not None
        assert g.get("tool_docs") is not None
        assert g.get("max_tools") is not None
        assert g.get("tool_guide") is not None

    def test_get_nonexistent_returns_none(self, sample_graph):
        assert sample_graph.get("does_not_exist") is None


class TestGraphForward:
    def test_dependencies_returns_connected_entities(self, sample_graph):
        # tool_use supports data_extraction and has prerequisite api_auth
        deps = sample_graph.dependencies("tool_use")
        dep_ids = {e.id for e in deps}
        assert "data_extraction" in dep_ids
        assert "api_auth" in dep_ids

    def test_leaf_has_no_dependencies(self, sample_graph):
        # api_auth has no relationship fields populated
        deps = sample_graph.dependencies("api_auth")
        assert deps == []


class TestGraphReverse:
    def test_dependents_finds_assets_that_reference_concept(self, sample_graph):
        # tool_guide teaches tool_use → tool_use should have tool_guide as dependent
        dependents = sample_graph.dependents("tool_use")
        dep_ids = {e.id for e in dependents}
        assert "tool_guide" in dep_ids

    def test_dependents_of_evidence_finds_facts_and_assets(self, sample_graph):
        # max_tools has evidence=[tool_docs], tool_guide has evidence_links=[tool_docs]
        dependents = sample_graph.dependents("tool_docs")
        dep_ids = {e.id for e in dependents}
        assert "max_tools" in dep_ids
        assert "tool_guide" in dep_ids


class TestGraphImpact:
    def test_impact_of_evidence_finds_affected_assets_and_facts(self, sample_graph):
        # Changing tool_docs should surface max_tools and tool_guide
        impacted = sample_graph.impact_of("tool_docs")
        imp_ids = {e.id for e in impacted}
        assert "max_tools" in imp_ids
        assert "tool_guide" in imp_ids

    def test_impact_of_concept_finds_assets(self, sample_graph):
        # Changing tool_use should surface tool_guide (teaches tool_use)
        impacted = sample_graph.impact_of("tool_use")
        imp_ids = {e.id for e in impacted}
        assert "tool_guide" in imp_ids


class TestGraphSubgraph:
    def test_subgraph_from_concept_walks_forward(self, sample_graph):
        # tool_use → supports data_extraction → enables configure_tools
        sub = sample_graph.subgraph(["tool_use"])
        sub_ids = {e.id for e in sub}
        assert "tool_use" in sub_ids
        assert "data_extraction" in sub_ids
        assert "configure_tools" in sub_ids

    def test_subgraph_does_not_walk_reverse(self, sample_graph):
        # tool_guide teaches tool_use but subgraph from tool_use (forward only)
        # should NOT include tool_guide since tool_guide doesn't appear in tool_use's outgoing edges
        sub = sample_graph.subgraph(["tool_use"])
        sub_ids = {e.id for e in sub}
        assert "tool_guide" not in sub_ids
