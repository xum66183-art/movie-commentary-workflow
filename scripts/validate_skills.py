#!/usr/bin/env python3
"""Validate skill names, required metadata, UI metadata, and relative Markdown links."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPOSITORY_ROOT / ".codex" / "skills"
NAME_PATTERN = re.compile(r"^[a-z0-9-]{1,64}$")
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    try:
        raw = text.split("---\n", 2)[1]
    except IndexError:
        return {}
    values: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def validate_skill(skill_dir: Path) -> list[str]:
    errors: list[str] = []
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        return [f"{skill_dir.name}: missing SKILL.md"]

    text = skill_file.read_text(encoding="utf-8")
    metadata = frontmatter(text)
    name = metadata.get("name", "")
    description = metadata.get("description", "")
    if name != skill_dir.name:
        errors.append(f"{skill_dir.name}: frontmatter name must match directory")
    if not NAME_PATTERN.fullmatch(name):
        errors.append(f"{skill_dir.name}: invalid skill name")
    if not description:
        errors.append(f"{skill_dir.name}: missing description")

    agent_file = skill_dir / "agents" / "openai.yaml"
    if not agent_file.is_file():
        errors.append(f"{skill_dir.name}: missing agents/openai.yaml")
    else:
        agent_text = agent_file.read_text(encoding="utf-8")
        for field in ("display_name:", "short_description:", "default_prompt:"):
            if field not in agent_text:
                errors.append(f"{skill_dir.name}: openai.yaml missing {field[:-1]}")
        if f"${name}" not in agent_text:
            errors.append(f"{skill_dir.name}: default_prompt must reference ${name}")

    for target in MARKDOWN_LINK_PATTERN.findall(text):
        if "://" in target or target.startswith("#"):
            continue
        clean_target = target.split("#", 1)[0]
        if clean_target and not (skill_dir / clean_target).exists():
            errors.append(f"{skill_dir.name}: broken relative link {target}")
    return errors


def validate_skills(skills_root: Path = SKILLS_ROOT) -> list[str]:
    errors = []
    for skill_dir in sorted(path for path in skills_root.iterdir() if path.is_dir()):
        errors.extend(validate_skill(skill_dir))
    if not list(path for path in skills_root.iterdir() if path.is_dir()):
        errors.append("no skills found")
    return errors


def main() -> int:
    errors = validate_skills()
    if errors:
        print("Skill validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Skill validation passed: {SKILLS_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
