"""Generate a locked narration in paragraph units, reusing the accepted Qwen VC voice."""

from __future__ import annotations

import hashlib
import json
import os
import wave
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests
from qwen_vc_audition import BASE, MODEL, save


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_plan(text):
    paragraphs = text.strip().split("\n\n")
    if any(not p.strip() or len(p) > 500 for p in paragraphs):
        raise ValueError("本生成路线要求每个自然段1–500字符，不改写或截断")
    return [
        {"id": i + 1, "text": p, "text_sha256": hashlib.sha256(p.encode()).hexdigest()}
        for i, p in enumerate(paragraphs)
    ]


def locked_inputs(project):
    state = json.loads((project / "production/state.json").read_text())
    locks = state["locks"]
    for name in ("script", "voice"):
        lock = locks[name]
        if not lock or sha(lock["path"]) != lock["sha256"] or not lock.get("user_confirmed"):
            raise ValueError("缺少有效的用户确认锁：" + name)
    script = json.loads(Path(locks["script"]["path"]).read_text())
    voice = json.loads(Path(locks["voice"]["path"]).read_text())
    if script["status"] != "SCRIPT_LOCKED" or voice["status"] != "VOICE_LOCKED":
        raise ValueError("文稿与音色未锁定")
    if voice["model"] != MODEL or voice["provider"] != "qwen":
        raise ValueError("采用音色不属于本模型，禁止切换")
    source = script["narration_text"]
    if sha(source["path"]) != source["sha256"]:
        raise ValueError("锁定文稿指纹不符")
    text = Path(source["path"]).read_text(encoding="utf-8")
    return source, voice, text


def generate_part(folder, row, voice, key):
    folder.mkdir(parents=True, exist_ok=True)
    mp = folder / "metadata.json"
    if mp.exists():
        meta = json.loads(mp.read_text())
        if meta["text_sha256"] != row["text_sha256"] or meta["voice_id"] != voice:
            raise ValueError("已有片段参数不符")
    else:
        meta = {
            **row,
            "model": MODEL,
            "voice_id": voice,
            "status": "PREPARED",
            "created_at": datetime.now(UTC).isoformat(),
            "synthesis_requests": 0,
        }
        save(mp, meta, key)
    if meta["status"] == "READY":
        if sha(meta["audio"]) != meta["audio_sha256"]:
            raise ValueError("已有音频指纹不符")
        return meta
    if meta["status"] in ("REJECTED", "SUBMITTED", "OUTCOME_UNKNOWN"):
        raise RuntimeError("拒绝或未知结果禁止自动再次合成")
    if meta["status"] == "PREPARED":
        meta.update(status="SUBMITTED", synthesis_requests=1)
        save(mp, meta, key)
        try:
            response = requests.post(
                BASE + "/aigc/multimodal-generation/generation",
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                json={
                    "model": MODEL,
                    "input": {"text": row["text"], "voice": voice, "language_type": "Chinese"},
                },
                timeout=(20, 120),
                allow_redirects=False,
            )
            payload = response.json()
            save(
                folder / "response.json",
                {"http_status": response.status_code, "payload": payload},
                key,
            )
            if not response.ok or payload.get("code"):
                meta.update(
                    status="REJECTED",
                    error_code=payload.get("code"),
                    http_status=response.status_code,
                )
                save(mp, meta, key)
                raise RuntimeError("合成请求拒绝，停止后续调用")
            meta.update(
                status="SYNTHESIZED",
                request_id=payload.get("request_id"),
                usage=payload.get("usage"),
            )
            save(mp, meta, key)
        except Exception:  # noqa: BLE001
            if meta["status"] == "SUBMITTED":
                meta["status"] = "OUTCOME_UNKNOWN"
                save(mp, meta, key)
            raise
    payload = json.loads((folder / "response.json").read_text())["payload"]
    url = payload["output"]["audio"]["url"]
    parts = urlsplit(url)
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or not parts.hostname.endswith(".aliyuncs.com")
    ):
        raise ValueError("音频不是预期阿里云地址")
    url = urlunsplit(parts._replace(scheme="https"))
    download = requests.get(url, timeout=(20, 60))
    download.raise_for_status()
    if not download.content or len(download.content) > 30 * 1024 * 1024:
        raise ValueError("返回音频为空或过大")
    raw = folder / "provider.wav"
    raw.write_bytes(download.content)
    # Preserve the entire PCM, replacing the provider's placeholder WAV length header.
    with wave.open(str(raw)) as wav:
        params = wav.getparams()
        pcm = wav.readframes(wav.getnframes())
    if params.nchannels != 1 or params.sampwidth != 2 or params.framerate != 24000 or len(pcm) % 2:
        raise ValueError("供应商PCM格式改变，停止合并")
    duration = len(pcm) / 2 / 24000
    if duration <= 0:
        raise ValueError("零长度音频")
    output = folder / "audio.wav"
    with wave.open(str(output), "wb") as wav:
        wav.setparams(params)
        wav.writeframes(pcm)
    meta.update(
        status="READY",
        audio=str(output),
        audio_sha256=sha(output),
        duration_seconds=duration,
        pcm_preserved=True,
        source_audio_sha256=sha(raw),
    )
    save(mp, meta, key)
    return meta


