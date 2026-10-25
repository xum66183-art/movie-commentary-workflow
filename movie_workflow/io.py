"""Project-relative references, verified locks, atomic JSON and POSIX process locks."""

from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import contextmanager
from pathlib import Path

LOCK_STATUSES = {
    "index": "INDEX_VERIFIED",
    "script": "SCRIPT_LOCKED",
    "voice": "VOICE_LOCKED",
    "narration": "NARRATION_LOCKED",
    "director_plan": "DIRECTOR_PLAN_LOCKED",
    "final_render": "FINAL_RENDERED",
    "second_review": "SECOND_REVIEW_PASS",
    "proxy_plan": "DIRECTOR_PROXY_PLAN_LOCKED",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_path(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("missing artifact/path")
    root = Path(root).resolve()
    path = Path(value).expanduser()
    absolute = path.is_absolute()
    path = (path if absolute else root / path).resolve()
    if not absolute and not path.is_relative_to(root):
        raise ValueError("relative path escapes project")
    return path


def reference(root: Path, item: dict) -> Path:
    values = [resolve_path(root, item[k]) for k in ("artifact", "path") if item.get(k)]
    if not values:
        raise ValueError("missing artifact/path")
    if len(set(values)) != 1:
        raise ValueError("artifact/path conflict")
    return values[0]


def verify_reference(root: Path, item: dict, *, require_hash: bool = True) -> Path:
    path = reference(root, item)
    if not path.is_file():
        raise ValueError(f"missing file: {path}")
    expected = item.get("sha256")
    if (require_hash and not expected) or (expected and sha256(path) != expected):
        raise ValueError(f"sha256 missing or mismatch: {path.name}")
    return path


def checked_lock(root: Path, state: dict, name: str, *, confirmed: bool = False) -> Path:
    lock = state.get("locks", {}).get(name)
    if not isinstance(lock, dict):
        raise ValueError(f"missing lock: {name}")
    # Reject ambiguous aliases before opening either target.
    reference(root, lock)
    if lock.get("status") != LOCK_STATUSES[name]:
        raise ValueError(f"invalid lock status: {name}")
    if confirmed and lock.get("user_confirmed") is not True:
        raise ValueError(f"user confirmation missing: {name}")
    return verify_reference(root, lock)


def read_state(root: Path, *, active: bool = False) -> dict:
    root = Path(root).resolve()
    manifest = root / "project.json"
    project = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {}
    state_path = resolve_path(
        root, project.get("paths", {}).get("production_state", "production/state.json")
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if active and state.get("workflow_control", {}).get("status") == "PAUSED":
        raise ValueError("PAUSED: resume the project explicitly before execution")
    return state


def write_json(path: Path, value: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


@contextmanager
def file_lock(folder: Path, name: str = ".operation.lock"):
    import fcntl

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / name).open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("operation already running in another process") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)
