"""Observable integration checks: coordinates, subtitles, evidence, caching and failures."""

import importlib.util
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path

import jsonschema
import pytest
import requests

WORKFLOW_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = WORKFLOW_ROOT / ".codex/skills/movie-index/scripts/movie_index.py"
spec = importlib.util.spec_from_file_location("local_movie_index", SCRIPT)
index = importlib.util.module_from_spec(spec)
spec.loader.exec_module(index)


@pytest.fixture(scope="session")
def fixture_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("movie-index")
    video = root / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=red:s=320x180:r=25:d=2",
            "-f",
            "lavfi",
            "-i",
            "color=blue:s=320x180:r=25:d=2",
            "-f",
            "lavfi",
            "-i",
            "color=green:s=320x180:r=25:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=6",
            "-filter_complex",
            "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
            "-map",
            "[v]",
            "-map",
            "3:a",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(video),
        ],
        check=True,
    )
    subtitle = root / "source.srt"
    subtitle.write_text(
        "1\n00:00:00,000 --> 00:00:01,500\n红色房间\n\n"
        "2\n00:00:01,500 --> 00:00:02,500\n我转身\n\n"
        "3\n00:00:02,500 --> 00:00:04,000\n蓝色天空\n\n"
        "4\n00:00:04,000 --> 00:00:06,000\n绿色草地\n",
        encoding="utf-8",
    )
    project = root / "prepared"
    assert (
        index.main(
            [
                "prepare",
                "--project",
                str(project),
                "--video",
                str(video),
                "--subtitle",
                str(subtitle),
                "--unit-seconds",
                "1",
                "--title",
                "合成索引测试",
            ]
        )
        == 0
    )
    return root


@pytest.fixture
def project(fixture_root, tmp_path):
    target = tmp_path / "project"
    shutil.copytree(fixture_root / "prepared", target)
    manifest = index.read_json(target / "project.json")
    manifest["canonical_root"] = str(target)
    index.write_json(target / "project.json", manifest)
    return target


@pytest.fixture
def api(monkeypatch):
    key = "test-credential-not-real"
    monkeypatch.setattr(index, "config", lambda: (key, index.DEFAULT_BASE, index.MODELS[0]))
    calls = []
    facts = {
        "description": "红色测试画面",
        "people": [],
        "locations": [],
        "actions": [],
        "objects": ["红色色块"],
        "keywords": ["红色"],
        "uncertainties": ["稀疏帧无法确认连续动作"],
    }

    def post(url, **kwargs):
        calls.append(kwargs["json"])
        return response(
            200,
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(facts, ensure_ascii=False)},
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            },
        )

    monkeypatch.setattr(index.requests, "post", post)
    return calls, facts, key


def response(status, payload):
    class Response:
        status_code = status

        def json(self):
            return payload

    return Response()


def test_named_object_evidence_preserved_and_unknown_variant_rejected():
    facts = {
        "description": "道具",
        "people": [],
        "locations": [],
        "actions": [],
        "objects": [{"name": "刀", "evidence": "第二帧金属反光"}],
        "keywords": [],
        "uncertainties": [],
    }
    payload = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(facts)}}]}
    assert index.normalize(payload)["objects"] == ["刀；证据：第二帧金属反光"]
    facts["objects"][0].update(description="刀刃", confidence=0.8)
    payload["choices"][0]["message"]["content"] = json.dumps(facts)
    assert json.loads(index.normalize(payload)["objects"][0]) == facts["objects"][0]
    facts["objects"][0]["appearance"] = "深色粗糙表面"
    payload["choices"][0]["message"]["content"] = json.dumps(facts)
    assert json.loads(index.normalize(payload)["objects"][0]) == facts["objects"][0]
    facts["objects"][0]["inferred_motive"] = "伤害"
    payload["choices"][0]["message"]["content"] = json.dumps(facts)
    with pytest.raises(jsonschema.ValidationError):
        index.normalize(payload)


