"""Ingest unstructured content into Kanon ontology entities.

Takes raw text (documentation, articles, etc.) and uses an LLM to
decompose it into structured ontology entities: concepts, facts,
tasks, evidence, and audiences.
"""
from __future__ import annotations

import json
from datetime import date, datetime, UTC
from typing import Any

import httpx

from kanon.auth import get_credential
from kanon.generate import ANTHROPIC_API_URL, ANTHROPIC_MODEL

INGESTION_SYSTEM_PROMPT = """\
You are a knowledge extraction system for Kanon, an ontology-driven training content system.

Your job is to decompose unstructured text into structured ontology entities. Extract ONLY what is explicitly stated in the source text. Do not infer, guess, or add information.

## Entity Types

### Concept
An idea a learner must understand. Has: id, name, description, content_block (2-3 sentence explanation).
- id format: snake_case, concise (e.g., "tool_use", "context_window")
- Only create a concept if a learner needs to understand it independently to perform a task.

### Fact
A specific, verifiable claim. Has: id, claim (what is stated), value (the assertion), numeric_value (if applicable), concept (which concept this belongs to).
- Facts are atomic: one claim per fact.
- Must be directly stated in the source, not inferred.
- id format: descriptive snake_case (e.g., "context_window_max", "tool_use_max_tools")

### Task
An action a user performs. Has: id, name, description, steps (ordered list), content_block.
- Only extract tasks that are explicitly described as steps/procedures in the source.

### Evidence
The source document itself. Has: id, name, description, url (if known), source_type.

## Output Format

Respond with a JSON object containing arrays for each entity type:

```json
{
  "evidence": [{ "id": "...", "name": "...", "description": "...", "source_type": "documentation" }],
  "concepts": [{ "id": "...", "name": "...", "description": "...", "content_block": "..." }],
  "facts": [{ "id": "...", "claim": "...", "value": "...", "numeric_value": null, "concept": "concept_id" }],
  "tasks": [{ "id": "...", "name": "...", "description": "...", "steps": ["..."], "content_block": "..." }]
}
```

## Rules
- Extract only what is explicitly stated. Do not add background knowledge.
- Every fact must reference a concept (by id). Create the concept if needed.
- Use snake_case for all IDs.
- Keep descriptions concise but specific.
- If the source doesn't contain a certain entity type, return an empty array.
- Respond with ONLY the JSON object. No markdown fences, no explanation.
"""


def ingest_text(
    text: str,
    source_name: str = "unknown",
    source_url: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Ingest unstructured text into ontology entities via LLM.

    Returns a dict with keys: evidence, concepts, facts, tasks.
    Each value is a list of dicts conforming to the entity schemas.
    """
    credential = get_credential()
    if credential is None:
        raise RuntimeError(
            "No Anthropic credential found. "
            "Set ANTHROPIC_API_KEY or authenticate via pi (oauth)."
        )

    user_prompt = (
        f"Extract ontology entities from the following document.\n\n"
        f"Source: {source_name}\n"
    )
    if source_url:
        user_prompt += f"URL: {source_url}\n"
    user_prompt += f"\n---\n\n{text}"

    headers = {
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
        **credential.auth_headers(),
    }

    body = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 4096,
        "system": credential.wrap_system_prompt(INGESTION_SYSTEM_PROMPT),
        "messages": [{"role": "user", "content": user_prompt}],
    }

    response = httpx.post(
        ANTHROPIC_API_URL,
        headers=headers,
        json=body,
        timeout=120,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Anthropic API error ({response.status_code}): {response.text}"
        )

    result = response.json()
    content = result["content"][0]["text"]

    # Parse JSON — handle markdown fences and truncated output
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1])

    try:
        entities = json.loads(content)
    except json.JSONDecodeError:
        # LLM may have been truncated — try to find the last complete entity
        # by finding the last valid JSON prefix
        # Try progressively shorter substrings ending at } or ]
        parsed = None
        for i in range(len(content), 0, -1):
            if content[i - 1] in ('}', ']'):
                # Try to close any open structures
                attempt = content[:i]
                # Count unclosed braces/brackets and close them
                opens = attempt.count('{') - attempt.count('}')
                opens_b = attempt.count('[') - attempt.count(']')
                attempt += ']' * opens_b + '}' * opens
                try:
                    parsed = json.loads(attempt)
                    break
                except json.JSONDecodeError:
                    continue
        if parsed is None:
            raise
        entities = parsed

    # Inject today's date into facts and evidence metadata
    today = date.today().isoformat()
    for fact in entities.get("facts", []):
        fact.setdefault("status", "active")
        fact.setdefault("effective_date", today)
        fact.setdefault("recorded_date", today)
        # Link evidence
        evidence_ids = [e["id"] for e in entities.get("evidence", [])]
        fact.setdefault("evidence", evidence_ids)

    for ev in entities.get("evidence", []):
        ev.setdefault("last_verified", today)
        if source_url and not ev.get("url"):
            ev["url"] = source_url

    return entities


def validate_ingested(entities: dict[str, list[dict]]) -> dict[str, list[str]]:
    """Validate ingested entities against Pydantic models.

    Returns a dict of entity_type → list of error messages.
    Empty dict means all valid.
    """
    from kanon.models.entities import Concept, Evidence, Fact, Task

    model_map = {
        "concepts": Concept,
        "facts": Fact,
        "tasks": Task,
        "evidence": Evidence,
    }

    errors: dict[str, list[str]] = {}

    for entity_type, model_class in model_map.items():
        items = entities.get(entity_type, [])
        for item in items:
            try:
                model_class(**item)
            except Exception as e:
                errors.setdefault(entity_type, []).append(
                    f"{item.get('id', '?')}: {e}"
                )

    return errors


def save_ingested(
    entities: dict[str, list[dict]],
    data_dir: str | Any,
) -> tuple[list[str], list[str]]:
    """Save ingested entities as YAML files in the data directory.

    Skips entities whose ID already exists (does not overwrite).

    Returns (written paths, skipped IDs).
    """
    from pathlib import Path
    import yaml

    data_path = Path(data_dir)
    written: list[str] = []
    skipped: list[str] = []

    type_to_dir = {
        "concepts": "concepts",
        "facts": "facts",
        "tasks": "tasks",
        "evidence": "evidence",
    }

    for entity_type, subdir in type_to_dir.items():
        items = entities.get(entity_type, [])
        entity_dir = data_path / subdir
        entity_dir.mkdir(exist_ok=True)
        for item in items:
            entity_id = item.get("id", "unknown")
            path = entity_dir / f"{entity_id}.yaml"
            if path.exists():
                skipped.append(f"{entity_type}/{entity_id}")
                continue
            path.write_text(yaml.dump(item, default_flow_style=False, sort_keys=False))
            written.append(str(path))

    return written, skipped
