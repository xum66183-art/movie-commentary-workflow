"""Safety and observable integration checks for the public offline demonstration."""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from scripts import run_demo as demo


def test_output_must_be_new_absolute_and_outside_checkout(tmp_path):
    with pytest.raises(ValueError, match="absolute"):
        demo.validate_output(Path("relative-demo"))
    with pytest.raises(ValueError, match="already exists"):
        demo.validate_output(tmp_path)
    with pytest.raises(ValueError, match="outside"):
        demo.validate_output(demo.REPOSITORY_ROOT / "uncreated-demo-output")
    existing = tmp_path / "existing"
    existing.mkdir()
    marker = existing / "keep.txt"
    marker.write_text("keep this")
    with pytest.raises(ValueError, match="already exists"):
        demo.run_demo(existing)
    assert marker.read_text() == "keep this"


def test_output_rejects_symlink_ancestors_in_both_directions(tmp_path, monkeypatch):
    repository = tmp_path / "checkout"
    repository.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    monkeypatch.setattr(demo, "REPOSITORY_ROOT", repository)
    (repository / "escape").symlink_to(external, target_is_directory=True)
    (external / "into-checkout").symlink_to(repository, target_is_directory=True)
    for target in (
        repository / "escape" / "new-demo",
        external / "into-checkout" / "new-demo",
    ):
        with pytest.raises(ValueError, match="symlinks"):
            demo.validate_output(target)
    assert sorted(path.name for path in external.iterdir()) == ["into-checkout"]
    assert sorted(path.name for path in repository.iterdir()) == ["escape"]


def test_missing_tool_fails_before_creating_output(tmp_path, monkeypatch):
    output = tmp_path / "never-created"
    monkeypatch.setattr(demo.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="required on PATH"):
        demo.run_demo(output)
    assert not output.exists()


def test_transcript_redacts_output_checkout_and_interpreter_prefixes(tmp_path):
    commands = demo.Commands(tmp_path / "demo")
    text = commands.clean(
        f"{commands.output}/release/source.mp4 {demo.REPOSITORY_ROOT}/scripts/movie_index.py "
        f"{demo.sys.executable}"
    )
    assert str(commands.output) not in text
    assert str(demo.REPOSITORY_ROOT) not in text
    assert demo.sys.executable not in text
    assert text == "<OUTPUT>/release/source.mp4 <REPOSITORY>/scripts/movie_index.py python"


def has_integration_dependencies():
    return all(shutil.which(name) for name in ("ffmpeg", "ffprobe")) and all(
        importlib.util.find_spec(name) for name in ("PIL", "cv2", "scenedetect")
    )


@pytest.mark.skipif(not has_integration_dependencies(), reason="requires .[index] and FFmpeg")
def test_demo_runs_real_cli_and_publishes_only_synthetic_receipts(tmp_path):
    output = tmp_path / "offline-demo"
    release = demo.run_demo(output)
    summary = json.loads((release / "summary.json").read_text())
    transcript_text = (release / "transcript.json").read_text()
    transcript = json.loads(transcript_text)
    assert all(summary["checks"].values())
    assert summary["index"]["shot_count"] == 3
    assert summary["index"]["visual_unit_count"] == 6
    assert summary["search"]["query"] == "我穿过边界"
    assert summary["workflow"] == {
        "current_status": "PROJECT_CREATED", "index_lock": None,
        "index_verified": False, "manual_review_required": True,
        "api_attempts": 0, "model_observations": 0,
    }
    actual_index_commands = [
        entry["argv"][2] for entry in transcript["commands"]
        if len(entry["argv"]) > 2 and entry["argv"][1].endswith("scripts/movie_index.py")
    ]
    assert set(actual_index_commands) == {"prepare", "search", "evidence", "verify"}
    assert all(entry["returncode"] == 0 for entry in transcript["commands"])
    assert str(output) not in transcript_text
    assert str(demo.REPOSITORY_ROOT) not in transcript_text
    assert set(path.name for path in release.iterdir()) == {
        "source.mp4", "source.srt", "evidence.mp4", "demo.mp4", "preview.png",
        "summary.json", "transcript.json", "README.md", "SHA256SUMS",
    }
    for name in ("summary.json", "transcript.json", "README.md"):
        public_text = (release / name).read_text()
        assert str(output) not in public_text
        assert str(Path.home()) not in public_text
    checksum_lines = (release / "SHA256SUMS").read_text().splitlines()
    assert len(checksum_lines) == 8
    for row in checksum_lines:
        checksum, filename = row.split("  ", 1)
        assert demo.digest(release / filename) == checksum
    assert (output / "project/database/shots.sqlite").is_file()
    assert (output / "project/production/state.json").is_file()
    # The fixture exercises the real public API without introducing vision/API mock results.
    assert not list(release.rglob("*.sqlite"))


@pytest.mark.parametrize("distribution", ["opencv-python-headless", "opencv-python"])
def test_runtime_records_actual_opencv_distribution(monkeypatch, distribution):
    required = {"Pillow": "12.0", "scenedetect": "0.6.7.1", "jsonschema": "4.0", "requests": "2.0"}
    installed = {**required, distribution: "4.11.0.86"}

    def version(name):
        if name not in installed:
            raise demo.importlib.metadata.PackageNotFoundError(name)
        return installed[name]

    monkeypatch.setattr(demo.importlib.metadata, "version", version)
    assert demo.package_versions() == installed