def test_failed_raw_response_recovers_without_paid_retry(project, api, monkeypatch):
    calls, facts, _ = api
    facts["objects"] = [{"name": "红色色块", "evidence": "所有三帧"}]
    original = index.normalize

    def old_parser(payload):
        value = json.loads(payload["choices"][0]["message"]["content"])
        jsonschema.Draft202012Validator(index.FACT_SCHEMA).validate(value)
        return value

    monkeypatch.setattr(index, "normalize", old_parser)
    assert analyze(project, "--max-units", "1") == 2
    monkeypatch.setattr(index, "normalize", original)
    with sqlite3.connect(project / "database/vision.sqlite") as db:
        unit = db.execute("SELECT unit_id FROM observations").fetchone()[0]
    assert analyze(project, "--unit-id", unit) == 0
    assert len(calls) == 1
    with sqlite3.connect(project / "database/vision.sqlite") as db:
        assert db.execute("SELECT status FROM observations").fetchone()[0] == "success"
        assert db.execute("SELECT count(*) FROM attempts").fetchone()[0] == 1
        assert db.execute("SELECT status FROM attempts").fetchone()[0] == "failed"
    history = index.read_json(project / "vision/normalization-recovery.json")
    assert history[0]["unit_id"] == unit


def analyze(project, *extra):
    return index.main(["analyze", "--project", str(project), *extra])


def test_media_coordinates_subtitles_and_contracts(project):
    assert index.verify(project) == []
    summary = index.read_json(project / "analysis/summary.json")
    assert summary["duration_ms"] == 6000
    assert summary["shot_count"] == 3
    assert summary["visual_unit_count"] == 6
    with sqlite3.connect(project / "database/shots.sqlite") as db:
        assert db.execute("SELECT start_ms,end_ms FROM shots ORDER BY ordinal").fetchall() == [
            (0, 2000),
            (2000, 4000),
            (4000, 6000),
        ]
        # A subtitle crossing the cut is attached to both shots, not just its midpoint.
        assert (
            db.execute("SELECT count(*) FROM shot_subtitles WHERE subtitle_id=2").fetchone()[0] == 2
        )
    for name, file in [("project", "project.json"), ("state", "production/state.json")]:
        schema = index.read_json(WORKFLOW_ROOT / f"schemas/{name}.schema.json")
        jsonschema.Draft202012Validator(schema).validate(index.read_json(project / file))
    assert index.read_json(project / "production/state.json")["current_status"] == "PROJECT_CREATED"


def test_ass_commas_and_time_edges(tmp_path):
    path = tmp_path / "subtitle.ass"
    path.write_text(
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        "Dialogue: 0,0:00:01.23,0:00:02.45,Default,,0,0,0,,{\\b1}你好,世界\\N第二行\n"
    )
    rows = index.parse_subtitles(path)
    assert rows[0]["start_ms"] == 1230 and rows[0]["end_ms"] == 2450
    assert rows[0]["text"] == "你好,世界\n第二行"
    assert index.overlap(rows, 2450, 3000) == []


def test_resume_and_model_comparison_preserve_observations(project, api):
    calls, _, _ = api
    assert analyze(project, "--max-units", "2") == 0
    assert len(calls) == 2
    assert analyze(project, "--max-units", "2") == 0
    assert len(calls) == 4  # It advances to two new units.
    assert analyze(project, "--max-units", "0") == 0
    assert len(calls) == 6
    assert analyze(project, "--max-units", "0") == 0
    assert len(calls) == 6  # Successful results are reused without another request.
    assert analyze(project, "--model", "qwen3-vl-plus", "--unit-id", "shot-000001-unit-001") == 0
    with sqlite3.connect(project / "database/vision.sqlite") as db:
        assert (
            db.execute("SELECT count(*) FROM observations WHERE status='success'").fetchone()[0]
            == 7
        )
    matches = index.search(project, "红色", 5)
    assert matches and matches[0]["id"] == "shot-000001"
    assert "我转身" not in json.dumps(calls)  # Subtitles cannot contaminate visual observations.
    assert index.read_json(project / "production/state.json")["locks"]["index"] is None


