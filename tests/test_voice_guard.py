import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from movie_workflow.io import file_lock
from movie_workflow.voice_guard import request_budget


def test_process_lock_blocks_second_process(tmp_path):
    with file_lock(tmp_path):
        child = subprocess.run(
            [
                sys.executable,
                "-c",
                "from pathlib import Path; from movie_workflow.io import file_lock;\n"
                "with file_lock(Path(__import__('sys').argv[1])): pass",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": os.getcwd()},
        )
    assert child.returncode != 0 and "already running" in child.stderr
    with file_lock(tmp_path):
        pass


def test_budget_counts_only_new_requests_and_stops_before_network(tmp_path):
    plan = [{"id": 1, "text": "第一段"}, {"id": 2, "text": "second"}]
    cached = tmp_path / "part-001"
    cached.mkdir()
    (cached / "metadata.json").write_text(json.dumps({"status": "READY"}))
    args = SimpleNamespace(max_new_requests=0)
    with pytest.raises(ValueError, match="budget"):
        request_budget(plan, tmp_path, args)
    args.max_new_requests = 1
    assert request_budget(plan, tmp_path, args)["new_requests"] == 1
    args.max_estimated_cost = 1
    with pytest.raises(ValueError, match="explicit rate"):
        request_budget(plan, tmp_path, args)


def test_legacy_output_cache_and_unknown_outcome(tmp_path):
    from movie_workflow.voice_guard import legacy_operation

    args = SimpleNamespace(output=tmp_path / "output.wav", provider="fake")
    calls = []

    def execute(options):
        calls.append(1)
        options.output.write_bytes(b"synthetic-audio")
        return 0

    assert legacy_operation(args, execute) == legacy_operation(args, execute) == 0
    assert len(calls) == 1
    args.output = tmp_path / "failed.wav"
    assert legacy_operation(args, lambda _: 1) == 1
    with pytest.raises(ValueError, match="reconciliation"):
        legacy_operation(args, execute)
    assert len(calls) == 1
