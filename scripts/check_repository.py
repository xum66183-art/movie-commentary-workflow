#!/usr/bin/env python3
"""Fail when a public checkout contains private paths, secrets, media, or large artifacts."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MAX_PUBLIC_FILE_BYTES = 5 * 1024 * 1024

IGNORED_GENERATED_DIRECTORY_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "build",
    "dist",
}

BLOCKED_DIRECTORY_NAMES = {
    "node_modules",
    "site-packages",
    "runtime",
    "models",
    "checkpoints",
}

BLOCKED_SUFFIXES = {
    ".srt",
    ".ass",
    ".vtt",
    ".pcm",
    ".mp4",
    ".mkv",
    ".mov",
    ".avi",
    ".m4v",
    ".mp3",
    ".wav",
    ".aiff",
    ".flac",
    ".ogg",
    ".opus",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".sqlite",
    ".db",
    ".onnx",
    ".pth",
    ".pt",
    ".safetensors",
}

TOKEN_PATTERNS = {
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    "Private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "OpenAI-style secret": re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
}

PRIVATE_PATH_PATTERNS = {
    "macOS user path": re.compile(r"/Users/(?P<user>[A-Za-z0-9._-]+)/"),
    "Linux user path": re.compile(r"/home/(?P<user>[A-Za-z0-9._-]+)/"),
    "Windows user path": re.compile(r"[A-Za-z]:\\Users\\(?P<user>[^\\]+)\\"),
}

PLACEHOLDER_USERS = {"user", "username", "name", "example", "..."}


def is_example_env(path: Path) -> bool:
    return path.name == ".env.example"


def iter_public_files(root: Path):
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        if any(part in IGNORED_GENERATED_DIRECTORY_NAMES for part in relative.parts):
            continue
        if path.is_symlink():
            yield path
            continue
        if any(
            part in BLOCKED_DIRECTORY_NAMES | IGNORED_GENERATED_DIRECTORY_NAMES
            for part in relative.parts[:-1]
        ):
            continue
        if path.is_file():
            yield path


def text_violations(path: Path, root: Path) -> list[str]:
    relative = path.relative_to(root)
    if path.stat().st_size > 2 * 1024 * 1024:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [f"binary file is not allowed: {relative}"]

    violations = []
    for label, pattern in TOKEN_PATTERNS.items():
        if pattern.search(text):
            violations.append(f"{label} detected in {relative}")

    for label, pattern in PRIVATE_PATH_PATTERNS.items():
        for match in pattern.finditer(text):
            user = match.group("user").strip().lower()
            if user not in PLACEHOLDER_USERS and not user.startswith("<"):
                violations.append(f"{label} detected in {relative}")
                break
    return violations


def scan_repository(root: Path) -> list[str]:
    root = root.expanduser().resolve()
    violations: list[str] = []

    for path in iter_public_files(root):
        relative = path.relative_to(root)
        if path.is_symlink():
            target = path.resolve()
            if root not in target.parents and target != root:
                violations.append(f"symlink points outside repository: {relative}")
            continue

        if path.name.startswith(".env") and not is_example_env(path):
            violations.append(f"credential file is not allowed: {relative}")
        if path.suffix.lower() in BLOCKED_SUFFIXES:
            violations.append(f"media/model/database file is not allowed: {relative}")
        if path.stat().st_size > MAX_PUBLIC_FILE_BYTES:
            violations.append(f"file exceeds 5 MiB public limit: {relative}")
        violations.extend(text_violations(path, root))

    for directory in sorted(root.rglob("*")):
        relative = directory.relative_to(root)
        if not directory.is_dir() or ".git" in relative.parts:
            continue
        if any(part in IGNORED_GENERATED_DIRECTORY_NAMES for part in relative.parts):
            continue
        if directory.name in BLOCKED_DIRECTORY_NAMES:
            violations.append(f"generated or vendored directory is not allowed: {relative}")

    return sorted(set(violations))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=REPOSITORY_ROOT)
    return parser


def main() -> int:
    root = build_parser().parse_args().root
    violations = scan_repository(root)
    if violations:
        print("Public repository safety check failed:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
        return 1
    print(f"Public repository safety check passed: {root.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