def test_truncated_or_malformed_output_not_cached(project, api, monkeypatch):
    calls, _, _ = api
    original = index.requests.post
    monkeypatch.setattr(
        index.requests,
        "post",
        lambda *a, **kw: response(
            200,
            {
                "choices": [{"finish_reason": "length", "message": {"content": "{"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 1600},
            },
        ),
    )
    assert analyze(project, "--max-units", "1") == 2
    assert index.refresh_report(project)["units_with_success"] == 0
    monkeypatch.setattr(index.requests, "post", original)
    assert analyze(project, "--max-units", "1") == 0
    assert len(calls) == 1
    summary = index.refresh_report(project)
    assert summary["api_attempts"] == 2 and summary["known_estimated_cost_yuan"] > 0


def test_auth_failure_stops_batch_and_redacts_secret(project, api, monkeypatch):
    _, _, key = api
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        return response(401, {"error": {"code": "invalid_api_key", "message": key}})

    monkeypatch.setattr(index.requests, "post", fail)
    assert analyze(project, "--max-units", "20") == 2
    assert len(calls) == 1
    raw = next((project / "vision/results").rglob("*.json")).read_text()
    assert key not in raw and "[REDACTED]" in raw


def test_billing_failure_stops_remaining_units(project, api, monkeypatch):
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        return response(400, {"error": {"code": "Arrearage"}})

    monkeypatch.setattr(index.requests, "post", fail)
    assert analyze(project, "--max-units", "20") == 2
    assert len(calls) == 1


def test_retry_and_unknown_usage_are_bounded(project, api, monkeypatch):
    calls, _, _ = api
    original = index.requests.post
    responses = [response(429, {"error": {"code": "rate_limit"}})]

    def throttle(*args, **kwargs):
        return responses.pop() if responses else original(*args, **kwargs)

    monkeypatch.setattr(index.requests, "post", throttle)
    monkeypatch.setattr(index.time, "sleep", lambda _: None)
    assert analyze(project, "--max-units", "1") == 0
    assert len(calls) == 1
    summary = index.refresh_report(project)
    assert summary["api_attempts"] == 2 and summary["attempts_without_usage"] == 1
    timeout_calls = []

    def timeout(*args, **kwargs):
        timeout_calls.append(1)
        raise requests.Timeout()

    monkeypatch.setattr(index.requests, "post", timeout)
    assert analyze(project, "--unit-id", "shot-000002-unit-001", "--max-attempts", "2") == 2
    assert len(timeout_calls) == 2


def test_corrupt_frame_prevents_api_call(project, api):
    calls, _, _ = api
    frame = next((project / "keyframes").glob("shot-000001-unit-001-*.jpg"))
    frame.write_bytes(b"broken image")
    assert analyze(project, "--max-units", "1") == 2
    assert calls == []
    assert index.verify(project)


def test_subtitle_search_and_manual_correction(project):
    assert index.search(project, "我转身", 5)[0]["id"] in {"shot-000001", "shot-000002"}
    row = {
        "target_id": "shot-000003-unit-001",
        "corrected_facts": "黑色手机",
        "evidence": {"source_time_ms": 4200},
        "author": "director",
        "created_at": index.now(),
        "reason": "原片确认",
    }
    index.write_json(project / "database/retrieval_overrides.json", {"overrides": [row]})
    found = index.search(project, "黑色手机", 5)
    assert found[0]["id"] == "shot-000003"
    assert found[0]["matches"][0]["signal"] == "human_override"


def test_evidence_keeps_source_audio_and_exact_interval(project):
    assert (
        index.main(
            [
                "evidence",
                "--project",
                str(project),
                "shot-000002-unit-001",
                "--padding-ms",
                "500",
            ]
        )
        == 0
    )
    root = project / "evidence/shot-000002-unit-001/pad-500"
    data = index.read_json(root / "evidence.json")
    assert (data["source_start_ms"], data["source_end_ms"]) == (1500, 3500)
    media, duration = index.probe(root / "clip.mp4")
    assert abs(duration - 2000) <= 50
    assert any(s["codec_type"] == "audio" for s in media["streams"])
    assert len(list(root.glob("frame-*.jpg"))) == 3
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(root / "clip.mp4"), "-f", "null", "-"],
        check=True,
    )


def test_credential_destination_and_output_path_guards(monkeypatch, tmp_path):
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://example.invalid/compatible-mode/v1")
    with pytest.raises(ValueError):
        index.config()
    with pytest.raises(ValueError):
        index.project_root(WORKFLOW_ROOT / "repository/film")
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    link = tmp_path / "escape"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        index.artifact(tmp_path, "escape/leak.json")


