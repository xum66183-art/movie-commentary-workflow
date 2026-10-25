"""Local dependency versions and credential presence; never makes API requests."""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import os
import re
import shutil
import sys
from pathlib import Path

RANGES = {
    "jsonschema": ("jsonschema", (4, 23), (5,)),
    "requests": ("requests", (2, 32), (3,)),
    "PIL": ("Pillow", (10,), (13,)),
    "scenedetect": ("scenedetect", (0, 6, 7), (0, 7)),
    "cv2": ("opencv-python-headless", (4, 10), (5,)),
}
CREDENTIALS = {
    "vision": ["DASHSCOPE_API_KEY"],
    "qwen": ["DASHSCOPE_API_KEY"],
    "minimax": ["MINIMAX_API_KEY"],
    "fish": ["FISH_API_KEY"],
    "volc-asr": ["VOLCENGINE_APPID", "VOLCENGINE_TOKEN"],
    "volc-tts": ["VOLCENGINE_TTS_API_KEY"],
}


def environment_values(path: Path | None):
    values = {}
    if path:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip("\"'")
    return {**values, **os.environ}


def report(*, index=False, config=None, provider=None):
    modules = {}
    for module in ["jsonschema", "requests"] + (["PIL", "scenedetect", "cv2"] if index else []):
        distribution, low, high = RANGES[module]
        try:
            imported = importlib.import_module(module)
            try:
                version = importlib.metadata.version(distribution)
            except importlib.metadata.PackageNotFoundError:
                version = imported.__version__
            parsed = tuple(int(n) for n in re.findall(r"\d+", version)[:3])
            modules[module] = {"version": version, "compatible": low <= parsed < high}
        except (ImportError, AttributeError, OSError):
            modules[module] = {"version": None, "compatible": False}
    values = environment_values(config)
    credentials = {key: bool(values.get(key)) for keys in CREDENTIALS.values() for key in keys}
    binaries = {name: shutil.which(name) is not None for name in ("ffmpeg", "ffprobe")}
    ready = (
        sys.version_info >= (3, 11)
        and all(row["compatible"] for row in modules.values())
        and all(binaries.values())
    )
    return {
        "python_supported": sys.version_info >= (3, 11),
        "modules": modules,
        "binaries": binaries,
        "credentials_configured": credentials,
        "selected_provider_configured": all(credentials[k] for k in CREDENTIALS[provider])
        if provider
        else None,
        "ready_for_local_tools": ready,
        "network_calls": 0,
        "api_credentials_verified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", action="store_true")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--provider", choices=CREDENTIALS)
    args = parser.parse_args()
    try:
        value = report(index=args.index, config=args.config, provider=args.provider)
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return (
            0
            if value["ready_for_local_tools"] and value["selected_provider_configured"] is not False
            else 1
        )
    except OSError:
        print(json.dumps({"status": "CONFIG_READ_FAILED", "network_calls": 0}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
