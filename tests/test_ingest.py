"""Tests for Experiment 02: Ingestion.

Unit tests use pre-built entity dicts (no API calls).
Integration tests call the real LLM and are marked with pytest.mark.llm.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kanon.ingest import validate_ingested, save_ingested
from kanon.graph import KnowledgeGraph


# ── Fixtures ─────────────────────────────────────────────────────────


VALID_ENTITIES = {
    "evidence": [
        {
            "id": "test_docs",
            "name": "Test Documentation",
            "description": "Test source",
            "source_type": "documentation",
            "last_verified": "2025-06-01",
        },
    ],
    "concepts": [
        {
            "id": "batch_processing",
            "name": "Batch Processing",
            "description": "Processing multiple requests in a single API call",
            "content_block": "Batch processing allows sending multiple messages in one request.",
        },
    ],
    "facts": [
        {
            "id": "batch_max_requests",
            "claim": "Maximum requests per batch",
            "value": "10,000",
            "numeric_value": 10000,
            "status": "active",
            "concept": "batch_processing",
            "evidence": ["test_docs"],
            "effective_date": "2025-06-01",
            "recorded_date": "2025-06-01",
        },
    ],
    "tasks": [
        {
            "id": "submit_batch_job",
            "name": "Submit a Batch Job",
            "description": "Send a batch of requests to the API",
            "steps": [
                "Prepare JSONL file with requests",
                "Upload file via Files API",
                "Submit batch with file ID",
                "Poll for completion",
            ],
            "content_block": "Create a JSONL file with one request per line.",
        },
    ],
}

INVALID_ENTITIES = {
    "concepts": [
        {
            # Missing required 'name' and 'description'
            "id": "broken_concept",
        },
    ],
    "facts": [
        {
            "id": "broken_fact",
            "claim": "Some claim",
            "value": "Some value",
            "status": "invalid_status",  # Not active/superseded/retracted
            "concept": "batch_processing",
            "evidence": ["test_docs"],
            "effective_date": "2025-06-01",
            "recorded_date": "2025-06-01",
        },
    ],
}


# ── Validation ───────────────────────────────────────────────────────


class TestValidateIngested:
    def test_valid_entities_pass(self):
        errors = validate_ingested(VALID_ENTITIES)
        assert errors == {}, f"Valid entities should have no errors: {errors}"

    def test_invalid_concept_caught(self):
        errors = validate_ingested(INVALID_ENTITIES)
        assert "concepts" in errors
        assert any("broken_concept" in e for e in errors["concepts"])

    def test_invalid_fact_status_caught(self):
        errors = validate_ingested(INVALID_ENTITIES)
        assert "facts" in errors
        assert any("broken_fact" in e for e in errors["facts"])

    def test_empty_entities_valid(self):
        errors = validate_ingested({"concepts": [], "facts": [], "tasks": [], "evidence": []})
        assert errors == {}

    def test_missing_keys_valid(self):
        errors = validate_ingested({})
        assert errors == {}


# ── Save ─────────────────────────────────────────────────────────────


class TestSaveIngested:
    def test_saves_to_yaml(self, tmp_path):
        for subdir in ["concepts", "facts", "tasks", "evidence"]:
            (tmp_path / subdir).mkdir()

        written = save_ingested(VALID_ENTITIES, tmp_path)
        assert len(written) == 4  # 1 evidence + 1 concept + 1 fact + 1 task

        # Verify files exist and are valid YAML
        concept_path = tmp_path / "concepts" / "batch_processing.yaml"
        assert concept_path.exists()
        data = yaml.safe_load(concept_path.read_text())
        assert data["name"] == "Batch Processing"

    def test_saved_entities_load_into_graph(self, tmp_path):
        """Saved entities should be loadable by KnowledgeGraph."""
        for subdir in ["concepts", "facts", "tasks", "evidence",
                        "capabilities", "constraints", "objectives",
                        "audiences", "assets"]:
            (tmp_path / subdir).mkdir()

        save_ingested(VALID_ENTITIES, tmp_path)
        graph = KnowledgeGraph(data_dir=tmp_path)

        assert graph.get("batch_processing") is not None
        assert graph.get("batch_max_requests") is not None
        assert graph.get("submit_batch_job") is not None
        assert graph.get("test_docs") is not None

    def test_saved_entities_have_relationships(self, tmp_path):
        """Facts should connect to concepts via graph traversal."""
        for subdir in ["concepts", "facts", "tasks", "evidence",
                        "capabilities", "constraints", "objectives",
                        "audiences", "assets"]:
            (tmp_path / subdir).mkdir()

        save_ingested(VALID_ENTITIES, tmp_path)
        graph = KnowledgeGraph(data_dir=tmp_path)

        # Fact should point to concept
        fact = graph.get("batch_max_requests")
        assert fact.concept == "batch_processing"

        # Concept should be reachable from fact via graph
        deps = graph.dependencies("batch_max_requests")
        dep_ids = {getattr(d, "id", None) for d in deps}
        assert "batch_processing" in dep_ids


# ── LLM Integration (requires API) ──────────────────────────────────


class TestIngestLLM:
    """Tests that call the real LLM. Only run when API is available."""

    @pytest.fixture
    def can_call_api(self):
        from kanon.auth import get_credential
        cred = get_credential()
        if cred is None:
            pytest.skip("No API credential available")
        return cred

    def test_ingest_short_text(self, can_call_api, tmp_path):
        """Ingest a short, clear text and verify output structure."""
        from kanon.ingest import ingest_text

        text = """
        Claude's Messages API supports batch processing for high-throughput use cases.
        You can submit up to 10,000 requests in a single batch. Each request in the
        batch is processed independently. Batch results are available within 24 hours.

        To submit a batch:
        1. Create a JSONL file with one request per line
        2. Upload the file using the Files API
        3. Create a batch referencing the uploaded file ID
        4. Poll the batch status endpoint until processing completes
        """

        entities = ingest_text(text, source_name="Batch API Test")

        # Should have at least one of each type
        assert len(entities.get("concepts", [])) >= 1
        assert len(entities.get("facts", [])) >= 1
        assert len(entities.get("tasks", [])) >= 1

        # Should pass validation
        errors = validate_ingested(entities)
        assert errors == {}, f"Ingested entities should validate: {errors}"

        # Should be saveable and loadable
        for subdir in ["concepts", "facts", "tasks", "evidence",
                        "capabilities", "constraints", "objectives",
                        "audiences", "assets"]:
            (tmp_path / subdir).mkdir()

        save_ingested(entities, tmp_path)
        graph = KnowledgeGraph(data_dir=tmp_path)
        assert len(graph.entities) >= 3  # at least concept + fact + evidence

    def test_ingest_real_crawled_content(self, can_call_api, tmp_path):
        """Ingest real crawled content from Anthropic docs."""
        from kanon.ingest import ingest_text

        # Use a snippet of the crawled tool use docs
        baseline_path = Path(__file__).parent.parent / "data" / "evidence_baselines" / "anthropic_tool_use_docs.txt"
        if not baseline_path.exists():
            pytest.skip("No crawled baseline available — run 'kanon crawl' first")

        # Use first 3000 chars to keep token usage reasonable
        text = baseline_path.read_text()[:3000]

        entities = ingest_text(
            text,
            source_name="Anthropic Tool Use Documentation",
            source_url="https://docs.anthropic.com/en/docs/build-with-claude/tool-use",
        )

        # Should produce entities
        assert len(entities.get("concepts", [])) >= 1
        assert len(entities.get("facts", [])) >= 0  # may not have numeric facts

        # Should validate
        errors = validate_ingested(entities)
        assert errors == {}, f"Ingested entities should validate: {errors}"

        # Save and load
        for subdir in ["concepts", "facts", "tasks", "evidence",
                        "capabilities", "constraints", "objectives",
                        "audiences", "assets"]:
            (tmp_path / subdir).mkdir()

        save_ingested(entities, tmp_path)
        graph = KnowledgeGraph(data_dir=tmp_path)
        assert len(graph.entities) >= 2

        # Print what was extracted for review
        print(f"\n--- Ingested from tool use docs ---")
        for entity_type, items in entities.items():
            if items:
                print(f"\n{entity_type}:")
                for item in items:
                    print(f"  {item.get('id')}: {item.get('name', item.get('claim', ''))}")
