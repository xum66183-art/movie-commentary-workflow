#!/usr/bin/env python3
"""Install or reversibly upgrade the eight bundled skills."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path

if __package__ in (None, ""):
    import _bootstrap  # noqa: F401

from movie_workflow.io import file_lock, write_json

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(path: Path) -> str:
    if path.is_symlink():
        return "link:" + os.readlink(path)
    digest = hashlib.sha256()
    for child in sorted(path.rglob("*")):
        if "__pycache__" in child.parts or child.suffix == ".pyc":
            continue
        digest.update(str(child.relative_to(path)).encode())
        if child.is_symlink():
            digest.update(os.readlink(child).encode())
        elif child.is_file():
            digest.update(child.read_bytes())
    return digest.hexdigest()


def remove_installed(path):
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def install(
    destination: Path,
    *,
    dry_run: bool = False,
    upgrade: bool = False,
    backup_directory: Path | None = None,
) -> list[str]:
    sources = sorted((ROOT / ".codex/skills").glob("movie-*"))
    destination = destination.expanduser().resolve()
    targets = [destination / p.name for p in sources]
    conflicts = [p.name for p in targets if p.exists() or p.is_symlink()]
    if conflicts and not upgrade:
        raise FileExistsError("Existing skills were preserved: " + ", ".join(conflicts))
    if dry_run:
        return [p.name for p in targets]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(destination.parent, ".movie-skills-install.lock"):
        # Recheck after acquiring the inter-process lock.
        conflicts = [p.name for p in targets if p.exists() or p.is_symlink()]
        if conflicts and not upgrade:
            raise FileExistsError("Existing skills were preserved: " + ", ".join(conflicts))
        backup = (
            backup_directory or destination.parent / "movie-skill-backups" / uuid.uuid4().hex
        ).resolve()
        if backup.is_relative_to(destination) or destination.is_relative_to(backup):
            raise ValueError("backup and destination must be separate directories")
        if backup.exists():
            raise FileExistsError("backup version already exists")
        stage = Path(tempfile.mkdtemp(prefix=".movie-skills-", dir=destination.parent))
        moved, installed = [], []
        try:
            for source in sources:
                shutil.copytree(
                    source,
                    stage / source.name,
                    ignore=lambda _, names: [
                        n
                        for n in names
                        if n in {"__pycache__", ".git"}
                        or n.endswith(".pyc")
                        or (n.startswith(".env") and n != ".env.example")
                    ],
                )
            destination.mkdir(parents=True, exist_ok=True)
            backup.mkdir(parents=True)
            for target in targets:
                if target.exists() or target.is_symlink():
                    target.rename(backup / target.name)
                    moved.append(target.name)
                (stage / target.name).rename(target)
                installed.append(target.name)
            write_json(
                backup / "receipt.json",
                {
                    "destination": str(destination),
                    "previous": moved,
                    "installed": {name: fingerprint(destination / name) for name in installed},
                },
            )
        except Exception:
            for name in installed:
                remove_installed(destination / name)
            for name in moved:
                (backup / name).rename(destination / name)
            raise
        finally:
            shutil.rmtree(stage)
        print("Rollback receipt: " + str(backup / "receipt.json"))
    return [p.name for p in targets]


def rollback(backup: Path, destination: Path):
    backup, destination = backup.resolve(), destination.expanduser().resolve()
    receipt = json.loads((backup / "receipt.json").read_text())
    if receipt["destination"] != str(destination):
        raise ValueError("rollback destination mismatch")
    known = {p.name for p in (ROOT / ".codex/skills").glob("movie-*")}
    if set(receipt["installed"]) != known or not set(receipt["previous"]) <= known:
        raise ValueError("invalid rollback receipt")
    with file_lock(destination.parent, ".movie-skills-install.lock"):
        for name, digest in receipt["installed"].items():
            if not (destination / name).exists() or fingerprint(destination / name) != digest:
                raise ValueError("installed skills changed; rollback would overwrite edits")
        if any(
            not ((backup / n).exists() or (backup / n).is_symlink()) for n in receipt["previous"]
        ):
            raise ValueError("backup is incomplete")
        for name in receipt["installed"]:
            remove_installed(destination / name)
        for name in receipt["previous"]:
            (backup / name).rename(destination / name)
        write_json(
            backup / "rollback.json", {"status": "ROLLED_BACK", "destination": str(destination)}
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--upgrade", action="store_true")
    mode.add_argument("--rollback", type=Path)
    parser.add_argument("--backup-directory", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        if args.rollback:
            if args.dry_run:
                parser.error("rollback preview is unsupported; inspect receipt.json")
            rollback(args.rollback, args.destination)
        else:
            for name in install(
                args.destination,
                dry_run=args.dry_run,
                upgrade=args.upgrade,
                backup_directory=args.backup_directory,
            ):
                print(("Would install " if args.dry_run else "Installed ") + name)
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
