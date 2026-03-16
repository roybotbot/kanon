from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

class AuditLogger:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, operation: str, input: dict[str, Any], result: str, trace: Optional[dict[str, Any]] = None):
        entry = {
            "operation": operation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input": input,
            "result": result,
        }
        if trace:
            entry["trace"] = trace
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
