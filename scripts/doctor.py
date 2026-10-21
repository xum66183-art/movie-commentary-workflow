#!/usr/bin/env python3
"""Check local dependencies and credential presence without making network calls."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--index", action="store_true", help="Require optional indexing dependencies"
    )
    args = parser.parse_args()
    required = ["jsonschema", "requests"] + (["PIL", "scenedetect", "cv2"] if args.index else [])
    modules = {name: importlib.util.find_spec(name) is not None for name in required}
    binaries = {name: shutil.which(name) is not None for name in ("ffmpeg", "ffprobe")}
    ok = sys.version_info >= (3, 11) and all(modules.values()) and all(binaries.values())
    print(
        json.dumps(
            {
                "python_supported": sys.version_info >= (3, 11),
                "modules": modules,
                "binaries": binaries,
                "credentials_in_process": {
                    name: bool(os.environ.get(name))
                    for name in (
                        "DASHSCOPE_API_KEY",
                        "MINIMAX_API_KEY",
                        "FISH_API_KEY",
                        "VOLCENGINE_APPID",
                        "VOLCENGINE_TOKEN",
                        "VOLCENGINE_TTS_API_KEY",
                    )
                },
                "network_calls": 0,
                "ready_for_local_tools": ok,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
