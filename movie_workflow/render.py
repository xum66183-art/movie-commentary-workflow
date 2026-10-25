"""Execute verified cut-only plans; technical QA never adopts a creative version."""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

from .io import (
    checked_lock,
    file_lock,
    read_state,
    resolve_path,
    sha256,
    verify_reference,
    write_json,
)
from .subtitles import read_srt


def run(command, *, cwd=None):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f"{command[0]} failed: {result.stderr[-1800:]}")
    return result


def probe(path):
    return json.loads(
        run(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]
        ).stdout
    )


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"invalid integer: {name}")
    return value


def check_keys(item, allowed):
    unknown = set(item) - set(allowed)
    if unknown:
        raise ValueError(f"unsupported plan fields: {sorted(unknown)}")


def load_plan(project, mode):
    project = Path(project).resolve()
    checkout = Path(__file__).resolve().parents[1]
    if (checkout / "pyproject.toml").exists() and project.is_relative_to(checkout):
        raise ValueError("private output must be outside public checkout")
    state = read_state(project, active=True)
    name = "director_plan" if mode == "final" else "proxy_plan"
    lock = checked_lock(project, state, name, confirmed=mode == "final")
    if mode == "final" and state.get("user_sample_approved") is not True:
        raise ValueError("final render requires explicit user_sample_approved")
    bundle = json.loads(lock.read_text(encoding="utf-8"))
    visual_path = verify_reference(project, bundle["visual_edit"])
    audio_path = verify_reference(project, bundle["audio_mix_plan"])
    visual = json.loads(visual_path.read_text(encoding="utf-8"))
    audio = json.loads(audio_path.read_text(encoding="utf-8"))
    check_keys(
        visual,
        {
            "schema_version",
            "film_id",
            "duration_ms",
            "source",
            "source_sha256",
            "narration",
            "narration_sha256",
            "clips",
            "output",
        },
    )
    check_keys(audio, {"schema_version", "film_id", "duration_ms", "events"})
    if visual.get("schema_version") != 1 or audio.get("schema_version") != 1:
        raise ValueError("unsupported plan schema version")
    if not (visual.get("film_id") == audio.get("film_id") == state.get("film_id")):
        raise ValueError("film identity mismatch")
    duration = integer(visual["duration_ms"], "duration_ms", 1000)
    if audio["duration_ms"] != duration:
        raise ValueError("picture/audio duration mismatch")
    output = visual["output"]
    check_keys(
        output, {"width", "height", "fps", "subtitle_mode", "font_family", "font_size", "margin_v"}
    )
    width, height = (integer(output[k], k, 2) for k in ("width", "height"))
    if width % 2 or height % 2 or max(width, height) > 8192:
        raise ValueError("H.264 dimensions must be even and at most 8192")
    fps = Fraction(str(output["fps"]))
    if not 1 <= fps <= 120:
        raise ValueError("invalid fps")
    subtitle_mode = output.get("subtitle_mode", "none")
    if subtitle_mode not in {"none", "sidecar", "burn"}:
        raise ValueError("unsupported subtitle_mode")
    source = verify_reference(
        project, {"path": visual["source"], "sha256": visual["source_sha256"]}
    )
    narration = verify_reference(
        project, {"path": visual["narration"], "sha256": visual["narration_sha256"]}
    )
    locked_narration = checked_lock(project, state, "narration")
    if locked_narration.suffix == ".json":
        metadata = json.loads(locked_narration.read_text(encoding="utf-8"))
        locked_narration = verify_reference(
            project, {"path": metadata["output_audio"], "sha256": metadata["output_sha256"]}
        )
    if locked_narration != narration:
        raise ValueError("narration does not match adopted lock")
    source_probe = probe(source)
    if not any(s["codec_type"] == "video" for s in source_probe["streams"]):
        raise ValueError("picture source has no video stream")
    source_duration = float(source_probe["format"]["duration"]) * 1000
    clips = visual["clips"]
    if not clips:
        raise ValueError("empty picture timeline")
    cursor, ids = 0, set()
    for clip in clips:
        check_keys(
            clip,
            {
                "id",
                "timeline_start_ms",
                "timeline_end_ms",
                "source_start_ms",
                "source_end_ms",
                "pace",
                "purpose",
                "source_audio",
            },
        )
        for key in ("timeline_start_ms", "timeline_end_ms", "source_start_ms", "source_end_ms"):
            integer(clip[key], key)
        if clip["id"] in ids:
            raise ValueError("duplicate clip id")
        ids.add(clip["id"])
        length = clip["timeline_end_ms"] - clip["timeline_start_ms"]
        if clip["timeline_start_ms"] != cursor or length < 1000:
            raise ValueError("picture gap/overlap or new clip shorter than one second")
        if clip["source_end_ms"] - clip["source_start_ms"] != length:
            raise ValueError("retiming is unsupported; source and timeline lengths must match")
        if clip["source_end_ms"] > source_duration + 1:
            raise ValueError("source video interval out of bounds")
        if (Fraction(length, 1000) * fps).denominator != 1:
            raise ValueError("clip boundary must fall on an output frame")
        if type(clip.get("source_audio", False)) is not bool:
            raise ValueError("source_audio must be boolean")
        cursor = clip["timeline_end_ms"]
    if cursor != duration:
        raise ValueError("picture coverage does not match duration")
    events = []
    probes = {str(source): source_probe, str(narration): probe(narration)}
    event_ids = set()
    for event in audio["events"]:
        check_keys(
            event,
            {
                "id",
                "type",
                "start_ms",
                "end_ms",
                "source",
                "source_sha256",
                "source_start_ms",
                "gain_db",
                "purpose",
            },
        )
        if event["id"] in event_ids:
            raise ValueError("duplicate audio event id")
        event_ids.add(event["id"])
        start, end = (integer(event[k], k) for k in ("start_ms", "end_ms"))
        if not 0 <= start < end <= duration:
            raise ValueError("audio event interval out of bounds")
        kind = event["type"]
        if kind not in {"narration", "source_dialogue", "ambience", "music", "silence"}:
            raise ValueError("unsupported audio event type")
        item = dict(event)
        if kind == "silence":
            if event.get("source"):
                raise ValueError("silence may not contain a source")
        else:
            item["file"] = str(
                verify_reference(
                    project, {"path": event["source"], "sha256": event["source_sha256"]}
                )
            )
            offset = integer(event.get("source_start_ms", 0), "source_start_ms")
            gain = event.get("gain_db", 0)
            if type(gain) not in (int, float) or not math.isfinite(gain):
                raise ValueError("invalid audio gain")
            media = probes.setdefault(item["file"], None)
            if media is None:
                media = probes[item["file"]] = probe(item["file"])
            if not any(s["codec_type"] == "audio" for s in media["streams"]):
                raise ValueError("audio event source has no audio")
            if offset + end - start > float(media["format"]["duration"]) * 1000 + 1:
                raise ValueError("audio source interval out of bounds")
            if kind == "narration" and item["file"] != str(narration):
                raise ValueError("narration identity mismatch")
            if kind == "source_dialogue":
                matches = [
                    c
                    for c in clips
                    if c.get("source_audio")
                    and c["timeline_start_ms"] <= start < end <= c["timeline_end_ms"]
                    and offset == c["source_start_ms"] + start - c["timeline_start_ms"]
                ]
                if item["file"] != str(source) or not matches:
                    raise ValueError("source dialogue must be explicitly enabled and synchronized")
        events.append(item)
    for i, event in enumerate(events):
        for other in events[i + 1 :]:
            overlap = max(event["start_ms"], other["start_ms"]) < min(
                event["end_ms"], other["end_ms"]
            )
            if overlap and event["type"] == other["type"] in {"narration", "source_dialogue"}:
                raise ValueError("voice events overlap")
            if overlap and (
                "silence" in {event["type"], other["type"]}
                or {event["type"], other["type"]} == {"narration", "source_dialogue"}
            ):
                raise ValueError("silence or source takeover overlaps another voice/event")
    for clip in clips:
        if clip.get("source_audio"):
            covered = sum(
                e["end_ms"] - e["start_ms"]
                for e in events
                if e["type"] == "source_dialogue"
                and clip["timeline_start_ms"]
                <= e["start_ms"]
                < e["end_ms"]
                <= clip["timeline_end_ms"]
            )
            if covered != clip["timeline_end_ms"] - clip["timeline_start_ms"]:
                raise ValueError("source_audio clip requires complete explicit dialogue coverage")
    subtitles = font = None
    if subtitle_mode != "none":
        subtitles = verify_reference(project, bundle["subtitles"])
        read_srt(subtitles, duration)
        if subtitle_mode == "burn":
            font = verify_reference(project, bundle["font"])
            family = output.get("font_family", "")
            if not re.fullmatch(r"[A-Za-z0-9 _-]{1,80}", family):
                raise ValueError("burn mode needs an explicit safe font_family")
            integer(output.get("font_size", 22), "font_size", 1)
            integer(output.get("margin_v", 16), "margin_v")
    elif bundle.get("subtitles"):
        raise ValueError("locked subtitles require burn or sidecar mode")
    identity = {
        "bundle": sha256(lock),
        "visual": sha256(visual_path),
        "audio": sha256(audio_path),
        "source": visual["source_sha256"],
        "narration": visual["narration_sha256"],
        "subtitles": sha256(subtitles) if subtitles else None,
        "font": sha256(font) if font else None,
        "mode": mode,
        "ffmpeg": run(["ffmpeg", "-version"]).stdout.splitlines()[0],
        "renderer": 1,
    }
    return {
        "visual": visual,
        "events": events,
        "source": source,
        "subtitles": subtitles,
        "font": font,
        "identity": identity,
        "fps": fps,
    }


