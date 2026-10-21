"""Bounded Qwen3 VC audition with persisted voice reuse and no automatic retries."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import uuid
import wave
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

import requests

BASE = "https://dashscope.aliyuncs.com/api/v1/services"
MODEL = "qwen3-tts-vc-2026-01-22"


def save(path, data, key):
    text = (
        json.dumps(data, ensure_ascii=False, indent=2).replace(key, "[REDACTED]")
        if key
        else json.dumps(data, ensure_ascii=False, indent=2)
    )
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text + "\n", encoding="utf-8")
    tmp.replace(path)


def register_body(audio, name):
    if not re.fullmatch(r"[A-Za-z0-9_]{1,16}", name):
        raise ValueError("音色名称须为1–16位字母数字或下划线")
    return {
        "model": "qwen-voice-enrollment",
        "input": {
            "action": "create",
            "target_model": MODEL,
            "preferred_name": name,
            "audio": {"data": "data:audio/wav;base64," + base64.b64encode(audio).decode()},
        },
    }


def run_trial(args):
    folder = args.operation_dir.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    mp = folder / "metadata.json"
    key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    meta = None
    try:
        if not key:
            raise ValueError("缺少DASHSCOPE_API_KEY")
        audio = args.reference.read_bytes()
        text = args.text_file.read_text(encoding="utf-8").strip()
        if len(audio) > 10 * 1024 * 1024 or not 4 <= len(text) <= 100:
            raise ValueError("短试音限制参考10MB，文案4–100字")
        with wave.open(str(args.reference)) as wav:
            duration = wav.getnframes() / wav.getframerate()
            if (
                wav.getnchannels() != 1
                or wav.getframerate() < 24000
                or wav.getsampwidth() != 2
                or not 3 <= duration <= 60
            ):
                raise ValueError("参考须为3–60秒、24k以上单声道PCM16 WAV")
        hashes = {
            "reference_sha256": hashlib.sha256(audio).hexdigest(),
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        }
        billed = len(text) + len(re.findall(r"[\u3400-\u9fff]", text))
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "status": "DRY_RUN_OK",
                        "model": MODEL,
                        "reference_seconds": duration,
                        "billing_characters": billed,
                    }
                )
            )
            return 0
        if mp.exists():
            meta = json.loads(mp.read_text())
            if meta.get("model") != MODEL or any(meta.get(k) != v for k, v in hashes.items()):
                raise ValueError("既有试音参数不同，禁止覆盖")
        else:
            meta = {
                "provider": "qwen",
                "model": MODEL,
                "status": "PREPARED",
                "created_at": datetime.now(UTC).isoformat(),
                **hashes,
                "reference_audio": str(args.reference.resolve()),
                "reference_seconds": duration,
                "reference_language": "zh",
                "target_language": "zh",
                "text": text,
                "preferred_name": "voice_" + uuid.uuid4().hex[:6],
                "billing_characters_estimated": billed,
                "price_without_free_quota_estimated_yuan": 0.01 + billed * 0.8 / 10000,
                "register_requests": 0,
                "synthesis_requests": 0,
                "assistant_listened": False,
                "user_voice_choice_confirmed": False,
                "full_narration": False,
            }
            save(mp, meta, key)
        if meta["status"] in ("REJECTED", "OUTCOME_UNKNOWN"):
            raise RuntimeError("既有请求拒绝或结果未知，禁止自动重试")
        if meta["status"] == "AUDITION_READY":
            print(json.dumps({"status": "AUDITION_READY", "audio": meta["output_audio"]}))
            return 0

        def post(step, endpoint, body):
            response = requests.post(
                BASE + endpoint,
                json=body,
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                timeout=(20, 90),
                allow_redirects=False,
            )
            try:
                payload = response.json()
            except ValueError:
                payload = {"message": "non-JSON response"}
            record = {"http_status": response.status_code, "payload": payload}
            save(folder / (step + "-response.json"), record, key)
            if not response.ok or payload.get("code"):
                meta.update(status="REJECTED", last_error=record)
                save(mp, meta, key)
                raise RuntimeError("千问请求拒绝，见本地记录")
            return payload

        if meta["status"] == "PREPARED":
            meta.update(status="REGISTER_SUBMITTED", register_requests=1)
            save(mp, meta, key)
            result = post(
                "register", "/audio/tts/customization", register_body(audio, meta["preferred_name"])
            )
            voice = result.get("output", {}).get("voice")
            if not voice:
                raise ValueError("成功返回缺少音色ID")
            meta.update(
                status="VOICE_CREATED",
                voice_id=voice,
                register_request_id=result.get("request_id"),
                register_usage=result.get("usage"),
            )
            save(mp, meta, key)
        if meta["status"] == "VOICE_CREATED":
            meta.update(status="SYNTHESIS_SUBMITTED", synthesis_requests=1)
            save(mp, meta, key)
            result = post(
                "synthesis",
                "/aigc/multimodal-generation/generation",
                {
                    "model": MODEL,
                    "input": {"text": text, "voice": meta["voice_id"], "language_type": "Chinese"},
                },
            )
            meta.update(
                status="SYNTHESIZED",
                synthesis_request_id=result.get("request_id"),
                synthesis_usage=result.get("usage"),
            )
            save(mp, meta, key)
        if meta["status"] != "SYNTHESIZED":
            raise RuntimeError("未完成请求，禁止自动重新发送")
        result = json.loads((folder / "synthesis-response.json").read_text())["payload"]
        url = result["output"]["audio"]["url"]
        parts = urlsplit(url)
        # Official response may use http; retrieve the same OSS object over HTTPS.
        if (
            parts.scheme not in ("http", "https")
            or not parts.hostname
            or not parts.hostname.endswith(".aliyuncs.com")
        ):
            raise ValueError("返回音频不是预期阿里云地址")
        url = urlunsplit(parts._replace(scheme="https"))
        response = requests.get(url, timeout=(20, 60))
        response.raise_for_status()
        if not response.content or len(response.content) > 20 * 1024 * 1024:
            raise ValueError("音频为空或过大")
        out = folder / "clone-demo.wav"
        out.write_bytes(response.content)
        meta.update(
            status="AUDITION_READY",
            output_audio=str(out),
            output_sha256=hashlib.sha256(response.content).hexdigest(),
        )
        save(mp, meta, key)
        print(json.dumps({"status": "AUDITION_READY", "audio": str(out), "model": MODEL}))
        return 0
    except Exception as exc:  # noqa: BLE001
        if meta and meta["status"] in ("REGISTER_SUBMITTED", "SYNTHESIS_SUBMITTED"):
            meta.update(status="OUTCOME_UNKNOWN", error_type=type(exc).__name__)
            save(mp, meta, key)
        print(
            json.dumps(
                {
                    "status": meta.get("status") if meta else "LOCAL_INPUT_ERROR",
                    "error_type": type(exc).__name__,
                    "metadata": str(mp),
                }
            )
        )
        return 1
