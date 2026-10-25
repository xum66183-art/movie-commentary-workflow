"""The source release must run after extraction, with no access to this checkout."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def run(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        [sys.executable, *arguments], cwd=root, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def test_source_archive_contains_runnable_workflow(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    shutil.copytree(
        REPOSITORY_ROOT,
        checkout,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
            "*.egg-info",
            "build",
            "dist",
        ),
    )
    release = tmp_path / "release"
    run(checkout, "-m", "build", "--sdist", "--no-isolation", "--outdir", str(release))
    archives = list(release.glob("*.tar.gz"))
    assert len(archives) == 1

    extraction = tmp_path / "extracted"
    with tarfile.open(archives[0]) as archive:
        for member in archive.getmembers():
            target = extraction / member.name
            assert target.resolve().is_relative_to(extraction.resolve())
            assert not member.issym() and not member.islnk()
            if member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
    (root,) = extraction.iterdir()
    assert len(list((root / ".codex/skills").glob("*/SKILL.md"))) == 8
    for required in (
        "NOTICE",
        ".env.example",
        "scripts/macos/local_subtitle_ocr.swift",
        ".codex/skills/movie-voice-tts/.env.example",
        "templates/film-project/.gitignore",
        ".github/workflows/ci.yml",
        "tests/test_movie_index.py",
    ):
        assert (root / required).is_file(), required
    run(root, "scripts/check_repository.py")
    run(root, "scripts/validate_skills.py")
    run(root, "scripts/validate_project.py", "examples/synthetic-demo")
    run(root, "scripts/doctor.py", "--index")
    run(root, "scripts/movie_index.py", "--help")
    installed = run(root, "scripts/install_skills.py", "--destination", str(tmp_path / "skills"))
    assert installed.count("Installed movie-") == 8
