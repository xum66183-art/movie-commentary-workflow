"""Exercise Apple Vision OCR and offline MIDI rendering with generated fixtures."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    frames = root / "frames"
    frames.mkdir()
    scripts = Path(__file__).resolve().parent
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=white:s=320x180",
            "-frames:v",
            "1",
            str(frames / "000001.jpg"),
        ],
        check=True,
    )
    subprocess.run(
        [
            "swift",
            str(scripts / "local_subtitle_ocr.swift"),
            str(frames),
            str(root / "ocr.jsonl"),
            "0",
            "0.5",
        ],
        check=True,
    )
    rows = [json.loads(line) for line in (root / "ocr.jsonl").read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["time"] == 0
    score = {
        "duration": 2,
        "tracks": [{"name": "piano", "program": 0, "volume": 0.2, "pan": 0}],
        "notes": [{"track": 0, "start": 0, "duration": 1, "pitch": 60, "velocity": 40}],
    }
    (root / "score.json").write_text(json.dumps(score))
    subprocess.run(
        [
            "swift",
            str(scripts / "render_music_score.swift"),
            str(root / "score.json"),
            str(root / "music.wav"),
        ],
        check=True,
    )
    assert (root / "music.wav").stat().st_size > 1000
    print("macOS OCR and offline MIDI smoke checks passed")


if __name__ == "__main__":
    main()
