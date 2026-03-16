import pytest
from pathlib import Path
from canon.graph import KnowledgeGraph
from canon.visualize import generate_graph_html


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


class TestVisualize:
    def test_generates_html_file(self, sample_graph, tmp_path):
        output = tmp_path / "graph.html"
        result = generate_graph_html(sample_graph, output)
        assert result.exists()
        assert result.suffix == ".html"

    def test_html_contains_entity_data(self, sample_graph, tmp_path):
        output = tmp_path / "graph.html"
        generate_graph_html(sample_graph, output)
        content = output.read_text()
        assert "Concept One" in content
        assert "Cap One" in content
        assert "Task One" in content

    def test_html_contains_edges(self, sample_graph, tmp_path):
        output = tmp_path / "graph.html"
        generate_graph_html(sample_graph, output)
        content = output.read_text()
        assert "supports" in content
        assert "enables" in content

    def test_html_is_self_contained(self, sample_graph, tmp_path):
        output = tmp_path / "graph.html"
        generate_graph_html(sample_graph, output)
        content = output.read_text()
        assert "<html" in content
        assert "<script" in content
        assert "<style" in content
        # No external references
        assert 'src="http' not in content
        assert 'href="http' not in content
