import pytest

from movie_workflow.subtitles import make_srt, merge_ocr, read_srt


def row(at, text, confidence=0.9):
    return {
        "time": at,
        "step": 0.5,
        "frame": str(at),
        "observations": [
            {"box": [0, 0, 1, 1], "candidates": [{"text": text, "confidence": confidence}]}
        ],
    }


def test_merge_preserves_words_and_flags_uncertainty(tmp_path):
    cues, review = merge_ocr([row(0, "字幕"), row(0.5, "字幕"), row(1, "子幕", 0.3)])
    assert len(cues) == 2 and cues[0]["end_ms"] == 1000
    assert review[0]["text"] == "子幕"
    path = tmp_path / "captions.srt"
    path.write_text(make_srt(cues))
    assert read_srt(path, 1500) == cues


def test_missing_frames_do_not_extend_captions():
    cues, _ = merge_ocr([row(0, "same"), row(1, "same")])
    assert len(cues) == 2
    with pytest.raises(ValueError):
        merge_ocr([row(0, "a"), row(0, "b")])
