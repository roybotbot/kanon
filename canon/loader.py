# canon/loader.py
from pathlib import Path
from typing import TypeVar, Type
import yaml
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def load_entities_from_dir(directory: Path, model: Type[T]) -> list[T]:
    """Load all YAML files from a directory into Pydantic model instances."""
    entities = []
    if not directory.exists():
        return entities
    for path in sorted(directory.glob("*.yaml")):
        with open(path) as f:
            data = yaml.safe_load(f)
        if data:
            entities.append(model(**data))
    return entities
