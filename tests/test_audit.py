import json
import pytest
from pathlib import Path
from kanon.audit import AuditLogger

class TestAuditLogger:
    def test_log_creates_file(self, tmp_path):
        logger = AuditLogger(tmp_path / "audit.jsonl")
        logger.log(operation="test", input={"key": "val"}, result="ok")
        assert (tmp_path / "audit.jsonl").exists()

    def test_log_writes_valid_json(self, tmp_path):
        logger = AuditLogger(tmp_path / "audit.jsonl")
        logger.log(operation="drift_detect", input={"evidence": "e1"}, result="flagged")
        lines = (tmp_path / "audit.jsonl").read_text().strip().split("\n")
        entry = json.loads(lines[0])
        assert entry["operation"] == "drift_detect"
        assert "timestamp" in entry

    def test_multiple_entries(self, tmp_path):
        logger = AuditLogger(tmp_path / "audit.jsonl")
        logger.log(operation="op1", input={}, result="r1")
        logger.log(operation="op2", input={}, result="r2")
        lines = (tmp_path / "audit.jsonl").read_text().strip().split("\n")
        assert len(lines) == 2

    def test_log_with_trace(self, tmp_path):
        logger = AuditLogger(tmp_path / "audit.jsonl")
        logger.log(
            operation="drift_detect",
            input={"evidence_id": "ctx_docs"},
            trace={"stale_facts": ["f1"], "affected_assets": ["a1"]},
            result="asset flagged"
        )
        lines = (tmp_path / "audit.jsonl").read_text().strip().split("\n")
        entry = json.loads(lines[0])
        assert entry["trace"]["stale_facts"] == ["f1"]
