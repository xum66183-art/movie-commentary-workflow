#!/usr/bin/env python3
"""使用火山引擎视频字幕语音识别恢复句级和字级时间戳。"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
from pathlib import Path

import requests

SKILL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SKILL_ROOT.parents[2]
SUBMIT_URL = "https://openspeech.bytedance.com/api/v1/vc/submit"
QUERY_URL = "https://openspeech.bytedance.com/api/v1/vc/query"


def load_env_file(path: Path | None) -> None:
    if path is None or not path.is_file():
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


def load_credentials(explicit_env: Path | None) -> tuple[str, str]:
    load_env_file(explicit_env)
    workflow_env = os.environ.get("MOVIE_WORKFLOW_ENV_FILE", "").strip()
    if workflow_env:
        load_env_file(Path(workflow_env).expanduser())
    load_env_file(REPOSITORY_ROOT / ".env")
    load_env_file(SKILL_ROOT / ".env")
    linked_env = os.environ.get("VOLCENGINE_ENV_FILE", "").strip()
    if linked_env:
        load_env_file(Path(linked_env).expanduser())
    appid = os.environ.get("VOLCENGINE_APPID", "").strip()
    token = os.environ.get("VOLCENGINE_TOKEN", "").strip()
    if not appid or not token:
        raise RuntimeError(
            "缺少 VOLCENGINE_APPID 或 VOLCENGINE_TOKEN；"
            "请配置到进程环境、仓库 .env、--env-file 或环境文件指针"
        )
    return appid, token


def response_json(response: requests.Response, step: str) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"{step}失败：HTTP {response.status_code}，响应不是 JSON") from exc
    if not response.ok:
        raise RuntimeError(f"{step}失败：HTTP {response.status_code}，{payload}")
    return payload


def content_type(path: Path) -> str:
    known = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
        ".opus": "audio/ogg",
    }
    return known.get(
        path.suffix.lower(),
        mimetypes.guess_type(path.name)[0] or "audio/*",
    )


def submit(
    session: requests.Session,
    audio: Path,
    appid: str,
    token: str,
    language: str,
) -> str:
    with audio.open("rb") as audio_file:
        response = session.post(
            SUBMIT_URL,
            params={
                "appid": appid,
                "language": language,
                "use_itn": "True",
                "use_punc": "True",
                "caption_type": "speech",
                "max_lines": 1,
                "words_per_line": 15 if language == "zh-CN" else 55,
            },
            headers={
                "Authorization": f"Bearer; {token}",
                "Content-Type": content_type(audio),
            },
            data=audio_file,
            timeout=120,
        )
    payload = response_json(response, "提交音频")
    if str(payload.get("code")) != "0" or not payload.get("id"):
        raise RuntimeError(
            f"提交音频失败：代码={payload.get('code')}，消息={payload.get('message')}"
        )
    return str(payload["id"])


def query(
    session: requests.Session,
    job_id: str,
    appid: str,
    token: str,
    timeout_seconds: int,
) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = session.get(
            QUERY_URL,
            params={"appid": appid, "id": job_id, "blocking": "0"},
            headers={"Authorization": f"Bearer; {token}"},
            timeout=30,
        )
        payload = response_json(response, "查询识别结果")
        code = str(payload.get("code"))
        if code == "0":
            return payload
        if code != "2000":
            raise RuntimeError(
                f"查询识别失败：代码={payload.get('code')}，消息={payload.get('message')}"
            )
        time.sleep(1)
    raise RuntimeError(f"查询识别超时：等待超过 {timeout_seconds} 秒")


def ms_to_srt(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def make_srt(utterances: list[dict]) -> str:
    blocks = []
    for utterance in utterances:
        text = str(utterance.get("text", "")).strip()
        if not text:
            continue
        blocks.append(
            "\n".join(
                [
                    str(len(blocks) + 1),
                    (
                        f"{ms_to_srt(int(utterance['start_time']))} --> "
                        f"{ms_to_srt(int(utterance['end_time']))}"
                    ),
                    text,
                ]
            )
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--language", default="zh-CN")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-srt", type=Path)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--timeout", type=int, default=180)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.audio.is_file():
        print(f"找不到音频：{args.audio}", file=sys.stderr)
        return 2
    try:
        appid, token = load_credentials(args.env_file)
        with requests.Session() as session:
            job_id = submit(session, args.audio, appid, token, args.language)
            payload = query(session, job_id, appid, token, args.timeout)
        write_text(
            args.output_json,
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        )
        utterances = payload.get("utterances") or []
        if args.output_srt:
            write_text(args.output_srt, make_srt(utterances))
        characters = sum(len(item.get("words") or []) for item in utterances)
        transcript = "".join(str(item.get("text", "")) for item in utterances)
        print(
            f"识别成功：{len(utterances)} 句，{characters} 个时间戳，"
            f"时长 {payload.get('duration', 0)} 秒"
        )
        print(f"识别文本：{transcript}")
        return 0
    except (OSError, requests.RequestException, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
