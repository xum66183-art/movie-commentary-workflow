#!/usr/bin/env python3
"""Run the bundled index skill from a source checkout."""

from pathlib import Path
from runpy import run_path

if __name__ == "__main__":
    run_path(
        str(
            Path(__file__).resolve().parents[1] / ".codex/skills/movie-index/scripts/movie_index.py"
        ),
        run_name="__main__",
    )
