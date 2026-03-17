# kanon/graph.py
"""KnowledgeGraph: loads all entity types and builds forward/reverse indexes."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from kanon.loader import load_entities_from_dir
from kanon.models.entities import (
    Asset,
    Audience,
    Capability,
    Concept,
    Constraint,
    Evidence,
    Fact,
    LearningObjective,
    Task,
)


@dataclass
class Edge:
    source_id: str
    relation: str
    target_id: str


# Maps entity type → (subdirectory name, list of relationship field names)
# For Fact.concept it's a str not a list — handled specially via "concept_single"
_ENTITY_CONFIG: list[tuple[type[BaseModel], str, list[str]]] = [
    (Concept,           "concepts",     ["supports", "prerequisites"]),
    (Capability,        "capabilities", ["enables"]),
    (Task,              "tasks",        ["targets"]),
    (Audience,          "audiences",    []),
    (LearningObjective, "objectives",   ["concepts", "tasks"]),
    (Fact,              "facts",        ["concept_single", "evidence", "superseded_by"]),
    (Evidence,          "evidence",     []),
    (Asset,             "assets",       ["teaches", "demonstrates", "supports_tasks",
                                         "targets", "references", "evidence_links",
                                         "constrained_by", "learning_objectives"]),
    (Constraint,        "constraints",  []),
]


class KnowledgeGraph:
    """Graph of Canon ontology entities with forward/reverse traversal."""

    def __init__(self, data_dir: Optional[Path] = None):
        self._entities: dict[str, BaseModel] = {}
        self._forward: dict[str, list[Edge]] = defaultdict(list)   # source_id → edges
        self._reverse: dict[str, list[Edge]] = defaultdict(list)   # target_id → edges

        if data_dir is not None:
            self._load(data_dir)
            self._build_indexes()

    # ------------------------------------------------------------------
    # Public load method (alternative to constructor-time loading)
    # ------------------------------------------------------------------

    def load(self, data_dir: Path) -> None:
        """Load entities from data_dir and rebuild indexes."""
        self._entities = {}
        self._forward = defaultdict(list)
        self._reverse = defaultdict(list)
        self._load(data_dir)
        self._build_indexes()

    @property
    def entities(self) -> dict[str, BaseModel]:
        """All loaded entities keyed by ID."""
        return self._entities

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load(self, data_dir: Path) -> None:
        for model, subdir, _ in _ENTITY_CONFIG:
            directory = data_dir / subdir
            for entity in load_entities_from_dir(directory, model):
                self._entities[entity.id] = entity  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Index building
    # ------------------------------------------------------------------

    def _build_indexes(self) -> None:
        for model, _, fields in _ENTITY_CONFIG:
            # Find all loaded entities of this type
            for entity in self._entities.values():
                if not isinstance(entity, model):
                    continue
                for field in fields:
                    if field == "concept_single":
                        # Fact.concept is a single str
                        value = getattr(entity, "concept", None)
                        if value:
                            self._add_edge(entity.id, "concept", value)  # type: ignore[attr-defined]
                    else:
                        targets = getattr(entity, field, None) or []
                        if isinstance(targets, str):
                            targets = [targets]
                        for target_id in targets:
                            if target_id:
                                self._add_edge(entity.id, field, target_id)  # type: ignore[attr-defined]

    def _add_edge(self, source_id: str, relation: str, target_id: str) -> None:
        edge = Edge(source_id=source_id, relation=relation, target_id=target_id)
        self._forward[source_id].append(edge)
        self._reverse[target_id].append(edge)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, entity_id: str) -> Optional[BaseModel]:
        """Return an entity by ID, or None if not found."""
        return self._entities.get(entity_id)

    def _collect_neighbors(
        self,
        index: dict[str, list[Edge]],
        entity_id: str,
        id_attr: str,
    ) -> list[BaseModel]:
        """Collect unique neighbor entities from an edge index.

        Args:
            index: Either ``_forward`` or ``_reverse`` edge index.
            entity_id: The starting entity ID to look up.
            id_attr: Edge attribute to read the neighbor ID from
                     (``"target_id"`` for forward, ``"source_id"`` for reverse).
        """
        result: list[BaseModel] = []
        seen: set[str] = set()
        for edge in index.get(entity_id, []):
            neighbor_id = getattr(edge, id_attr)
            if neighbor_id not in seen:
                entity = self._entities.get(neighbor_id)
                if entity is not None:
                    result.append(entity)
                    seen.add(neighbor_id)
        return result

    def dependencies(self, entity_id: str) -> list[BaseModel]:
        """Return entities that this entity points to (forward edges)."""
        return self._collect_neighbors(self._forward, entity_id, "target_id")

    def dependents(self, entity_id: str) -> list[BaseModel]:
        """Return entities that point to this entity (reverse edges)."""
        return self._collect_neighbors(self._reverse, entity_id, "source_id")

    def impact_of(self, entity_id: str) -> list[BaseModel]:
        """BFS over both forward AND reverse edges from entity_id.

        Returns all reachable entities (excluding the starting entity itself).
        """
        visited: set[str] = {entity_id}
        queue: deque[str] = deque([entity_id])
        result: list[BaseModel] = []

        while queue:
            current = queue.popleft()
            # Walk forward
            for edge in self._forward.get(current, []):
                if edge.target_id not in visited:
                    visited.add(edge.target_id)
                    queue.append(edge.target_id)
                    entity = self._entities.get(edge.target_id)
                    if entity is not None:
                        result.append(entity)
            # Walk reverse
            for edge in self._reverse.get(current, []):
                if edge.source_id not in visited:
                    visited.add(edge.source_id)
                    queue.append(edge.source_id)
                    entity = self._entities.get(edge.source_id)
                    if entity is not None:
                        result.append(entity)

        return result

    def subgraph(self, ids: list[str]) -> list[BaseModel]:
        """BFS over forward edges only from the given entity IDs.

        Returns all reachable entities including the starting entities.
        """
        visited: set[str] = set()
        queue: deque[str] = deque(ids)
        result: list[BaseModel] = []

        for entity_id in ids:
            if entity_id not in visited:
                visited.add(entity_id)
                entity = self._entities.get(entity_id)
                if entity is not None:
                    result.append(entity)

        while queue:
            current = queue.popleft()
            for edge in self._forward.get(current, []):
                if edge.target_id not in visited:
                    visited.add(edge.target_id)
                    queue.append(edge.target_id)
                    entity = self._entities.get(edge.target_id)
                    if entity is not None:
                        result.append(entity)

        return result
