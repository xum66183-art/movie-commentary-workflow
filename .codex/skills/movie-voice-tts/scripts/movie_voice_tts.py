#!/usr/bin/env python3
"""使用千问、MiniMax 或 Fish Audio 完成项目配音克隆与生成。"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import requests

SKILL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SKILL_ROOT.parents[2]
QWEN_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
QWEN_MODEL = "qwen-audio-3.0-tts-plus"
MINIMAX_BASE_URL = "https://api.minimaxi.com/v1"
MINIMAX_MODEL = "speech-2.8-hd"
FISH_MODEL = "s2.1-pro-free"
FISH_TIMESTAMP_URL = "https://api.fish.audio/v1/tts/stream/with-timestamp"
KEY_NAMES = {
    "qwen": "DASHSCOPE_API_KEY",
    "minimax": "MINIMAX_API_KEY",
    "fish": "FISH_API_KEY",
}


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(name.strip(), value)


def load_default_env() -> None:
    linked_env = os.environ.get("MOVIE_WORKFLOW_ENV_FILE", "").strip()
    paths = [
        Path(linked_env).expanduser() if linked_env else None,
        REPOSITORY_ROOT / ".env",
        SKILL_ROOT / ".env",
    ]
    for path in paths:
        if path is not None:
            load_env(path)


def parse_response(response: requests.Response, step: str) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"{step}失败：服务返回无法解析的响应（HTTP {response.status_code}）"
        ) from exc
    if not response.ok:
        raise RuntimeError(f"{step}失败：HTTP {response.status_code}，{payload}")
    return payload


def read_text(
    value: str | None,
    path: Path | None,
    label: str,
    *,
    strip_markdown_headings: bool = False,
) -> str:
    if value:
        return value.strip()
    if path:
        text = path.read_text(encoding="utf-8").strip()
        if strip_markdown_headings:
            text = "\n".join(
                line for line in text.splitlines() if not line.lstrip().startswith("#")
            ).strip()
        return text
    raise ValueError(f"缺少{label}")


def load_metadata(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_metadata(path: Path, metadata: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def download(url: str, destination: Path) -> None:
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    destination.write_bytes(response.content)


def qwen_headers(api_key: str, *, resolve_oss: bool = False) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if resolve_oss:
        headers["X-DashScope-OssResourceResolve"] = "enable"
    return headers


def qwen_create_voice(
    api_key: str,
    reference: Path,
    reference_language: str,
) -> tuple[str, str]:
    response = requests.get(
        f"{QWEN_BASE_URL}/uploads",
        headers=qwen_headers(api_key),
        params={"action": "getPolicy", "model": "voice-enrollment"},
        timeout=30,
    )
    policy_payload = parse_response(response, "获取千问上传凭证")
    policy = policy_payload["data"]
    object_key = f"{policy['upload_dir']}/{reference.name}"
    with reference.open("rb") as audio_file:
        response = requests.post(
            policy["upload_host"],
            files={
                "OSSAccessKeyId": (None, policy["oss_access_key_id"]),
                "Signature": (None, policy["signature"]),
                "policy": (None, policy["policy"]),
                "x-oss-object-acl": (None, policy["x_oss_object_acl"]),
                "x-oss-forbid-overwrite": (None, policy["x_oss_forbid_overwrite"]),
                "key": (None, object_key),
                "success_action_status": (None, "200"),
                "file": (reference.name, audio_file, "application/octet-stream"),
            },
            timeout=120,
        )
    if not response.ok:
        raise RuntimeError(f"上传千问参考音频失败：HTTP {response.status_code}")

    prefix = f"movie{datetime.now(UTC).strftime('%m%d%H%M%S')}"
    response = requests.post(
        f"{QWEN_BASE_URL}/services/audio/tts/customization",
        headers=qwen_headers(api_key, resolve_oss=True),
        json={
            "model": "voice-enrollment",
            "input": {
                "action": "create_voice",
                "target_model": QWEN_MODEL,
                "prefix": prefix,
                "url": f"oss://{object_key}",
                "language_hints": [reference_language],
                "max_prompt_audio_length": 20,
                "enable_preprocess": False,
            },
        },
        timeout=180,
    )
    payload = parse_response(response, "创建千问克隆音色")
    return payload["output"]["voice_id"], payload.get("request_id", "")


def qwen_wait_for_voice(api_key: str, voice_id: str) -> None:
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        response = requests.post(
            f"{QWEN_BASE_URL}/services/audio/tts/customization",
            headers=qwen_headers(api_key),
            json={
                "model": "voice-enrollment",
                "input": {"action": "query_voice", "voice_id": voice_id},
            },
            timeout=30,
        )
        payload = parse_response(response, "查询千问音色")
        status = payload["output"]["status"]
        if status == "OK":
            return
        if status == "UNDEPLOYED":
            raise RuntimeError("千问音色审核未通过")
        time.sleep(5)
    raise TimeoutError("等待千问音色部署超时")


def run_qwen(args: argparse.Namespace, api_key: str, text: str, metadata: dict) -> dict:
    voice_id = args.voice_id or metadata.get("voice_id", "")
    created = False
    request_id = ""
    if not voice_id:
        voice_id, request_id = qwen_create_voice(
            api_key,
            args.reference,
            args.reference_language,
        )
        created = True
    qwen_wait_for_voice(api_key, voice_id)
    response = requests.post(
        f"{QWEN_BASE_URL}/services/audio/tts/SpeechSynthesizer",
        headers=qwen_headers(api_key),
        json={
            "model": QWEN_MODEL,
            "input": {
                "text": text,
                "voice": voice_id,
                "format": "wav",
                "sample_rate": 24000,
                "language_hints": [args.language],
            },
        },
        timeout=240,
    )
    payload = parse_response(response, "千问语音生成")
    download(payload["output"]["audio"]["url"], args.output)
    return {
        "provider": "qwen",
        "model": QWEN_MODEL,
        "voice_id": voice_id,
        "voice_created": created,
        "create_request_id": request_id,
        "synthesis_request_id": payload.get("request_id", ""),
        "usage": payload.get("usage") or {},
    }


def minimax_headers(api_key: str, *, json_content: bool = False) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {api_key}"}
    if json_content:
        headers["Content-Type"] = "application/json"
    return headers


def check_minimax(payload: dict, step: str) -> dict:
    base_response = payload.get("base_resp") or {}
    if base_response.get("status_code") != 0:
        raise RuntimeError(
            f"{step}失败：MiniMax status_code={base_response.get('status_code')}，"
            f"{base_response.get('status_msg', '未知错误')}"
        )
    return payload


def minimax_create_voice(
    api_key: str,
    reference: Path,
    text: str,
    language: str,
) -> tuple[str, int, str]:
    with reference.open("rb") as audio_file:
        response = requests.post(
            f"{MINIMAX_BASE_URL}/files/upload",
            headers=minimax_headers(api_key),
            data={"purpose": "voice_clone"},
            files={
                "file": (
                    reference.name,
                    audio_file,
                    "application/octet-stream",
                )
            },
            timeout=120,
        )
    upload = check_minimax(parse_response(response, "上传 MiniMax 参考音频"), "上传")
    file_id = int(upload["file"]["file_id"])
    voice_id = f"MovieVoice_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
    response = requests.post(
        f"{MINIMAX_BASE_URL}/voice_clone",
        headers=minimax_headers(api_key, json_content=True),
        json={
            "file_id": file_id,
            "voice_id": voice_id,
            "text": text,
            "model": MINIMAX_MODEL,
            "language_boost": "Chinese" if language == "zh" else "English",
            "need_noise_reduction": False,
            "need_volume_normalization": False,
            "aigc_watermark": False,
        },
        timeout=300,
    )
    clone = check_minimax(parse_response(response, "创建 MiniMax 克隆音色"), "克隆")
    demo_url = clone.get("demo_audio", "")
    return voice_id, file_id, demo_url


def run_minimax(
    args: argparse.Namespace,
    api_key: str,
    text: str,
    metadata: dict,
) -> dict:
    voice_id = args.voice_id or metadata.get("voice_id", "")
    created = False
    file_id = None
    demo_url = ""
    if not voice_id:
        voice_id, file_id, demo_url = minimax_create_voice(
            api_key,
            args.reference,
            text,
            args.language,
        )
        created = True
        if demo_url:
            download(demo_url, args.output.with_name(f"{args.output.stem}_clone_demo.mp3"))

    response = requests.post(
        f"{MINIMAX_BASE_URL}/t2a_v2",
        headers=minimax_headers(api_key, json_content=True),
        json={
            "model": MINIMAX_MODEL,
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice_id,
                "speed": 1,
                "vol": 1,
                "pitch": 0,
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1,
            },
            "language_boost": "Chinese" if args.language == "zh" else "English",
            "subtitle_enable": False,
            "output_format": "url",
            "aigc_watermark": False,
        },
        timeout=300,
    )
    payload = check_minimax(parse_response(response, "MiniMax 语音生成"), "生成")
    audio = (payload.get("data") or {}).get("audio", "")
    if not audio:
        raise RuntimeError("MiniMax 响应中没有音频")
    if audio.startswith(("http://", "https://")):
        download(audio, args.output)
    else:
        args.output.write_bytes(bytes.fromhex(audio))
    return {
        "provider": "minimax",
        "model": MINIMAX_MODEL,
        "voice_id": voice_id,
        "voice_created": created,
        "reference_file_id": file_id,
        "trace_id": payload.get("trace_id", ""),
        "usage": payload.get("extra_info") or {},
    }


def run_fish(args: argparse.Namespace, api_key: str, text: str) -> dict:
    if args.fish_reference_id:
        return run_fish_timestamped(args, api_key, text)

    try:
        from fishaudio import FishAudio
        from fishaudio.types import ReferenceAudio
    except ImportError as exc:
        raise RuntimeError("缺少 fish-audio-sdk；请按 SKILL.md 中的 uv 命令运行") from exc

    reference_text = read_text(
        args.reference_text,
        args.reference_text_file,
        "Fish 参考音频逐字稿",
    )
    synthesis_text = f"[{args.direction}]{text}" if args.direction else text
    client = FishAudio(api_key=api_key, timeout=300)
    try:
        audio = client.tts.convert(
            model=args.fish_model,
            text=synthesis_text,
            references=[
                ReferenceAudio(
                    audio=args.reference.read_bytes(),
                    text=reference_text,
                )
            ],
            format="mp3",
            latency="normal",
            speed=1.0,
        )
    finally:
        client.close()
    args.output.write_bytes(audio)
    return {
        "provider": "fish",
        "model": args.fish_model,
        "voice_id": None,
        "voice_created": False,
        "reference_text": reference_text,
        "direction": args.direction,
        "output_bytes": len(audio),
    }


def normalize_fish_reference_id(value: str) -> str:
    raw_value = value.strip()
    match = re.search(r"(?:/m/)?([0-9a-fA-F]{32})(?:[/?#]|$)", raw_value)
    if not match:
        raise ValueError(
            "Fish 公共音色必须是 32 位模型编号，或包含 /m/<模型编号> 的 fish.audio 链接"
        )
    return match.group(1).lower()


def flatten_fish_alignments(
    chunks: dict[int, dict],
) -> tuple[list[dict], list[dict], int]:
    flattened: list[dict] = []
    chunk_records: list[dict] = []
    duration_ms = 0
    for chunk_seq in sorted(chunks):
        chunk = chunks[chunk_seq]
        offset = float(chunk.get("chunk_audio_offset_sec") or 0)
        alignment = chunk.get("alignment") or {}
        segments = alignment.get("segments") or []
        for segment in segments:
            start_ms = round((offset + float(segment["start"])) * 1000)
            end_ms = round((offset + float(segment["end"])) * 1000)
            flattened.append(
                {
                    "text": segment.get("text", ""),
                    "start_time_ms": start_ms,
                    "end_time_ms": end_ms,
                    "chunk_seq": chunk_seq,
                }
            )
            duration_ms = max(duration_ms, end_ms)
        local_duration = float(alignment.get("audio_duration") or 0)
        duration_ms = max(duration_ms, round((offset + local_duration) * 1000))
        chunk_records.append(
            {
                "chunk_seq": chunk_seq,
                "chunk_audio_offset_sec": offset,
                "content": chunk.get("content", ""),
                "alignment": alignment,
            }
        )
    return flattened, chunk_records, duration_ms


def format_srt_time(milliseconds: int) -> str:
    hours, remainder = divmod(max(0, milliseconds), 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def fish_segments_to_srt(
    segments: list[dict],
    language: str,
    source_text: str = "",
) -> str:
    if not segments:
        return ""
    if language == "zh" and source_text:
        source_lines = [line.strip() for line in source_text.splitlines() if line.strip()]
        source_units = [character for character in source_text if character.isalnum()]
        if len(source_units) == len(segments):
            for segment, character in zip(segments, source_units):
                segment["text"] = character
            cues: list[tuple[int, int, str]] = []
            cursor = 0
            for line in source_lines:
                unit_count = sum(character.isalnum() for character in line)
                if not unit_count:
                    continue
                line_segments = segments[cursor : cursor + unit_count]
                cues.append(
                    (
                        line_segments[0]["start_time_ms"],
                        line_segments[-1]["end_time_ms"],
                        line,
                    )
                )
                cursor += unit_count
            lines: list[str] = []
            for cue_index, (start_ms, end_ms, text) in enumerate(cues, 1):
                lines.extend(
                    [
                        str(cue_index),
                        f"{format_srt_time(start_ms)} --> {format_srt_time(end_ms)}",
                        text,
                        "",
                    ]
                )
            return "\n".join(lines)

    cues: list[tuple[int, int, str]] = []
    current: list[dict] = []
    hard_stops = set("。！？!?；;")
    soft_stops = set("，,、：:")
    max_units = 22 if language == "zh" else 12

    def cue_text(items: list[dict]) -> str:
        tokens = [str(item.get("text", "")).strip() for item in items]
        tokens = [token for token in tokens if token]
        return "".join(tokens) if language == "zh" else " ".join(tokens)

    for index, segment in enumerate(segments):
        current.append(segment)
        text = cue_text(current)
        next_start = (
            segments[index + 1]["start_time_ms"]
            if index + 1 < len(segments)
            else segment["end_time_ms"]
        )
        gap_ms = next_start - segment["end_time_ms"]
        last_character = text[-1:] if text else ""
        should_close = (
            last_character in hard_stops
            or len(text) >= max_units
            or gap_ms >= 650
            or (last_character in soft_stops and len(text) >= max_units // 2)
            or index + 1 == len(segments)
        )
        if should_close and text:
            cues.append(
                (
                    current[0]["start_time_ms"],
                    current[-1]["end_time_ms"],
                    text,
                )
            )
            current = []

    lines: list[str] = []
    for cue_index, (start_ms, end_ms, text) in enumerate(cues, 1):
        lines.extend(
            [
                str(cue_index),
                f"{format_srt_time(start_ms)} --> {format_srt_time(end_ms)}",
                text,
                "",
            ]
        )
    return "\n".join(lines)


def run_fish_timestamped(
    args: argparse.Namespace,
    api_key: str,
    text: str,
) -> dict:
    reference_id = normalize_fish_reference_id(args.fish_reference_id)
    synthesis_text = f"[{args.direction}]{text}" if args.direction else text
    response = requests.post(
        FISH_TIMESTAMP_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "model": args.fish_model,
        },
        json={
            "text": synthesis_text,
            "reference_id": reference_id,
            "format": "mp3",
            "normalize": True,
            "temperature": 0.7,
            "top_p": 0.7,
            "prosody": {
                "speed": args.speed,
                "volume": 0,
                "normalize_loudness": True,
            },
            "chunk_length": 300,
            "sample_rate": 44100,
            "mp3_bitrate": 128,
            "latency": "normal",
            "condition_on_previous_chunks": True,
        },
        stream=True,
        timeout=(30, 1800),
    )
    if not response.ok:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:500]
        raise RuntimeError(f"Fish 带时间戳语音生成失败：HTTP {response.status_code}，{detail}")

    audio_parts: list[bytes] = []
    chunks: dict[int, dict] = {}
    event_count = 0
    event_lines: list[str] = []

    def parse_event(lines: list[str]) -> dict | None:
        if not lines:
            return None
        payload_text = "".join(lines).strip()
        if not payload_text or payload_text == "[DONE]":
            return None
        return json.loads(payload_text)

    def consume_event(event: dict | None) -> None:
        nonlocal event_count
        if event is None:
            return
        event_count += 1
        audio_base64 = event.get("audio_base64")
        if audio_base64:
            audio_parts.append(base64.b64decode(audio_base64))
        chunk_seq = int(event.get("chunk_seq") or 0)
        chunks[chunk_seq] = {
            "chunk_seq": chunk_seq,
            "chunk_audio_offset_sec": event.get("chunk_audio_offset_sec") or 0,
            "content": event.get("content") or "",
            "alignment": event.get("alignment") or {},
        }

    for raw_line_bytes in response.iter_lines(decode_unicode=False):
        raw_line = raw_line_bytes.decode("utf-8")
        if raw_line == "":
            consume_event(parse_event(event_lines))
            event_lines = []
            continue
        if raw_line.startswith("data:"):
            event_lines.append(raw_line[5:].lstrip())
        elif event_lines:
            event_lines.append(raw_line)
    consume_event(parse_event(event_lines))

    if not audio_parts:
        raise RuntimeError("Fish 响应中没有音频数据")
    args.output.write_bytes(b"".join(audio_parts))

    segments, chunk_records, duration_ms = flatten_fish_alignments(chunks)
    if not segments:
        raise RuntimeError("Fish 响应中没有原生时间戳")
    timestamp_path = args.timestamp_json or args.output.with_suffix(".timestamps.json")
    srt_path = args.output_srt or args.output.with_suffix(".srt")
    srt_text = fish_segments_to_srt(segments, args.language, text)
    save_metadata(
        timestamp_path,
        {
            "schema_version": "1.0",
            "created_at": datetime.now(UTC).isoformat(),
            "provider": "fish",
            "model": args.fish_model,
            "timestamp_source": "fish_native_alignment",
            "reference_id": reference_id,
            "audio_file": str(args.output.resolve()),
            "duration_ms": duration_ms,
            "segment_count": len(segments),
            "segments": segments,
            "chunks": chunk_records,
        },
    )
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    srt_path.write_text(
        srt_text,
        encoding="utf-8",
    )
    return {
        "provider": "fish",
        "model": args.fish_model,
        "voice_id": reference_id,
        "voice_created": False,
        "reference_id": reference_id,
        "reference_url": f"https://fish.audio/m/{reference_id}",
        "reference_text": None,
        "direction": args.direction,
        "speed": args.speed,
        "output_bytes": sum(len(part) for part in audio_parts),
        "timestamp_source": "fish_native_alignment",
        "timestamp_json": str(timestamp_path.resolve()),
        "output_srt": str(srt_path.resolve()),
        "timestamp_segment_count": len(segments),
        "timestamp_duration_ms": duration_ms,
        "stream_event_count": event_count,
    }


def check_environment() -> int:
    load_default_env()
    missing = [name for name in KEY_NAMES.values() if not os.environ.get(name, "").strip()]
    if missing:
        print(f"缺少配置：{', '.join(missing)}", file=sys.stderr)
        return 2
    try:
        import fishaudio  # noqa: F401
    except ImportError:
        print("缺少 fish-audio-sdk", file=sys.stderr)
        return 2
    print("千问、MiniMax、Fish Audio 配置与运行依赖均已就绪。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="provider", required=True)
    subparsers.add_parser("check", help="只检查三家密钥和运行依赖，不调用 API")

    trial = subparsers.add_parser(
        "volc-audition", help="火山V3后付费注册及接口内置短试听，不调用正式合成"
    )
    trial.add_argument("--reference", type=Path, required=True)
    trial.add_argument("--text-file", type=Path, required=True)
    trial.add_argument("--operation-dir", type=Path, required=True)
    trial.add_argument("--env-file", type=Path, required=True)
    trial.add_argument("--dry-run", action="store_true")

    qvc = subparsers.add_parser("qwen-vc-audition", help="千问3 VC中文克隆短试音")
    qvc.add_argument("--reference", type=Path, required=True)
    qvc.add_argument("--text-file", type=Path, required=True)
    qvc.add_argument("--operation-dir", type=Path, required=True)
    qvc.add_argument("--env-file", type=Path, required=True)
    qvc.add_argument("--dry-run", action="store_true")

    qfull = subparsers.add_parser(
        "qwen-vc-narrate", help="复用已采用千问VC音色，按锁定文稿生成整篇旁白"
    )
    qfull.add_argument("--project", type=Path, required=True)
    qfull.add_argument("--operation-dir", type=Path, required=True)
    qfull.add_argument("--env-file", type=Path, required=True)
    qfull.add_argument("--dry-run", action="store_true")
    qfull.add_argument("--max-new-requests", type=int, default=20)
    qfull.add_argument("--max-billable-characters", type=int, default=20000)
    qfull.add_argument("--price-per-10k", type=float)
    qfull.add_argument("--max-estimated-cost", type=float)

    for provider in KEY_NAMES:
        child = subparsers.add_parser(provider)
        child.add_argument("--reference", type=Path)
        text_group = child.add_mutually_exclusive_group(required=True)
        text_group.add_argument("--text")
        text_group.add_argument("--text-file", type=Path)
        child.add_argument("--strip-markdown-headings", action="store_true")
        child.add_argument("--output", type=Path, required=True)
        child.add_argument("--metadata", type=Path)
        child.add_argument("--reference-language", choices=("zh", "en"), default="en")
        child.add_argument("--language", choices=("zh", "en"), default="zh")
        child.add_argument("--voice-id")
        child.add_argument("--dry-run", action="store_true")
        if provider == "fish":
            reference_group = child.add_mutually_exclusive_group()
            reference_group.add_argument("--reference-text")
            reference_group.add_argument("--reference-text-file", type=Path)
            child.add_argument(
                "--fish-reference-id",
                help="Fish 公共音色模型编号或 fish.audio/m/<编号> 链接",
            )
            child.add_argument("--direction", default="")
            child.add_argument("--fish-model", default=FISH_MODEL)
            child.add_argument("--speed", type=float, default=1.0)
            child.add_argument("--timestamp-json", type=Path)
            child.add_argument("--output-srt", type=Path)
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.provider in {"qwen", "minimax"} and not args.reference:
        raise ValueError(f"{args.provider} 必须提供 --reference")
    if args.provider == "fish" and not args.fish_reference_id and not args.reference:
        raise ValueError("Fish 必须提供 --fish-reference-id 或 --reference")
    if args.reference and not args.reference.is_file():
        raise FileNotFoundError(f"找不到参考音频：{args.reference}")
    if args.text_file and not args.text_file.is_file():
        raise FileNotFoundError(f"找不到文案：{args.text_file}")
    if (
        args.provider == "fish"
        and args.reference_text_file
        and not args.reference_text_file.is_file()
    ):
        raise FileNotFoundError(f"找不到参考音频逐字稿：{args.reference_text_file}")
    if args.provider == "fish" and not args.fish_reference_id:
        if not args.reference_text and not args.reference_text_file:
            raise ValueError("Fish 零样本克隆必须提供参考音频逐字稿")
    if args.provider == "fish" and args.fish_reference_id:
        normalize_fish_reference_id(args.fish_reference_id)
    if args.provider == "fish" and args.speed <= 0:
        raise ValueError("Fish 语速必须大于 0")
    expected_suffix = ".wav" if args.provider == "qwen" else ".mp3"
    if args.output.suffix.lower() != expected_suffix:
        raise ValueError(f"{args.provider} 输出文件必须使用 {expected_suffix} 后缀")


def execute(args) -> int:
    load_default_env()
    if args.provider == "check":
        return check_environment()
    if args.provider == "volc-audition":
        from volc_voice_clone import run_trial

        load_env(args.env_file)
        return run_trial(args)
    if args.provider == "qwen-vc-audition":
        from qwen_vc_audition import run_trial

        load_env(args.env_file)
        return run_trial(args)
    if args.provider == "qwen-vc-narrate":
        from qwen_vc_narration import run_narration

        load_env(args.env_file)
        return run_narration(args)

    try:
        validate_args(args)
        text = read_text(
            args.text,
            args.text_file,
            "生成文案",
            strip_markdown_headings=args.strip_markdown_headings,
        )
        api_key = os.environ.get(KEY_NAMES[args.provider], "").strip()
        if not api_key:
            raise RuntimeError(f"缺少 {KEY_NAMES[args.provider]}")
        metadata_path = args.metadata or args.output.with_suffix(".json")
        metadata = load_metadata(metadata_path)
        if args.dry_run:
            print(
                f"检查通过：供应商={args.provider}，"
                f"参考语言={args.reference_language}，"
                f"目标语言={args.language}，文案字符数={len(text)}"
            )
            return 0

        args.output.parent.mkdir(parents=True, exist_ok=True)
        base_metadata = {
            "created_at": datetime.now(UTC).isoformat(),
            "reference_audio": str(args.reference.resolve()) if args.reference else None,
            "reference_language": args.reference_language,
            "target_language": args.language,
            "text": text,
            "output_audio": str(args.output.resolve()),
            "status": "RUNNING",
        }
        save_metadata(metadata_path, {**metadata, **base_metadata})
        if args.provider == "qwen":
            result = run_qwen(args, api_key, text, metadata)
        elif args.provider == "minimax":
            result = run_minimax(args, api_key, text, metadata)
        else:
            result = run_fish(args, api_key, text)
        save_metadata(
            metadata_path,
            {**metadata, **base_metadata, **result, "status": "OK"},
        )
        print(f"生成完成：{args.output}")
        return 0
    except Exception as exc:  # noqa: BLE001 - 命令行只输出简洁错误
        reason = str(exc)
        for name in (*KEY_NAMES.values(), "VOLCENGINE_TTS_API_KEY"):
            if os.environ.get(name):
                reason = reason.replace(os.environ[name], "[REDACTED]")
        print(reason, file=sys.stderr)
        return 1


def main() -> int:
    from movie_workflow.voice_guard import legacy_operation

    args = build_parser().parse_args()
    if args.provider in KEY_NAMES and not args.dry_run:
        try:
            return legacy_operation(args, execute)
        except (OSError, ValueError, RuntimeError) as exc:
            print(
                type(exc).__name__ + ": paid operation stopped; inspect local receipt",
                file=sys.stderr,
            )
            return 1
    return execute(args)


if __name__ == "__main__":
    raise SystemExit(main())