def technical_qa(path, plan):
    media = probe(path)
    streams = media["streams"]
    video = next(s for s in streams if s["codec_type"] == "video")
    audio = next(s for s in streams if s["codec_type"] == "audio")
    output = plan["visual"]["output"]
    duration = plan["visual"]["duration_ms"] / 1000
    if (
        video["width"] != output["width"]
        or video["height"] != output["height"]
        or Fraction(video["avg_frame_rate"]) != plan["fps"]
    ):
        raise ValueError("rendered video profile mismatch")
    if abs(float(media["format"]["duration"]) - duration) > max(0.06, 1 / float(plan["fps"])):
        raise ValueError("rendered duration mismatch")
    if audio["channels"] != 2 or int(audio["sample_rate"]) != 48000:
        raise ValueError("rendered audio profile mismatch")
    run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"])
    return {
        "full_decode": True,
        "duration_seconds": float(media["format"]["duration"]),
        "video_codec": video["codec_name"],
        "audio_codec": audio["codec_name"],
        "creative_review_complete": False,
        "formal_verified": False,
    }


def render(project: Path, output: Path, *, mode="proxy"):
    project = Path(project).resolve()
    output = Path(output).resolve()
    if not output.is_relative_to(project) or output == project:
        raise ValueError("render output must be a new directory within the private project")
    with file_lock(project, ".render.lock"):
        plan = load_plan(project, mode)
        output.mkdir(parents=True, exist_ok=True)
        manifest_path = output / "render-manifest.json"
        if manifest_path.exists():
            saved = json.loads(manifest_path.read_text())
            if saved["identity"] != plan["identity"]:
                raise ValueError("output version inputs changed; select a new directory")
            if saved.get("status") == "READY":
                for item in saved["outputs"]:
                    verify_reference(project, item)
                return saved
        elif any(output.iterdir()):
            raise ValueError("output directory is not empty")
        write_json(manifest_path, {"identity": plan["identity"], "status": "PREPARED"})
        visual = plan["visual"]
        spec = visual["output"]
        cache = resolve_path(project, ".render-cache")
        cache.mkdir(exist_ok=True)
        segment_names = []
        reused = 0
        for clip in visual["clips"]:
            import hashlib

            key = hashlib.sha256(
                json.dumps(
                    {
                        "source": visual["source_sha256"],
                        "clip": clip,
                        "output": spec,
                        "ffmpeg": plan["identity"]["ffmpeg"],
                        "renderer": 1,
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            segment = cache / f"{key}.mp4"
            receipt = segment.with_suffix(".json")
            if (
                segment.exists()
                and receipt.exists()
                and sha256(segment) == json.loads(receipt.read_text())["sha256"]
            ):
                reused += 1
            else:
                temp = cache / f"{key}.partial.mp4"
                length = (clip["timeline_end_ms"] - clip["timeline_start_ms"]) / 1000
                vf = (
                    f"fps={plan['fps']},scale={spec['width']}:{spec['height']}:"
                    "force_original_aspect_ratio=decrease,"
                    f"pad={spec['width']}:{spec['height']}:(ow-iw)/2:(oh-ih)/2,setsar=1"
                )
                run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-y",
                        "-ss",
                        str(clip["source_start_ms"] / 1000),
                        "-i",
                        str(plan["source"]),
                        "-t",
                        str(length),
                        "-an",
                        "-map",
                        "0:v:0",
                        "-vf",
                        vf,
                        "-c:v",
                        "libx264",
                        "-preset",
                        "fast",
                        "-crf",
                        "18",
                        "-pix_fmt",
                        "yuv420p",
                        str(temp),
                    ]
                )
                temp.replace(segment)
                write_json(receipt, {"sha256": sha256(segment)})
            name = f"segment-{len(segment_names):05d}.mp4"
            shutil.copy2(segment, output / name)
            segment_names.append(name)
        (output / "concat.txt").write_text(
            "\n".join(f"file '{name}'" for name in segment_names) + "\n"
        )
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "1",
                "-i",
                "concat.txt",
                "-c:v",
                "copy",
                "-an",
                "picture-lock.mp4",
            ],
            cwd=output,
        )
        duration = visual["duration_ms"] / 1000
        command = ["ffmpeg", "-v", "error", "-y"]
        filters, labels = [], []
        sources = [e for e in plan["events"] if e["type"] != "silence"]
        if not sources:
            command += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            filters = [f"[0:a]atrim=duration={duration}[mix]"]
        else:
            for i, event in enumerate(sources):
                command += ["-i", event["file"]]
                start = event.get("source_start_ms", 0) / 1000
                length = (event["end_ms"] - event["start_ms"]) / 1000
                filters.append(
                    f"[{i}:a:0]atrim=start={start}:duration={length},asetpts=PTS-STARTPTS,"
                    "aresample=48000,aformat=channel_layouts=stereo,"
                    f"volume={event.get('gain_db', 0)}dB,"
                    f"adelay={event['start_ms']}|{event['start_ms']}[a{i}]"
                )
                labels.append(f"[a{i}]")
            filters.append(
                "".join(labels) + f"amix=inputs={len(labels)}:normalize=0:dropout_transition=0,"
                f"apad,atrim=duration={duration}[mix]"
            )
        run(
            command
            + [
                "-filter_complex",
                ";".join(filters),
                "-map",
                "[mix]",
                "-c:a",
                "pcm_f32le",
                "mix.wav",
            ],
            cwd=output,
        )
        peaks = run(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                "mix.wav",
                "-af",
                "astats=metadata=0:reset=0",
                "-f",
                "null",
                "-",
            ],
            cwd=output,
        ).stderr
        levels = [float(v) for v in re.findall(r"Peak level dB: ([-+\w.]+)", peaks)]
        if not levels or max(levels) > 0:
            raise ValueError("mix exceeds full scale; adjust locked audio plan")
        if plan["subtitles"]:
            shutil.copy2(plan["subtitles"], output / "subtitles.srt")
        video_args = ["-c:v", "copy"]
        if spec.get("subtitle_mode") == "burn":
            fonts = output / "fonts"
            fonts.mkdir(exist_ok=True)
            shutil.copy2(plan["font"], fonts / ("font" + plan["font"].suffix))
            style = (
                f"FontName={spec['font_family']},FontSize={spec.get('font_size', 22)},"
                f"MarginV={spec.get('margin_v', 16)}"
            )
            video_args = [
                "-vf",
                f"subtitles=subtitles.srt:fontsdir=fonts:force_style='{style}'",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
            ]
        filename = "final.mp4" if mode == "final" else "proxy.mp4"
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                "picture-lock.mp4",
                "-i",
                "mix.wav",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                *video_args,
                "-c:a",
                "aac",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-t",
                str(duration),
                "-movflags",
                "+faststart",
                filename,
            ],
            cwd=output,
        )
        qa = technical_qa(output / filename, plan)
        qa["mix_peak_dbfs"] = max(levels) if math.isfinite(max(levels)) else None
        write_json(output / "TECHNICAL_QA.json", qa)
        outputs = [
            {"path": str((output / name).relative_to(project)), "sha256": sha256(output / name)}
            for name in [
                filename,
                "picture-lock.mp4",
                "mix.wav",
                "TECHNICAL_QA.json",
                *(["subtitles.srt"] if plan["subtitles"] else []),
            ]
        ]
        result = {
            "identity": plan["identity"],
            "status": "READY",
            "segments_reused": reused,
            "outputs": outputs,
            "qa": qa,
            "state_changed": False,
        }
        write_json(manifest_path, result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=["proxy", "final"], default="proxy")
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                render(args.project, args.output, mode=args.mode), ensure_ascii=False, indent=2
            )
        )
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, StopIteration) as exc:
        print(json.dumps({"status": "STOPPED", "reason": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
