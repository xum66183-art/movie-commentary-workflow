import json
from pathlib import Path

import pytest

from movie_workflow.demo import build
from movie_workflow.io import sha256, write_json
from movie_workflow.render import load_plan, render


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    project = tmp_path_factory.mktemp("render") / "private-demo"
    result = build(project)
    assert result["real_api_calls"] == 0 and result["technical_pass"]
    assert not result["formal_verified"]
    return project


def change(project, kind, mutate):
    path = project / f"director/{kind}.json"
    data = json.loads(path.read_text())
    mutate(data)
    write_json(path, data)
    bundle = json.loads((project / "director/bundle.json").read_text())
    bundle[kind]["sha256"] = sha256(path)
    write_json(project / "director/bundle.json", bundle)
    state = json.loads((project / "production/state.json").read_text())
    state["locks"]["proxy_plan"]["sha256"] = sha256(project / "director/bundle.json")
    write_json(project / "production/state.json", state)


def clone(demo, tmp_path):
    import shutil

    target = tmp_path / "copy"
    shutil.copytree(demo, target)
    return target


def test_complete_demo_and_same_version_cache(demo):
    before = sha256(demo / "production/state.json")
    receipt = render(demo, demo / "render/proxy-v001")
    assert receipt["status"] == "READY" and receipt["state_changed"] is False
    assert sha256(demo / "production/state.json") == before


def test_gap_and_unsupported_effect_are_rejected(demo, tmp_path):
    project = clone(demo, tmp_path)
    change(project, "visual_edit", lambda p: p["clips"][1].update(timeline_start_ms=3100))
    with pytest.raises(ValueError, match="gap/overlap"):
        load_plan(project, "proxy")
    change(project, "visual_edit", lambda p: p["clips"][1].update(timeline_start_ms=3000, speed=2))
    with pytest.raises(ValueError, match="unsupported"):
        load_plan(project, "proxy")


def test_fingerprint_change_and_unapproved_final_are_rejected(demo, tmp_path):
    project = clone(demo, tmp_path)
    (project / "media/captions.srt").write_text("changed")
    with pytest.raises(ValueError, match="sha256"):
        load_plan(project, "proxy")
    with pytest.raises(ValueError, match="lock"):
        load_plan(project, "final")


def test_source_dialogue_requires_explicit_enable(demo, tmp_path):
    project = clone(demo, tmp_path)

    def mutate(plan):
        plan["events"] = [
            {
                "id": "source",
                "type": "source_dialogue",
                "start_ms": 0,
                "end_ms": 3000,
                "source": "media/source.mp4",
                "source_sha256": sha256(project / "media/source.mp4"),
                "source_start_ms": 0,
            }
        ]

    change(project, "audio_mix_plan", mutate)
    with pytest.raises(ValueError, match="explicitly enabled"):
        load_plan(project, "proxy")


def test_burn_subtitles_when_test_font_is_available(demo, tmp_path):
    font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if not font.is_file():
        pytest.skip("Linux reference font unavailable; macOS tools have a separate job")
    project = clone(demo, tmp_path)
    change(
        project,
        "visual_edit",
        lambda p: p["output"].update(subtitle_mode="burn", font_family="DejaVu Sans", font_size=20),
    )
    bundle = json.loads((project / "director/bundle.json").read_text())
    bundle["font"] = {"path": str(font), "sha256": sha256(font)}
    write_json(project / "director/bundle.json", bundle)
    state = json.loads((project / "production/state.json").read_text())
    state["locks"]["proxy_plan"]["sha256"] = sha256(project / "director/bundle.json")
    write_json(project / "production/state.json", state)
    assert render(project, project / "render/burn")["qa"]["full_decode"]


def test_final_requires_user_approval_and_preserves_state(demo, tmp_path):
    project = clone(demo, tmp_path)
    state_path = project / "production/state.json"
    state = json.loads(state_path.read_text())
    state["locks"]["director_plan"] = {
        **state["locks"]["proxy_plan"],
        "status": "DIRECTOR_PLAN_LOCKED",
        "user_confirmed": True,
    }
    write_json(state_path, state)
    with pytest.raises(ValueError, match="user_sample_approved"):
        load_plan(project, "final")
    state["user_sample_approved"] = True  # Synthetic fixture only, never a real adoption.
    write_json(state_path, state)
    before = sha256(state_path)
    assert render(project, project / "render/final-fixture", mode="final")["qa"]["full_decode"]
    assert sha256(state_path) == before


def test_clipping_rejected_without_rewriting_mix_intent(demo, tmp_path):
    project = clone(demo, tmp_path)
    change(project, "audio_mix_plan", lambda p: p["events"][0].update(gain_db=60))
    with pytest.raises(ValueError, match="full scale"):
        render(project, project / "render/clipping")
    assert not (project / "render/clipping/proxy.mp4").exists()
