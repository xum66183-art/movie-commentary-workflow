#!/usr/bin/env python3
"""Build an offline, original synthetic index demo outside this public checkout."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
QUERY = "我穿过边界"
SUBTITLES = (
    "1\n00:00:00,000 --> 00:00:01,500\n红色方块起点\n\n"
    "2\n00:00:01,500 --> 00:00:02,500\n我穿过边界\n\n"
    "3\n00:00:02,500 --> 00:00:04,000\n蓝色方块停留\n\n"
    "4\n00:00:04,000 --> 00:00:06,000\n绿色方块终点\n"
)
EXPECTED_SHOTS = [(0, 2000, 0, 50), (2000, 4000, 50, 100), (4000, 6000, 100, 150)]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_output(path: Path) -> Path:
    """Reject existing targets, checkout output, and symlinked ancestors before writes."""
    path = path.expanduser()
    if not path.is_absolute():
        raise ValueError("--output must be an absolute path to a new directory")
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("--output must not use symlinks, including parent directories")
    resolved = path.resolve()
    if resolved.is_relative_to(REPOSITORY_ROOT.resolve()):
        raise ValueError("demo output must be outside the public repository")
    if resolved.exists():
        raise ValueError("output already exists; choose a new directory (nothing was overwritten)")
    return resolved


class Commands:
    """Keep actual subprocess receipts while replacing machine-specific path prefixes."""

    def __init__(self, output: Path):
        self.output = output
        self.entries: list[dict] = []

    def clean(self, value: str) -> str:
        replacements = {
            str(self.output): "<OUTPUT>",
            str(REPOSITORY_ROOT): "<REPOSITORY>",
            sys.executable: "python",
        }
        for old, new in sorted(replacements.items(), key=lambda item: -len(item[0])):
            value = value.replace(old, new)
        return value

    def run(self, command: list[str]) -> str:
        process = subprocess.run(command, capture_output=True, text=True, check=False)
        self.entries.append(
            {
                "argv": [self.clean(str(arg)) for arg in command],
                "returncode": process.returncode,
                "stdout": self.clean(process.stdout),
                "stderr": self.clean(process.stderr),
            }
        )
        if process.returncode:
            raise RuntimeError(
                f"{Path(command[0]).name} failed with exit code {process.returncode}: "
                + self.clean(process.stderr[-1500:])
            )
        return process.stdout

    def index(self, *arguments: str) -> str:
        return self.run(
            [sys.executable, str(REPOSITORY_ROOT / "scripts/movie_index.py"), *arguments]
        )

    def probe(self, path: Path) -> dict:
        return json.loads(
            self.run(
                [
                    "ffprobe", "-v", "error", "-show_format", "-show_streams",
                    "-of", "json", str(path),
                ]
            )
        )


def create_source(release: Path, commands: Commands) -> None:
    (release / "source.srt").write_text(SUBTITLES, encoding="utf-8")
    args = ["ffmpeg", "-v", "error", "-n"]
    for color, x in (("red", 90), ("blue", 270), ("green", 450)):
        args += [
            "-f", "lavfi", "-i",
            f"color={color}:s=640x360:r=25:d=2,"
            f"drawbox=x={x}:y=110:w=100:h=100:color=white:t=fill",
        ]
    args += [
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=6",
        "-i", str(release / "source.srt"),
        "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
        "-map", "[v]", "-map", "3:a", "-map", "4:s",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-c:s", "mov_text", "-metadata:s:s:0", "language=zho",
        "-movflags", "+faststart", str(release / "source.mp4"),
    ]
    commands.run(args)


def check_demo(project: Path, release: Path, commands: Commands) -> dict:
    """Check observable coordinates, retrieval, source audio, and adoption state."""
    analysis = read_json(project / "analysis/summary.json")
    verification = read_json(project / "analysis/verification.json")
    state = read_json(project / "production/state.json")
    with sqlite3.connect(project / "database/shots.sqlite") as db:
        shots = [json.loads(row[0]) for row in db.execute(
            "SELECT record_json FROM shots ORDER BY ordinal"
        )]
        linked = [row[0] for row in db.execute(
            "SELECT shot_id FROM shot_subtitles WHERE subtitle_id=2 ORDER BY shot_id"
        )]
    with sqlite3.connect(project / "database/vision.sqlite") as db:
        attempts = db.execute("SELECT count(*) FROM attempts").fetchone()[0]
        observations = db.execute("SELECT count(*) FROM observations").fetchone()[0]
    matches = json.loads(commands.index(
        "search", "--project", str(project), QUERY, "--limit", "5"
    ))
    evidence = read_json(project / "evidence/shot-000002-unit-001/pad-500/evidence.json")
    source_media = commands.probe(release / "source.mp4")
    evidence_media = commands.probe(project / evidence["clip"])
    evidence_duration = round(float(evidence_media["format"]["duration"]) * 1000)
    coordinates = [
        (s["start_ms"], s["end_ms"], s["start_frame"], s["end_frame"]) for s in shots
    ]
    checks = {
        "exact_shot_coordinates": coordinates == EXPECTED_SHOTS,
        "duration_6000_ms": analysis["duration_ms"] == 6000,
        "six_visual_units": analysis["visual_unit_count"] == 6,
        "cross_cut_subtitle_attached_to_both_shots": linked == ["shot-000001", "shot-000002"],
        "subtitle_search_returns_both_shots": {s["id"] for s in matches}
        == {"shot-000001", "shot-000002"},
        "source_has_audio": any(s["codec_type"] == "audio" for s in source_media["streams"]),
        "evidence_has_audio": any(
            s["codec_type"] == "audio" for s in evidence_media["streams"]
        ),
        "evidence_source_interval_1500_3500_ms": (
            evidence["source_start_ms"], evidence["source_end_ms"]
        ) == (1500, 3500),
        "evidence_duration_within_50_ms": abs(evidence_duration - 2000) <= 50,
        "three_evidence_frames": len(evidence["frames"]) == 3 and all(
            (project / frame["path"]).is_file() for frame in evidence["frames"]
        ),
        "structural_verification_passed": verification["structural_pass"]
        and not verification["errors"],
        "no_model_observations_or_api_attempts": observations == 0 and attempts == 0,
        "production_state_not_advanced": state["current_status"] == "PROJECT_CREATED"
        and state["locks"]["index"] is None and verification["index_verified"] is False,
    }
    if not all(checks.values()):
        raise ValueError("demo self-check failed: " + ", ".join(
            name for name, passed in checks.items() if not passed
        ))
    commands.run([
        "ffmpeg", "-v", "error", "-i", str(project / evidence["clip"]), "-f", "null", "-"
    ])
    shutil.copyfile(project / evidence["clip"], release / "evidence.mp4")
    return {
        "schema_version": 1,
        "kind": "offline synthetic integration demo; no API calls",
        "material_provenance": "Original generated color blocks, white squares, and a 440 Hz tone; "
        "Chinese captions written for this demo. No film footage or cloned voice.",
        "source": {
            "file": "source.mp4", "sha256": digest(release / "source.mp4"),
            "duration_ms": 6000, "width": 640, "height": 360, "fps": 25,
        },
        "index": {
            "shot_count": analysis["shot_count"],
            "visual_unit_count": analysis["visual_unit_count"],
            "subtitle_count": analysis["subtitle_count"],
            "shots": [{key: shot[key] for key in (
                "id", "start_ms", "end_ms", "start_frame", "end_frame", "subtitle_ids"
            )} for shot in shots],
        },
        "search": {
            "query": QUERY, "signal": "subtitle", "matching_shots": [s["id"] for s in matches],
            "cross_cut_subtitle_id": 2, "cross_cut_links": linked,
        },
        "evidence": {
            "file": "evidence.mp4", "sha256": digest(release / "evidence.mp4"),
            "target_id": evidence["target_id"], "source_start_ms": 1500,
            "source_end_ms": 3500, "measured_duration_ms": evidence_duration,
            "audio": "Preserved synthetic source tone; no narration",
        },
        "checks": checks,
        "workflow": {
            "current_status": state["current_status"], "index_lock": None,
            "index_verified": False, "manual_review_required": True,
            "api_attempts": attempts, "model_observations": observations,
        },
        "limitations": [
            "Tests a six-second fixture, not a real film or retrieval quality benchmark.",
            "No visual model inference, script writing, voice cloning, narration, "
            "or final commentary.",
            "Structural verification does not adopt an index or advance production state.",
            "Media bytes can vary across FFmpeg versions; coordinates and checks are reproducible.",
        ],
    }


def font(size: int):
    from PIL import ImageFont

    for candidate in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ):
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow 10.0 does not accept the size argument.
        return ImageFont.load_default()


def make_visuals(project: Path, release: Path, build: Path, summary: dict) -> list[Path]:
    from PIL import Image, ImageDraw

    background, ink, muted, accent = "#101827", "#f4f7fc", "#b0bfd3", "#58d6c8"

    def base(title: str, eyebrow: str):
        image = Image.new("RGB", (1280, 720), background)
        draw = ImageDraw.Draw(image)
        draw.text((64, 42), eyebrow, font=font(22), fill=accent)
        draw.text((64, 95), title, font=font(46), fill=ink)
        return image, draw

    def line(draw, y: int, text: str, size=29, fill=ink):
        draw.text((64, y), text, font=font(size), fill=fill)

    frames = [
        project / f"keyframes/shot-{n:06d}-unit-001-02.jpg" for n in range(1, 4)
    ]
    intro, draw = base(
        "From source to inspectable evidence", "MOVIE COMMENTARY WORKFLOW / OFFLINE DEMO"
    )
    line(draw, 200, "SOURCE  >  INDEX  >  SEARCH  >  EVIDENCE", 32)
    line(draw, 270, "6 seconds / 3 technical shots / Chinese subtitles", 28, muted)
    for n, path in enumerate(frames):
        with Image.open(path) as image:
            intro.paste(image.resize((352, 198)), (64 + n * 400, 340))
        draw.text(
            (64 + n * 400, 560), f"SHOT {n + 1:02d} / {n * 2}-{n * 2 + 2}s",
            font=font(24), fill=ink,
        )
    line(draw, 640, "Original geometric footage + synthetic tone. No API key needed.", 24, muted)

    results, draw = base("Search crosses the cut correctly", "ACTUAL CLI OUTPUT / SELF-CHECKED")
    line(draw, 200, "Subtitle #2 spans 1.500s to 2.500s.", 32)
    line(draw, 260, "Its text is linked to BOTH adjacent shots.", 29, muted)
    line(draw, 340, "shot-000001     0.000 - 2.000s     frames 0-50", 28)
    line(draw, 395, "shot-000002     2.000 - 4.000s     frames 50-100", 28)
    line(draw, 480, "Evidence: unit #2.1 + 500ms padding = 1.500 - 3.500s", 28, accent)
    line(draw, 545, "Next: the real exported 2-second clip, with source audio.", 25, muted)
    line(
        draw, 640,
        f"All {len(summary['checks'])} checks passed. Receipts: summary.json + transcript.json", 24,
    )

    boundary, draw = base(
        "A passing check is not creative approval", "HONEST SCOPE / PRODUCTION STATE"
    )
    line(draw, 210, "Structural verification: PASS", 34, accent)
    line(draw, 285, "Production state: PROJECT_CREATED", 32)
    line(draw, 350, "Index lock: null     INDEX_VERIFIED: false", 29)
    line(draw, 435, "0 API attempts / 0 visual model observations", 29, muted)
    line(draw, 505, "No script, cloned voice, narration, or final commentary.", 27, muted)
    line(draw, 605, "Human review and explicit adoption are still required.", 27)
    cards = []
    for name, image in (("intro", intro), ("results", results), ("boundary", boundary)):
        path = build / f"{name}.png"
        image.save(path)
        cards.append(path)
    preview = Image.new("RGB", (1280, 1440), background)
    preview.paste(intro, (0, 0))
    preview.paste(results, (0, 720))
    preview.save(release / "preview.png")
    return cards


def create_showcase(cards: list[Path], release: Path, commands: Commands) -> None:
    intro, results, boundary = cards
    command = [
        "ffmpeg", "-v", "error", "-n",
        "-loop", "1", "-t", "4", "-i", str(intro),
        "-i", str(release / "source.mp4"),
        "-loop", "1", "-t", "5", "-i", str(results),
        "-i", str(release / "evidence.mp4"),
        "-loop", "1", "-t", "5", "-i", str(boundary),
    ]
    filters = []
    for n in range(5):
        filters.append(
            f"[{n}:v]scale=1280:720:force_original_aspect_ratio=decrease,"
            f"pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=25,format=yuv420p,"
            f"setsar=1,setpts=PTS-STARTPTS[v{n}]"
        )
    for n, duration in ((0, 4), (2, 5), (4, 5)):
        filters.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={duration}[a{n}]")
    for n in (1, 3):
        filters.append(
            f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS[a{n}]"
        )
    filters.append("".join(f"[v{n}][a{n}]" for n in range(5)) + "concat=n=5:v=1:a=1[v][a]")
    command += [
        "-filter_complex", ";".join(filters), "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac",
        "-movflags", "+faststart", str(release / "demo.mp4"),
    ]
    commands.run(command)
    commands.run([
        "ffmpeg", "-v", "error", "-i", str(release / "demo.mp4"), "-f", "null", "-"
    ])
    media = commands.probe(release / "demo.mp4")
    if abs(float(media["format"]["duration"]) - 22) > 0.12:
        raise ValueError("showcase duration is not approximately 22 seconds")
    if not any(s["codec_type"] == "audio" for s in media["streams"]):
        raise ValueError("showcase is missing its audio stream")


def package_versions() -> dict[str, str]:
    versions = {name: importlib.metadata.version(name) for name in (
        "Pillow", "scenedetect", "jsonschema", "requests"
    )}
    for name in ("opencv-python-headless", "opencv-python"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    if not any(name.startswith("opencv-python") for name in versions):
        raise importlib.metadata.PackageNotFoundError("opencv-python-headless or opencv-python")
    return versions


def run_demo(output: Path) -> Path:
    output = validate_output(output)
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"{tool} is required on PATH; see docs/demo.md")
    versions = package_versions()
    output.mkdir(parents=True, exist_ok=False)
    release, project, build = output / "release", output / "project", output / "build"
    release.mkdir()
    build.mkdir()
    commands = Commands(output)
    create_source(release, commands)
    commands.index(
        "prepare", "--project", str(project), "--video", str(release / "source.mp4"),
        "--subtitle", str(release / "source.srt"), "--unit-seconds", "1",
        "--title", "Original synthetic demo", "--film-id", "synthetic-demo",
    )
    commands.index(
        "evidence", "--project", str(project), "shot-000002-unit-001", "--padding-ms", "500"
    )
    commands.index("verify", "--project", str(project))
    summary = check_demo(project, release, commands)
    cards = make_visuals(project, release, build, summary)
    create_showcase(cards, release, commands)
    summary["runtime"] = {
        "python": platform.python_version(), "os": platform.system(),
        "packages": versions,
        "ffmpeg": commands.run(["ffmpeg", "-version"]).splitlines()[0],
        "ffprobe": commands.run(["ffprobe", "-version"]).splitlines()[0],
    }
    # Version commands can include local build configuration paths; publish only the first line.
    for entry in commands.entries[-2:]:
        entry["stdout"] = entry["stdout"].splitlines()[0] + "\n"
    write_json(release / "summary.json", summary)
    write_json(release / "transcript.json", {
        "schema_version": 1,
        "path_placeholders": {
            "<OUTPUT>": "selected external output", "<REPOSITORY>": "source checkout"
        },
        "commands": commands.entries,
    })
    (release / "README.md").write_text(
        "# Offline synthetic demonstration\n\n"
        "Run `python scripts/run_demo.py --output /absolute/path/new-demo` from the checkout.\n\n"
        "Watch `demo.mp4` (22 seconds) or inspect `preview.png`. `source.mp4` contains original "
        "generated geometric footage, a synthetic tone, and a selectable Chinese subtitle track; "
        "`source.srt` is its sidecar. `evidence.mp4` is the actual 1.500–3.500 second export.\n\n"
        "`summary.json` records observable checks and versions. `transcript.json` records actual "
        "commands, exit codes, and outputs with machine path prefixes replaced. `SHA256SUMS` "
        "covers the files in this directory. Paths and timestamps in the private project are "
        "deliberately excluded. Publish only this release directory.\n\n"
        "This fixture does not demonstrate visual model inference, scripts, voice cloning, "
        "narration, real film retrieval quality, or a finished commentary. No API calls are made. "
        "Structural verification passes while production remains PROJECT_CREATED with no "
        "index lock. INDEX_VERIFIED remains false and human review is required.\n\n"
        "The synthetic media, captions, and artwork generated by this demo are offered under "
        "the project Apache License 2.0: https://www.apache.org/licenses/LICENSE-2.0 . "
        "See the source checkout LICENSE and NOTICE for repository attribution.\n",
        encoding="utf-8",
    )
    files = sorted(path for path in release.iterdir() if path.is_file())
    (release / "SHA256SUMS").write_text(
        "".join(f"{digest(path)}  {path.name}\n" for path in files), encoding="utf-8"
    )
    return release


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, required=True, help="new absolute directory outside checkout"
    )
    args = parser.parse_args(argv)
    try:
        release = run_demo(args.output)
    except (OSError, ValueError, RuntimeError, importlib.metadata.PackageNotFoundError) as exc:
        print(f"Demo failed: {exc}", file=sys.stderr)
        return 2
    print(f"Offline demo passed. Public artifacts: {release}")
    print("Production state: PROJECT_CREATED; INDEX_VERIFIED remains false.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