def test_database_coordinate_drift_detected(project):
    with sqlite3.connect(project / "database/vision.sqlite") as db:
        db.execute("UPDATE units SET start_ms=123 WHERE id='shot-000001-unit-001'")
    assert any("视觉数据库坐标" in error for error in index.verify(project))


def test_missing_usage_not_mistaken_for_free_call(project, api, monkeypatch):
    _, facts, _ = api
    monkeypatch.setattr(
        index.requests,
        "post",
        lambda *a, **kw: response(
            200,
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(facts, ensure_ascii=False)},
                    }
                ],
                "usage": None,
            },
        ),
    )
    assert analyze(project, "--max-units", "1") == 0
    summary = index.refresh_report(project)
    assert summary["api_attempts"] == 1 and summary["attempts_without_usage"] == 1


def test_analysis_proxy_keeps_original_coordinates_and_evidence(fixture_root, tmp_path):
    proxy = tmp_path / "proxy.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(fixture_root / "source.mp4"),
            "-vf",
            "scale=160:90,fps=15",
            "-an",
            "-c:v",
            "libx264",
            str(proxy),
        ],
        check=True,
    )
    prepared = tmp_path / "proxy-index"
    assert (
        index.main(
            [
                "prepare",
                "--project",
                str(prepared),
                "--video",
                str(fixture_root / "source.mp4"),
                "--analysis-proxy",
                str(proxy),
                "--subtitle",
                str(fixture_root / "source.srt"),
            ]
        )
        == 0
    )
    manifest = index.read_json(prepared / "project.json")
    assert manifest["source"]["video"]["path"] == str(fixture_root / "source.mp4")
    assert manifest["source"]["analysis_proxy"]["path"] == str(proxy)
    shots = [json.loads(s) for s in (prepared / "analysis/shots.jsonl").read_text().splitlines()]
    assert len(shots) == 3
    assert shots[1]["start_ms"] == 2000
    assert shots[1]["start_frame"] == 50  # Original 25fps, not proxy 15fps.
    assert index.verify(prepared) == []
    assert (
        index.main(["evidence", "--project", str(prepared), "shot-000002", "--padding-ms", "0"])
        == 0
    )
    clip = prepared / "evidence/shot-000002/pad-0/clip.mp4"
    media, _ = index.probe(clip)
    video = next(s for s in media["streams"] if s["codec_type"] == "video")
    assert video["width"] == 320  # Evidence still comes from original, not 160px proxy.
    assert any(s["codec_type"] == "audio" for s in media["streams"])
    with proxy.open("ab") as f:
        f.write(b"changed")
    with pytest.raises(ValueError, match="analysis_proxy"):
        index.assert_sources(prepared)


def test_wrong_length_proxy_is_rejected(fixture_root, tmp_path):
    proxy = tmp_path / "trimmed-proxy.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(fixture_root / "source.mp4"),
            "-t",
            "3",
            "-an",
            "-c:v",
            "libx264",
            str(proxy),
        ],
        check=True,
    )
    prepared = tmp_path / "bad-proxy-index"
    assert (
        index.main(
            [
                "prepare",
                "--project",
                str(prepared),
                "--video",
                str(fixture_root / "source.mp4"),
                "--analysis-proxy",
                str(proxy),
            ]
        )
        == 2
    )
    assert not (prepared / "analysis/summary.json").exists()


def test_parallel_analysis_keeps_unique_attempts_and_reuses_cache(project, api):
    calls, _, _ = api
    assert analyze(project, "--workers", "3", "--max-units", "4") == 0
    assert len(calls) == 4
    assert analyze(project, "--workers", "3", "--max-units", "4") == 0
    assert len(calls) == 6
    assert analyze(project, "--workers", "3", "--max-units", "4") == 0
    assert len(calls) == 6
    summary = index.refresh_report(project)
    assert summary["units_with_success"] == 6
    assert summary["api_attempts"] == 6
    assert summary["prompt_tokens"] == 600
    assert summary["completion_tokens"] == 300
    with sqlite3.connect(project / "database/vision.sqlite") as db:
        assert db.execute("SELECT count(DISTINCT cache_key) FROM attempts").fetchone()[0] == 6
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
