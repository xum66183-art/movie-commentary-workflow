"""Offline tests may mock adapters, but must never contact real cloud services."""

import pytest
import requests


@pytest.fixture(autouse=True)
def forbid_live_http(monkeypatch):
    def stop(*args, **kwargs):
        raise AssertionError("Live HTTP is forbidden in tests; mock the provider")

    monkeypatch.setattr(requests.sessions.Session, "send", stop)
