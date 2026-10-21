#!/usr/bin/env python3
"""Install the eight bundled skills without overwriting existing installations."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def install(destination: Path, *, dry_run: bool = False) -> list[str]:
    sources = sorted((ROOT / ".codex/skills").glob("movie-*"))
    destination = destination.expanduser().resolve()
    targets = [destination / p.name for p in sources]
    conflicts = [p.name for p in targets if p.exists() or p.is_symlink()]
    if conflicts:
        raise FileExistsError("Existing skills were preserved: " + ", ".join(conflicts))
    if not dry_run:
        destination.mkdir(parents=True, exist_ok=True)
        for source, target in zip(sources, targets, strict=True):
            shutil.copytree(
                source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".env")
            )
    return [p.name for p in targets]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        for name in install(args.destination, dry_run=args.dry_run):
            print(("Would install " if args.dry_run else "Installed ") + name)
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
