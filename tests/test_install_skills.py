import importlib.util
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


def test_installed_index_allows_private_projects_beside_skills(tmp_path: Path):
    destination = tmp_path / "user" / ".codex" / "skills"
    install(destination)
    skill = destination / "movie-index"
    spec = importlib.util.spec_from_file_location(
        "installed_movie_index", skill / "scripts" / "movie_index.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    private_project = tmp_path / "user" / "MovieCommentaryWorkflow" / "projects" / "film"
    assert module.project_root(private_project) == private_project.resolve()
    with pytest.raises(ValueError):
        module.project_root(skill / "private-project")
    with pytest.raises(ValueError):
        module.project_root(destination / "movie-direct" / "private-project")


def test_upgrade_restores_existing_symlink(tmp_path):
    from scripts.install_skills import rollback

    dest = tmp_path / "skills"
    dest.mkdir()
    old = tmp_path / "old-skill"
    old.mkdir()
    (old / "SKILL.md").write_text("old")
    link = dest / "movie-index"
    link.symlink_to(old, target_is_directory=True)
    backup = tmp_path / "backup"
    install(dest, upgrade=True, backup_directory=backup)
    assert not link.is_symlink()
    rollback(backup, dest)
    assert link.is_symlink() and (link / "SKILL.md").read_text() == "old"
    assert len(list(dest.iterdir())) == 1


def test_rollback_protects_local_changes(tmp_path):
    from scripts.install_skills import rollback

    dest, backup = tmp_path / "skills", tmp_path / "backup"
    install(dest, backup_directory=backup)
    (dest / "movie-index/SKILL.md").write_text("user edit")
    with pytest.raises(ValueError, match="overwrite edits"):
        rollback(backup, dest)
    assert (dest / "movie-index/SKILL.md").read_text() == "user edit"
