from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_project import validate_project

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_synthetic_demo_is_valid() -> None:
    errors = validate_project(REPOSITORY_ROOT / "examples" / "synthetic-demo")
    assert errors == []


def test_script_lock_requires_index_and_script_locks(tmp_path: Path) -> None:
    project_root = tmp_path / "film"
    (project_root / "production").mkdir(parents=True)
    project = json.loads(
        (REPOSITORY_ROOT / "examples" / "synthetic-demo" / "project.json").read_text()
    )
    state = json.loads(
        (REPOSITORY_ROOT / "examples" / "synthetic-demo" / "production" / "state.json").read_text()
    )
    state["current_status"] = "SCRIPT_LOCKED"
    (project_root / "project.json").write_text(json.dumps(project), encoding="utf-8")
    (project_root / "production" / "state.json").write_text(json.dumps(state), encoding="utf-8")

    errors = validate_project(project_root)

    assert "locks.index is required at SCRIPT_LOCKED" in errors
    assert "locks.script is required at SCRIPT_LOCKED" in errors


def test_localized_project_title_is_supported(tmp_path: Path) -> None:
    project_root = tmp_path / "localized-film"
    (project_root / "production").mkdir(parents=True)
    project = json.loads(
        (REPOSITORY_ROOT / "examples" / "synthetic-demo" / "project.json").read_text()
    )
    state = json.loads(
        (REPOSITORY_ROOT / "examples" / "synthetic-demo" / "production" / "state.json").read_text()
    )
    project["title_zh"] = project.pop("title")
    (project_root / "project.json").write_text(json.dumps(project), encoding="utf-8")
    (project_root / "production" / "state.json").write_text(json.dumps(state), encoding="utf-8")

    assert validate_project(project_root) == []
