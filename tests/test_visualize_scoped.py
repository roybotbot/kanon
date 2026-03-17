import pytest
from pathlib import Path
from kanon.graph import KnowledgeGraph
from kanon.visualize import generate_scoped_html


@pytest.fixture
def sample_graph(tmp_path):
    concepts = tmp_path / "concepts"
    concepts.mkdir()
    (concepts / "c1.yaml").write_text("id: c1\nname: Concept One\ndescription: desc\nsupports:\n  - cap1\n")
    capabilities = tmp_path / "capabilities"
    capabilities.mkdir()
    (capabilities / "cap1.yaml").write_text("id: cap1\nname: Cap One\ndescription: desc\nenables:\n  - t1\n")
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "t1.yaml").write_text("id: t1\nname: Task One\ndescription: desc\n")
    for d in ["audiences", "objectives", "facts", "evidence", "assets", "constraints"]:
        (tmp_path / d).mkdir()
    g = KnowledgeGraph()
    g.load(tmp_path)
    return g


class TestScopedVisualize:
    def test_generates_file(self, sample_graph, tmp_path):
        output = tmp_path / "scoped.html"
        result = generate_scoped_html(
            sample_graph, ["c1", "cap1"], ["c1"],
            "Test", "Test subtitle", output
        )
        assert result.exists()

    def test_contains_only_scoped_entities(self, sample_graph, tmp_path):
        output = tmp_path / "scoped.html"
        generate_scoped_html(
            sample_graph, ["c1", "cap1"], ["c1"],
            "Test", "Test subtitle", output
        )
        content = output.read_text()
        assert "Concept One" in content
        assert "Cap One" in content
        assert "Task One" not in content  # t1 not in entity_ids

    def test_contains_title(self, sample_graph, tmp_path):
        output = tmp_path / "scoped.html"
        generate_scoped_html(
            sample_graph, ["c1"], ["c1"],
            "Drift Report", "Evidence changed: e1", output
        )
        content = output.read_text()
        assert "Drift Report" in content
        assert "Evidence changed: e1" in content

    def test_self_contained(self, sample_graph, tmp_path):
        output = tmp_path / "scoped.html"
        generate_scoped_html(
            sample_graph, ["c1"], ["c1"],
            "Test", "sub", output
        )
        content = output.read_text()
        assert "<html" in content
        assert "src=\"http" not in content