def run_narration(args):
    key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    try:
        if not key:
            raise ValueError("缺少DASHSCOPE_API_KEY")
        project = args.project.resolve()
        source, voice, text = locked_inputs(project)
        plan = make_plan(text)
        folder = args.operation_dir.resolve()
        folder.mkdir(parents=True, exist_ok=True)
        manifest = {
            "model": MODEL,
            "voice_id": voice["voice_id"],
            "narration_text": source,
            "parts": plan,
            "new_voice_registration_requests": 0,
            "pause_between_paragraphs_seconds": 0.35,
            "script_changed": False,
        }
        pp = folder / "plan.json"
        if pp.exists() and json.loads(pp.read_text()) != manifest:
            raise ValueError("已保存的生产计划不符，禁止覆盖")
        locked_meta = folder / "narration.json"
        if locked_meta.exists():
            cached = json.loads(locked_meta.read_text())
            if cached.get("status") == "NARRATION_LOCKED":
                if any(
                    cached.get(k) != manifest[k]
                    for k in ("model", "voice_id", "narration_text", "parts")
                ):
                    raise ValueError("已锁定旁白参数不符，禁止覆盖")
                if sha(cached["output_audio"]) != cached["output_sha256"]:
                    raise ValueError("已锁定旁白音频指纹不符")
                print(
                    json.dumps(
                        {
                            "status": "LOCKED_CACHE_UNCHANGED",
                            "audio": cached["output_audio"],
                            "duration_seconds": cached["duration_seconds"],
                            "live_calls": 0,
                        }
                    )
                )
                return 0
        save(pp, manifest, key)
        if args.dry_run:
            print(json.dumps({"status": "DRY_RUN_OK", "parts": len(plan), "voice_reused": True}))
            return 0
        metas = []
        for row in plan:
            meta = generate_part(folder / f"part-{row['id']:03d}", row, voice["voice_id"], key)
            metas.append(meta)
            print(
                json.dumps(
                    {
                        "completed": len(metas),
                        "total": len(plan),
                        "duration_seconds": meta["duration_seconds"],
                    }
                ),
                flush=True,
            )
        frames = []
        offsets = []
        cursor = 0
        for i, meta in enumerate(metas):
            with wave.open(meta["audio"]) as wav:
                pcm = wav.readframes(wav.getnframes())
            count = len(pcm) // 2
            offsets.append(
                {
                    "id": meta["id"],
                    "start_frame": cursor,
                    "end_frame": cursor + count,
                    "start_seconds": cursor / 24000,
                    "end_seconds": (cursor + count) / 24000,
                    "text": meta["text"],
                    "audio_sha256": meta["audio_sha256"],
                }
            )
            frames.append(pcm)
            cursor += count
            if i < len(metas) - 1:
                frames.append(b"\0\0" * 8400)
                cursor += 8400
        final = folder / "narration.wav"
        with wave.open(str(final), "wb") as wav:
            wav.setparams((1, 2, 24000, 0, "NONE", "none"))
            for pcm in frames:
                wav.writeframes(pcm)
        save(
            folder / "narration.json",
            {
                **manifest,
                "status": "GENERATED_QA_PENDING",
                "output_audio": str(final),
                "output_sha256": sha(final),
                "duration_seconds": cursor / 24000,
                "part_offsets": offsets,
                "synthesis_requests": sum(m["synthesis_requests"] for m in metas),
                "usage_characters": sum(m.get("usage", {}).get("characters", 0) for m in metas),
                "timestamp_source": None,
                "assistant_listened": False,
            },
            key,
        )
        print(
            json.dumps(
                {
                    "status": "GENERATED_QA_PENDING",
                    "audio": str(final),
                    "duration_seconds": cursor / 24000,
                }
            ),
            flush=True,
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {
                    "status": "STOPPED",
                    "error_type": type(exc).__name__,
                    "reason": str(exc).replace(key, "[REDACTED]") if key else str(exc),
                }
            )
        )
        return 1
