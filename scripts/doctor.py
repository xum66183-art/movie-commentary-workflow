#!/usr/bin/env python3
"""Compatibility entry point for the installed workflow diagnostics."""

if __package__ in (None, ""):
    import _bootstrap  # noqa: F401

from movie_workflow.doctor import main

if __name__ == "__main__":
    raise SystemExit(main())
