"""Tests for canon/generate.py — dry-run asset generation."""
from __future__ import annotations

import pytest

from canon.generate import generate_asset_dry_run, load_template
from canon.graph import KnowledgeGraph
from canon.models.entities import Audience, Concept


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_graph(tmp_path, concepts=None, audiences=None):
    """Build a minimal graph from scratch in a temp directory."""
    import yaml

    concepts_dir = tmp_path / "concepts"
    audiences_dir = tmp_path / "audiences"
    concepts_dir.mkdir(parents=True, exist_ok=True)
    audiences_dir.mkdir(parents=True, exist_ok=True)

    for c in (concepts or []):
        (concepts_dir / f"{c['id']}.yaml").write_text(yaml.dump(c))

    for a in (audiences or []):
        (audiences_dir / f"{a['id']}.yaml").write_text(yaml.dump(a))

    return KnowledgeGraph(data_dir=tmp_path)


# ---------------------------------------------------------------------------
# TestLoadTemplate
# ---------------------------------------------------------------------------

class TestLoadTemplate:
    def test_load_setup_guide(self):
        tmpl = load_template("setup_guide")
        assert "overview" in tmpl["sections"]
        assert "prerequisites" in tmpl["sections"]

    def test_load_facilitator_guide(self):
        tmpl = load_template("facilitator_guide")
        assert "key_concepts" in tmpl["sections"]

    def test_load_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            load_template("nonexistent_template")


# ---------------------------------------------------------------------------
# TestDryRunGeneration
# ---------------------------------------------------------------------------

class TestDryRunGeneration:
    def test_generates_content(self, tmp_path):
        graph = _make_graph(
            tmp_path,
            concepts=[
                {
                    "id": "tool_use",
                    "name": "Tool Use",
                    "description": "How to use tools with Claude.",
                    "supports": [],
                    "prerequisites": [],
                    "content_block": "Tool use allows models to call external functions.",
                }
            ],
            audiences=[
                {
                    "id": "dev",
                    "name": "Developer",
                    "description": "Software developers.",
                    "assumed_knowledge": [],
                    "tone": "technical",
                    "preferred_formats": [],
                }
            ],
        )

        result = generate_asset_dry_run(
            graph=graph,
            template_name="setup_guide",
            concept_ids=["tool_use"],
            audience_id="dev",
        )

        assert "tool_use" in result["teaches"]
        assert "Tool Use" in result["content"]
        assert result["generation_method"] == "dry_run"

    def test_missing_concept_raises(self, tmp_path):
        graph = _make_graph(tmp_path)  # empty graph

        with pytest.raises(ValueError, match="not found"):
            generate_asset_dry_run(
                graph=graph,
                template_name="setup_guide",
                concept_ids=["nonexistent"],
                audience_id="dev",
            )

    def test_missing_audience_raises(self, tmp_path):
        graph = _make_graph(
            tmp_path,
            concepts=[
                {
                    "id": "tool_use",
                    "name": "Tool Use",
                    "description": "How to use tools with Claude.",
                    "supports": [],
                    "prerequisites": [],
                    "content_block": None,
                }
            ],
        )

        with pytest.raises(ValueError, match="not found"):
            generate_asset_dry_run(
                graph=graph,
                template_name="setup_guide",
                concept_ids=["tool_use"],
                audience_id="nonexistent_audience",
            )

    def test_output_has_all_template_sections(self, tmp_path):
        graph = _make_graph(
            tmp_path,
            concepts=[
                {
                    "id": "tool_use",
                    "name": "Tool Use",
                    "description": "How to use tools with Claude.",
                    "supports": [],
                    "prerequisites": [],
                    "content_block": "Tool use allows models to call external functions.",
                }
            ],
            audiences=[
                {
                    "id": "dev",
                    "name": "Developer",
                    "description": "Software developers.",
                    "assumed_knowledge": [],
                    "tone": "technical",
                    "preferred_formats": [],
                }
            ],
        )

        template = load_template("setup_guide")
        result = generate_asset_dry_run(
            graph=graph,
            template_name="setup_guide",
            concept_ids=["tool_use"],
            audience_id="dev",
        )

        for section in template["sections"]:
            header = f"## {section.replace('_', ' ').title()}"
            assert header in result["content"], f"Missing section header: {header}"
