# tests/test_loader.py
import pytest
from pathlib import Path
from kanon.loader import load_entities_from_dir
from kanon.models.entities import Concept


class TestLoader:
    def test_load_concepts(self, tmp_path):
        concept_dir = tmp_path / "concepts"
        concept_dir.mkdir()
        (concept_dir / "test.yaml").write_text(
            "id: test_concept\nname: Test\ndescription: A test concept\n"
        )
        entities = load_entities_from_dir(concept_dir, Concept)
        assert len(entities) == 1
        assert entities[0].id == "test_concept"

    def test_load_empty_dir(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        entities = load_entities_from_dir(empty_dir, Concept)
        assert entities == []

    def test_load_skips_non_yaml(self, tmp_path):
        d = tmp_path / "concepts"
        d.mkdir()
        (d / "readme.md").write_text("not yaml")
        (d / "test.yaml").write_text("id: c1\nname: C1\ndescription: desc\n")
        entities = load_entities_from_dir(d, Concept)
        assert len(entities) == 1

    def test_load_real_fixture(self):
        entities = load_entities_from_dir(Path("data/concepts"), Concept)
        found = [e for e in entities if e.id == "tool_use"]
        assert len(found) == 1
        assert "structured_data_extraction" in found[0].supports
