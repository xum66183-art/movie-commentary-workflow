from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VOICE_SCRIPTS = ROOT / ".codex/skills/movie-voice-tts/scripts"
spec = importlib.util.spec_from_file_location(
    "qwen_vc_audition", VOICE_SCRIPTS / "qwen_vc_audition.py"
)
audition = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audition)
sys.modules["qwen_vc_audition"] = audition
spec = importlib.util.spec_from_file_location(
    "qwen_vc_narration", VOICE_SCRIPTS / "qwen_vc_narration.py"
)
narration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(narration)


def test_unknown_submission_cannot_be_rebilled(tmp_path: Path, monkeypatch):
    folder = tmp_path / "part"
    folder.mkdir()
    row = {"id": 1, "text": "测试旁白", "text_sha256": "test-hash"}
    (folder / "metadata.json").write_text(
        json.dumps({**row, "voice_id": "test-voice", "status": "OUTCOME_UNKNOWN"})
    )

    def forbidden(*args, **kwargs):
        pytest.fail("An unresolved submission must never be sent again")

    monkeypatch.setattr(narration.requests, "post", forbidden)
    with pytest.raises(RuntimeError, match="未知结果"):
        narration.generate_part(folder, row, "test-voice", "fake-credential")


def test_narration_does_not_truncate_or_rewrite_long_paragraphs():
    with pytest.raises(ValueError):
        narration.make_plan("字" * 501)
    text = "第一段。\n\n第二段。"
    assert [part["text"] for part in narration.make_plan(text)] == text.split("\n\n")


def test_metadata_redacts_key_without_corrupting_empty_key(tmp_path: Path):
    output = tmp_path / "metadata.json"
    audition.save(output, {"text": "test"}, "")
    assert json.loads(output.read_text()) == {"text": "test"}
    audition.save(output, {"token": "fake-credential"}, "fake-credential")
    assert "fake-credential" not in output.read_text()
