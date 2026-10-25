#!/usr/bin/env python3
"""Validate a private film project's metadata, state schema, and lock invariants."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

if __package__ in (None, ""):
    import _bootstrap  # noqa: F401

from movie_workflow.io import verify_reference

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = REPOSITORY_ROOT / "schemas"

WORKFLOW = [
    "PROJECT_CREATED",
    "INDEX_VERIFIED",
    "DRAFT_READY",
    "DIRECTOR_SCRIPT_REVIEW",
    "SCRIPT_LOCKED",
    "VOICE_LOCKED",
    "NARRATION_LOCKED",
    "DIRECTOR_PROXY_PLAN_LOCKED",
    "DIRECTOR_PROXY_RENDERED",
    "USER_CREATIVE_REVIEW",
    "USER_SAMPLE_APPROVED",
    "DIRECTOR_PLAN_LOCKED",
    "FINAL_RENDERED",
    "SECOND_REVIEW",
    "SECOND_REVIEW_PASS",
    "FINAL_VERIFIED",
]

LOCK_GATES = {
    "index": ("INDEX_VERIFIED", "INDEX_VERIFIED"),
    "script": ("SCRIPT_LOCKED", "SCRIPT_LOCKED"),
    "voice": ("VOICE_LOCKED", "VOICE_LOCKED"),
    "narration": ("NARRATION_LOCKED", "NARRATION_LOCKED"),
    "director_plan": ("DIRECTOR_PLAN_LOCKED", "DIRECTOR_PLAN_LOCKED"),
    "final_render": ("FINAL_RENDERED", "FINAL_RENDERED"),
    "second_review": ("SECOND_REVIEW_PASS", "SECOND_REVIEW_PASS"),
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"missing file: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON in {path}: {error}") from error


def schema_errors(instance: dict[str, Any], schema_name: str) -> list[str]:
    schema = load_json(SCHEMA_ROOT / schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{schema_name}:{location}: {error.message}")
    return errors


def state_invariant_errors(
    project: dict[str, Any], state: dict[str, Any], project_root: Path
) -> list[str]:
    errors: list[str] = []
    if project.get("id") != state.get("film_id"):
        errors.append("project.id must match state.film_id")

    accepted_titles = {
        value
        for value in (
            project.get("title"),
            project.get("title_zh"),
            project.get("title_original"),
        )
        if value
    }
    if state.get("title") not in accepted_titles:
        errors.append("state.title must match one of the project's declared titles")

    workflow_control = state.get("workflow_control", {})
    if workflow_control.get("fixed_role_threads") is True:
        errors.append("fixed_role_threads must not be true in single-main-director mode")

    current_status = state.get("current_status")
    if current_status not in WORKFLOW:
        return errors
    current_index = WORKFLOW.index(current_status)
    locks = state.get("locks", {})

    for lock_name, (gate_status, expected_status) in LOCK_GATES.items():
        if current_index < WORKFLOW.index(gate_status):
            continue
        lock = locks.get(lock_name)
        if not isinstance(lock, dict):
            errors.append(f"locks.{lock_name} is required at {current_status}")
            continue
        if lock.get("status") != expected_status:
            errors.append(f"locks.{lock_name}.status must be {expected_status} at {current_status}")

    if current_status == "FINAL_VERIFIED":
        if state.get("next_legal_action") is not None:
            errors.append("FINAL_VERIFIED must not declare a next_legal_action")
    elif workflow_control.get("status") == "ACTIVE" and state.get("next_legal_action") is None:
        errors.append("an active, unfinished project must declare next_legal_action")

    canonical_project = state.get("canonical_project")
    if canonical_project:
        candidate = Path(canonical_project)
        if not candidate.is_absolute():
            candidate = project_root / candidate
        if candidate.resolve() != (project_root / "project.json").resolve():
            errors.append("state.canonical_project does not resolve to project.json")

    return errors


def artifact_errors(state: dict[str, Any], project_root: Path) -> list[str]:
    errors: list[str] = []
    for lock_name, lock in state.get("locks", {}).items():
        if not isinstance(lock, dict):
            continue
        try:
            verify_reference(project_root, lock)
        except (OSError, ValueError) as exc:
            errors.append(f"locks.{lock_name}: {exc}")
    return errors


def validate_project(project_root: Path, *, check_artifacts: bool = False) -> list[str]:
    project_root = project_root.expanduser().resolve()
    project_path = project_root / "project.json"
    try:
        project = load_json(project_path)
    except ValueError as error:
        return [str(error)]

    state_value = project.get("paths", {}).get("production_state", "production/state.json")
    state_path = Path(state_value)
    if not state_path.is_absolute():
        state_path = project_root / state_path
    try:
        state = load_json(state_path)
    except ValueError as error:
        return [str(error)]

    errors = []
    errors.extend(schema_errors(project, "project.schema.json"))
    errors.extend(schema_errors(state, "state.schema.json"))
    errors.extend(state_invariant_errors(project, state, project_root))
    if check_artifacts:
        errors.extend(artifact_errors(state, project_root))
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path, help="Directory containing project.json")
    parser.add_argument(
        "--check-artifacts",
        action="store_true",
        help="Also verify lock artifact/path targets and SHA-256 fingerprints",
    )
    parser.add_argument("--json", action="store_true", help="Print a machine-readable result")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    errors = validate_project(args.project_root, check_artifacts=args.check_artifacts)
    if args.json:
        print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    elif errors:
        print("Project validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
    else:
        print(f"Project validation passed: {args.project_root.resolve()}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
