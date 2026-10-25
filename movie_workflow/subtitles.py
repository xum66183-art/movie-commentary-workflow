"""Strict SRT timing and conservative fixed-step OCR grouping."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def timestamp(value: str) -> int:
    match = re.fullmatch(r"(\d+):(\d{2}):(\d{2})[,.](\d{3})", value.strip())
    if not match or int(match[2]) >= 60 or int(match[3]) >= 60:
        raise ValueError("invalid subtitle timestamp")
    h, m, s, ms = map(int, match.groups())
    return ((h * 60 + m) * 60 + s) * 1000 + ms


def stamp(ms: int) -> str:
    seconds, millis = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def read_srt(path: Path, duration_ms: int) -> list[dict]:
    rows = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8-sig").strip()):
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].strip().isdigit() or " --> " not in lines[1]:
            raise ValueError("invalid SRT block")
        start, end = (timestamp(s) for s in lines[1].split(" --> "))
        if not 0 <= start < end <= duration_ms or (rows and start < rows[-1]["end_ms"]):
            raise ValueError("subtitle timing out of bounds or overlapping")
        rows.append({"start_ms": start, "end_ms": end, "text": "\n".join(lines[2:])})
    return rows


def make_srt(rows) -> str:
    return (
        "\n\n".join(
            f"{i}\n{stamp(r['start_ms'])} --> {stamp(r['end_ms'])}\n{r['text']}"
            for i, r in enumerate(rows, 1)
        )
        + "\n"
    )


def merge_ocr(records, threshold: float = 0.8):
    if not 0 <= threshold <= 1:
        raise ValueError("confidence threshold must be between zero and one")
    cues, review = [], []
    previous = -1
    for row in sorted(records, key=lambda r: r["time"]):
        start = round(row["time"] * 1000)
        end = start + round(row["step"] * 1000)
        if start <= previous or end <= start or start < 0:
            raise ValueError("invalid/duplicate fixed-step sampling times")
        previous = start
        observations = sorted(
            row.get("observations", []), key=lambda r: (-r["box"][1], r["box"][0])
        )
        picks = [o.get("candidates", [])[0] for o in observations if o.get("candidates")]
        if not picks:
            continue
        text = "\n".join(p["text"].strip() for p in picks).strip()
        if not text:
            continue
        score = min(p["confidence"] for p in picks)
        if score < threshold:
            review.append(
                {"frame": row["frame"], "time_ms": start, "text": text, "confidence": score}
            )
        if cues and cues[-1]["text"] == text and cues[-1]["end_ms"] == start:
            cues[-1]["end_ms"] = end
        else:
            cues.append({"start_ms": start, "end_ms": end, "text": text})
    return cues, review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--confidence", type=float, default=0.8)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(".review.json").exists():
        parser.error("output exists; use a new version")
    rows = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
    cues, review = merge_ocr(rows, args.confidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(make_srt(cues), encoding="utf-8")
    args.output.with_suffix(".review.json").write_text(
        json.dumps(
            {
                "timing": "fixed-step approximation; boundaries need review",
                "low_confidence": review,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
