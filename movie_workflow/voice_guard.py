"""Bounded request plans and mutual exclusion; no service calls in this module."""

from __future__ import annotations

import functools
import json
import math
import re
from contextlib import ExitStack
from pathlib import Path

from .io import file_lock, sha256


def guarded_operation(function):
    @functools.wraps(function)
    def run(args):
        try:
            with ExitStack() as stack:
                if getattr(args, "project", None):
                    stack.enter_context(file_lock(Path(args.project), ".narration.lock"))
                stack.enter_context(file_lock(Path(args.operation_dir)))
                return function(args)
        except (OSError, RuntimeError, ValueError) as exc:
            print(json.dumps({"status": "STOPPED", "reason": str(exc)}))
            return 1

    return run


def guarded_part(function):
    @functools.wraps(function)
    def run(folder, *args, **kwargs):
        with file_lock(Path(folder)):
            return function(folder, *args, **kwargs)

    return run


def billing_characters(text: str) -> int:
    # Adapter estimate only; billing remains subject to the provider's rules.
    return len(text) + len(re.findall(r"[\u3400-\u9fff]", text))


def request_budget(plan, folder, args, *, voice=None, model=None):
    pending = []
    for row in plan:
        meta = Path(folder) / f"part-{row['id']:03d}" / "metadata.json"
        saved = json.loads(meta.read_text()) if meta.is_file() else {}
        if saved and saved.get("status") not in {"PREPARED", "READY", "SYNTHESIZED"}:
            raise ValueError("unresolved/rejected submission must be reconciled before continuing")
        if saved and any(
            saved.get(key) != value
            for key, value in (
                ("text_sha256", row.get("text_sha256")),
                ("voice_id", voice),
                ("model", model),
            )
            if value is not None
        ):
            raise ValueError("cached paragraph identity mismatch before submission")
        if saved.get("status") == "READY" and voice is not None:
            if not saved.get("audio") or sha256(Path(saved["audio"])) != saved.get("audio_sha256"):
                raise ValueError("cached audio fingerprint mismatch before submission")
        if saved.get("status") not in {"READY", "SYNTHESIZED"}:
            pending.append(row)
    count = len(pending)
    chars = sum(billing_characters(row["text"]) for row in pending)
    maximum = getattr(args, "max_new_requests", 20)
    max_chars = getattr(args, "max_billable_characters", 20000)
    rate = getattr(args, "price_per_10k", None)
    cap = getattr(args, "max_estimated_cost", None)
    if maximum < 0 or max_chars < 0 or count > maximum or chars > max_chars:
        raise ValueError("new request/character budget exceeded before submission")
    if any(v is not None and (not math.isfinite(v) or v < 0) for v in (rate, cap)):
        raise ValueError("cost parameters must be finite and non-negative")
    cost = 0.0 if chars == 0 else None if rate is None else chars * rate / 10000
    if cap is not None and (cost is None or cost > cap):
        raise ValueError("estimated cost budget requires an explicit rate and sufficient allowance")
    return {
        "new_requests": count,
        "estimated_billable_characters": chars,
        "price_per_10k": rate,
        "estimated_cost": cost,
        "estimate_is_invoice": False,
    }


def legacy_operation(args, execute):
    """Serialize an output workflow and refuse to replay an unresolved paid outcome."""
    import hashlib

    from .io import sha256, write_json

    output = args.output.resolve()
    journal = output.with_name(output.name + ".request.json")
    identity = {
        key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()
    }
    for key in ("reference", "text_file", "reference_text_file"):
        path = getattr(args, key, None)
        if path:
            identity[key + "_sha256"] = sha256(path)
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    with file_lock(output.parent, "." + output.name + ".lock"):
        if journal.exists():
            saved = json.loads(journal.read_text())
            if saved["identity"] != digest or saved["status"] != "READY":
                raise ValueError("existing request differs or its outcome needs reconciliation")
            for item in saved["outputs"]:
                if sha256(Path(item["path"])) != item["sha256"]:
                    raise ValueError("existing output fingerprint mismatch")
            print(json.dumps({"status": "CACHED", "new_output_workflows": 0}))
            return 0
        if output.exists():
            raise ValueError("output already exists without a receipt; select a new version")
        saved = {"identity": digest, "status": "SUBMITTED", "outputs": []}
        write_json(journal, saved)
        try:
            result = execute(args)
            if result == 0 and output.is_file():
                paths = [output] + [
                    getattr(args, key, None) for key in ("output_srt", "timestamp_json", "metadata")
                ]
                saved.update(
                    status="READY",
                    outputs=[
                        {"path": str(p.resolve()), "sha256": sha256(p)}
                        for p in paths
                        if p and p.is_file()
                    ],
                )
            else:
                saved["status"] = "OUTCOME_UNKNOWN"
            return result
        finally:
            if saved["status"] == "SUBMITTED":
                saved["status"] = "OUTCOME_UNKNOWN"
            write_json(journal, saved)
