import json

import pytest

from movie_workflow.io import checked_lock, read_state, sha256


def test_relative_artifact_and_hash(tmp_path):
    path = tmp_path / "locked.json"
    path.write_text("{}")
    state = {
        "locks": {
            "script": {
                "artifact": path.name,
                "sha256": sha256(path),
                "status": "SCRIPT_LOCKED",
                "user_confirmed": True,
            }
        }
    }
    assert checked_lock(tmp_path, state, "script", confirmed=True) == path
    path.write_text("changed")
    with pytest.raises(ValueError, match="sha256"):
        checked_lock(tmp_path, state, "script", confirmed=True)


def test_conflicting_reference_rejected(tmp_path):
    state = {"locks": {"voice": {"artifact": "one", "path": "two"}}}
    with pytest.raises(ValueError, match="conflict"):
        checked_lock(tmp_path, state, "voice")


def test_state_path_and_pause(tmp_path):
    (tmp_path / "project.json").write_text(
        json.dumps({"paths": {"production_state": "state.json"}})
    )
    (tmp_path / "state.json").write_text(json.dumps({"workflow_control": {"status": "PAUSED"}}))
    with pytest.raises(ValueError, match="PAUSED"):
        read_state(tmp_path, active=True)
