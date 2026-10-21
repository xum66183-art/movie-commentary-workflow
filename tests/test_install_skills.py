from pathlib import Path

import pytest

from scripts.install_skills import install


def test_preview_and_install_all_skills(tmp_path: Path):
    destination = tmp_path / "skills"
    names = install(destination, dry_run=True)
    assert len(names) == 8 and not destination.exists()
    assert install(destination) == names
    assert all((destination / name / "SKILL.md").is_file() for name in names)
    assert not list(destination.rglob("__pycache__"))


def test_existing_symlink_prevents_partial_install(tmp_path: Path):
    destination = tmp_path / "skills"
    destination.mkdir()
    link = destination / "movie-index"
    link.symlink_to(tmp_path / "absent", target_is_directory=True)
    with pytest.raises(FileExistsError):
        install(destination)
    assert list(destination.iterdir()) == [link]
    assert link.is_symlink()
