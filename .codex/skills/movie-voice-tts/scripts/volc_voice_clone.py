"""Bounded Volc V3 postpaid clone audition, never calls regular TTS/activation."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import uuid
import wave
from datetime import UTC, datetime
from urllib.parse import urlsplit

import requests

from movie_workflow.voice_guard import guarded_operation

BASE = "https://openspeech.bytedance.com/api/v3/tts"


def save(path, value, key=""):
    encoded = json.dumps(value, ensure_ascii=False, indent=2)
    if key:
        encoded = encoded.replace(key, "[REDACTED]")
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(encoded + "\n", encoding="utf-8")
    temp.replace(path)


def choose_demo(payload):
    rows = payload.get("speaker_status", [])
    if not isinstance(rows, list):
        return None
    # Select the ICL2.0 family, never silently use an ICL1.0 result.
    for model in (4, 5):
        for row in rows:
            if row.get("model_type") == model and row.get("demo_audio"):
                return {"model_type": model, "url": row["demo_audio"]}
    return None


def clone_body(reference, speaker, text):
    return {
        "speaker_id": "custom_speaker_id",
        "custom_speaker_id": speaker,
        "audio": {"data": base64.b64encode(reference).decode(), "format": "wav"},
        "language": 0,
        "extra_params": {"demo_text": text, "enable_audio_denoise": False},
    }


@guarded_operation
def run_trial(args):
    folder = args.operation_dir.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    meta_path = folder / "metadata.json"
    meta = None
    key = os.environ.get("VOLCENGINE_TTS_API_KEY", "").strip()
    try:
        if not key and not args.dry_run:
            raise ValueError("缺少VOLCENGINE_TTS_API_KEY")
        audio = args.reference.read_bytes()
        text = args.text_file.read_text(encoding="utf-8").strip()
        if len(audio) > 10 * 1024 * 1024 or not 4 <= len(text) <= 100:
            raise ValueError("本试音限制参考音频10MB、文案4–100字")
        with wave.open(str(args.reference)) as source:
            duration = source.getnframes() / source.getframerate()
            if source.getnchannels() != 1 or not 14 <= duration <= 30:
                raise ValueError("试音参考须为14–30秒单声道WAV")
        hashes = {
            "reference_sha256": hashlib.sha256(audio).hexdigest(),
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        }
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "status": "DRY_RUN_OK",
                        "reference_seconds": duration,
                        "demo_characters": len(text),
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            if any(meta.get(k) != v for k, v in hashes.items()):
                raise ValueError("既有操作参数不同，禁止覆盖或再次注册")
        else:
            meta = {
                "provider": "volcengine",
                "route": "V3_POSTPAID_CLONE_DEMO",
                "status": "PREPARED",
                "created_at": datetime.now(UTC).isoformat(),
                "speaker_id": "movie_voice_" + uuid.uuid4().hex[:16],
                "register_request_id": str(uuid.uuid4()),
                "reference_audio": str(args.reference.resolve()),
                "reference_language": "zh",
                "target_language": "zh",
                "text": text,
                "reference_seconds": duration,
                **hashes,
                "regular_tts_called": False,
                "activated": False,
                "user_voice_choice_confirmed": False,
                "assistant_listened": False,
                "http_register_attempts": 0,
                "http_query_attempts": 0,
            }
            save(meta_path, meta, key)

        def request(action, body, request_id):
            response = requests.post(
                BASE + "/" + action,
                json=body,
                headers={
                    "X-Api-Key": key,
                    "X-Api-Request-Id": request_id,
                    "Content-Type": "application/json",
                },
                timeout=(20, 50),
                allow_redirects=False,
            )
            try:
                payload = response.json()
            except ValueError:
                payload = {"message": "non-JSON response"}
            if not isinstance(payload, dict):
                payload = {"message": "unexpected response type"}
            result = {
                "http_status": response.status_code,
                "payload": payload,
                "request_id": request_id,
                "log_id": response.headers.get("X-Tt-Logid"),
            }
            save(folder / (action + "-" + str(time.time_ns()) + ".json"), result, key)
            if not response.ok or payload.get("code") not in (None, 0, 20000000):
                meta.update(status="REJECTED", last_error=result)
                save(meta_path, meta, key)
                raise RuntimeError("火山请求被拒绝，见本地返回记录")
            return payload

        if meta["status"] in ("REJECTED", "TRAINING_FAILED"):
            print(
                json.dumps(
                    {
                        "status": meta["status"],
                        "reason": meta.get("last_error"),
                        "metadata": str(meta_path),
                    },
                    ensure_ascii=False,
                ).replace(key, "[REDACTED]")
            )
            return 2
        if meta["status"] == "AUDITION_READY":
            print(json.dumps({"status": "AUDITION_READY", "audio": meta["output_audio"]}))
            return 0
        if meta["status"] == "PREPARED":
            # Persist before network; unknown outcome is queried, never automatically re-uploaded.
            meta.update(status="REGISTER_SUBMITTED", http_register_attempts=1)
            save(meta_path, meta, key)
            payload = request(
                "voice_clone",
                clone_body(audio, meta["speaker_id"], text),
                meta["register_request_id"],
            )
            meta.update(status="TRAINING", last_payload=payload)
            save(meta_path, meta, key)
        else:
            payload = meta.get("last_payload", {})
        deadline = time.monotonic() + 120
        while True:
            if payload.get("status") == 3:
                meta.update(status="TRAINING_FAILED", last_payload=payload)
                save(meta_path, meta, key)
                raise RuntimeError("火山音色训练失败")
            demo = choose_demo(payload)
            if payload.get("status") in (2, 4) and demo:
                break
            if time.monotonic() >= deadline:
                meta.update(status="PENDING", last_payload=payload)
                save(meta_path, meta, key)
                print(json.dumps({"status": "PENDING", "metadata": str(meta_path)}))
                return 3
            time.sleep(5)
            meta["http_query_attempts"] += 1
            save(meta_path, meta, key)
            payload = request(
                "get_voice",
                {"speaker_id": "custom_speaker_id", "custom_speaker_id": meta["speaker_id"]},
                str(uuid.uuid4()),
            )
            meta.update(status="TRAINING", last_payload=payload)
            save(meta_path, meta, key)
        url = demo["url"]
        if urlsplit(url).scheme != "https":
            raise ValueError("试听返回URL不是HTTPS，未下载")
        result = requests.get(url, timeout=(15, 45))
        result.raise_for_status()
        if not result.content or len(result.content) > 20 * 1024 * 1024:
            raise ValueError("试听音频为空或超出大小上限")
        output = folder / "clone-demo.audio"
        output.write_bytes(result.content)
        meta.update(
            status="AUDITION_READY",
            last_payload=payload,
            model_type=demo["model_type"],
            output_audio=str(output),
            output_sha256=hashlib.sha256(result.content).hexdigest(),
            regular_tts_called=False,
        )
        save(meta_path, meta, key)
        print(
            json.dumps(
                {
                    "status": "AUDITION_READY",
                    "audio": str(output),
                    "model_type": demo["model_type"],
                    "speaker_id": meta["speaker_id"],
                }
            )
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - persist unknown outcomes without exposing credentials
        if meta and meta.get("status") not in ("REJECTED", "TRAINING_FAILED"):
            meta.update(status="OUTCOME_UNKNOWN_OR_LOCAL_ERROR", error_type=type(exc).__name__)
            save(meta_path, meta, key)
        print(
            json.dumps(
                {
                    "status": meta.get("status") if meta else "LOCAL_INPUT_ERROR",
                    "error_type": type(exc).__name__,
                    "metadata": str(meta_path),
                },
                ensure_ascii=False,
            )
        )
        return 1
