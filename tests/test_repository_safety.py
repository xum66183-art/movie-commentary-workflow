from __future__ import annotations

from pathlib import Path

from scripts.check_repository import scan_repository


def test_clean_repository_fragment_passes(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("safe text\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("API_KEY=\n", encoding="utf-8")
    assert scan_repository(tmp_path) == []


def test_private_path_secret_and_media_are_rejected(tmp_path: Path) -> None:
    private_path = "/" + "Users" + "/privateperson/Movies/source.mp4"
    fake_secret = "sk-" + "1234567890abcdefghijklmnop"
    (tmp_path / "config.txt").write_text(
        f"source={private_path}\ntoken={fake_secret}\n",
        encoding="utf-8",
    )
    (tmp_path / "clip.mp4").write_bytes(b"not-real-media")

    violations = scan_repository(tmp_path)

    assert any("macOS user path" in item for item in violations)
    assert any("OpenAI-style secret" in item for item in violations)
    assert any("media/model/database" in item for item in violations)


def test_subtitles_and_github_tokens_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "captions.srt").write_text("private captions\n")
    (tmp_path / "config.txt").write_text("ghp_" + "a" * 36)
    violations = scan_repository(tmp_path)
    assert any("GitHub token" in item for item in violations)
    assert any("media/model/database" in item for item in violations)
