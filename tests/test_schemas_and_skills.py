from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts.validate_skills import validate_skills

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_all_schemas_are_valid() -> None:
    for path in sorted((REPOSITORY_ROOT / "schemas").glob("*.schema.json")):
        Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


def test_all_skills_are_structurally_valid() -> None:
    assert validate_skills() == []
