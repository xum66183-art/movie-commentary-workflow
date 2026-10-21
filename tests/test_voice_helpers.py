from __future__ import annotations

import importlib.util
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fish_reference_id_and_srt_helpers() -> None:
    module = load_module(
        "movie_voice_tts",
        REPOSITORY_ROOT
        / ".codex"
        / "skills"
        / "movie-voice-tts"
        / "scripts"
        / "movie_voice_tts.py",
    )
    reference_id = "ABCDEF0123456789ABCDEF0123456789"
    assert module.normalize_fish_reference_id(f"https://fish.audio/m/{reference_id}") == (
        reference_id.lower()
    )
    assert module.format_srt_time(3_723_004) == "01:02:03,004"


def test_volc_srt_helper() -> None:
    module = load_module(
        "volc_asr",
        REPOSITORY_ROOT / ".codex" / "skills" / "movie-voice-tts" / "scripts" / "volc_asr.py",
    )
    result = module.make_srt([{"start_time": 80, "end_time": 240, "text": "测试"}])
    assert "00:00:00,080 --> 00:00:00,240" in result
    assert result.endswith("测试\n")
