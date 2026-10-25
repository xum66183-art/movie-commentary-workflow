"""Generate a reproducible private demo with color bars and a labelled mock voice tone."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import struct
import wave
from pathlib import Path

from .io import sha256, write_json
from .render import render


def build(project: Path, *, repository: Path | None = None, font: Path | None = None):
    project = Path(project).resolve()
    repository = repository or Path(__file__).resolve().parents[1]
    if project.exists():
        raise ValueError("demo directory exists; choose a new directory")
    if project.is_relative_to(repository.resolve()):
        raise ValueError("demo must be outside public repository")
    project.mkdir(parents=True)
    media = project / "media"
    media.mkdir()
    source = media / "source.mp4"
    generator_spec = importlib.util.spec_from_file_location(
        "source_demo", repository / "scripts/run_demo.py"
    )
    generator = importlib.util.module_from_spec(generator_spec)
    generator_spec.loader.exec_module(generator)
    generator.create_source(media, generator.Commands(project))
    narration = media / "mock-narration.wav"
    with wave.open(str(narration), "wb") as stream:
        stream.setparams((1, 2, 24000, 0, "NONE", "none"))
        stream.writeframes(
            b"".join(
                struct.pack("<h", round(1200 * math.sin(2 * math.pi * 440 * i / 24000)))
                for i in range(6 * 24000)
            )
        )
    subtitles = media / "captions.srt"
    subtitles.write_text(
        "1\n00:00:00,000 --> 00:00:03,000\nSynthetic scene A\n\n"
        "2\n00:00:03,000 --> 00:00:06,000\nSynthetic scene B\n",
        encoding="utf-8",
    )
    index_script = repository / ".codex/skills/movie-index/scripts/movie_index.py"
    spec = importlib.util.spec_from_file_location("synthetic_index", index_script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    indexed = project / "index"
    if module.main(
        ["prepare", "--project", str(indexed), "--video", str(source), "--subtitle", str(subtitles)]
    ) != 0 or module.verify(indexed):
        raise ValueError("synthetic index failed")
    state = {
        "schema_version": 1,
        "film_id": "synthetic-runtime-001",
        "title": "Synthetic runtime demo",
        "current_status": "PROJECT_CREATED",
        "synthetic_fixture": True,
        "user_sample_approved": False,
        "workflow_control": {
            "status": "ACTIVE",
            "execution_mode": "SINGLE_MAIN_DIRECTOR",
            "master_skill": "movie-master-director",
        },
        "locks": {
            name: None
            for name in (
                "index",
                "script",
                "voice",
                "narration",
                "director_plan",
                "final_render",
                "second_review",
            )
        },
        "next_legal_action": {
            "responsible_skill": "movie-direct",
            "action": "Review the synthetic proxy; no real creative adoption is recorded.",
        },
    }
    metadata = json.loads((indexed / "project.json").read_text())
    metadata.update(id=state["film_id"], title=state["title"])
    metadata["source"]["video"]["path"] = str(source)
    metadata["paths"]["production_state"] = "production/state.json"
    write_json(project / "project.json", metadata)
    visual = {
        "schema_version": 1,
        "film_id": state["film_id"],
        "duration_ms": 6000,
        "source": "media/source.mp4",
        "source_sha256": sha256(source),
        "narration": "media/mock-narration.wav",
        "narration_sha256": sha256(narration),
        "output": {
            "width": 320,
            "height": 180,
            "fps": 25,
            "subtitle_mode": "burn" if font else "sidecar",
        },
        "clips": [
            {
                "id": f"scene-{i}",
                "timeline_start_ms": i * 3000,
                "timeline_end_ms": (i + 1) * 3000,
                "source_start_ms": i * 3000,
                "source_end_ms": (i + 1) * 3000,
                "pace": "normal",
                "purpose": "synthetic fixture",
                "source_audio": False,
            }
            for i in range(2)
        ],
    }
    audio = {
        "schema_version": 1,
        "film_id": state["film_id"],
        "duration_ms": 6000,
        "events": [
            {
                "id": "mock-voice",
                "type": "narration",
                "start_ms": 0,
                "end_ms": 6000,
                "source": "media/mock-narration.wav",
                "source_sha256": sha256(narration),
                "gain_db": -3,
                "purpose": "test tone, not synthesized speech",
            }
        ],
    }
    write_json(project / "director/visual_edit.json", visual)
    write_json(project / "director/audio_mix_plan.json", audio)
    bundle = {
        "status": "DIRECTOR_PROXY_PLAN_LOCKED",
        "synthetic_fixture": True,
        "visual_edit": {
            "path": "director/visual_edit.json",
            "sha256": sha256(project / "director/visual_edit.json"),
        },
        "audio_mix_plan": {
            "path": "director/audio_mix_plan.json",
            "sha256": sha256(project / "director/audio_mix_plan.json"),
        },
        "subtitles": {"path": "media/captions.srt", "sha256": sha256(subtitles)},
    }
    if font:
        visual["output"].update(font_family="DejaVu Sans", font_size=20, margin_v=12)
        write_json(project / "director/visual_edit.json", visual)
        bundle["visual_edit"]["sha256"] = sha256(project / "director/visual_edit.json")
        bundle["font"] = {"path": str(font.resolve()), "sha256": sha256(font)}
    write_json(project / "director/bundle.json", bundle)
    state["locks"]["proxy_plan"] = {
        "status": "DIRECTOR_PROXY_PLAN_LOCKED",
        "artifact": "director/bundle.json",
        "sha256": sha256(project / "director/bundle.json"),
        "synthetic_fixture": True,
    }
    state["locks"]["narration"] = {
        "status": "NARRATION_LOCKED",
        "artifact": "media/mock-narration.wav",
        "sha256": sha256(narration),
        "synthetic_fixture": True,
    }
    write_json(project / "production/state.json", state)
    before = sha256(project / "production/state.json")
    first = render(project, project / "render/proxy-v001")
    second = render(project, project / "render/proxy-v002")
    if before != sha256(project / "production/state.json") or second["segments_reused"] != 2:
        raise ValueError("demo changed formal state or failed cache reuse")
    report = {
        "index_structural_pass": True,
        "real_api_calls": 0,
        "mock_narration": "local sine tone; no voice quality claim",
        "technical_pass": first["qa"]["full_decode"],
        "cached_segments_second_version": 2,
        "user_adopted": False,
        "formal_verified": False,
        "video": str(project / "render/proxy-v001/proxy.mp4"),
    }
    write_json(project / "DEMO_REPORT.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--repository", type=Path)
    parser.add_argument("--font", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.project, repository=args.repository, font=args.font), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
