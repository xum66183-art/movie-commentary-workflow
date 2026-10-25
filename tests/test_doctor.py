import json

from movie_workflow.doctor import report


def test_config_presence_never_exposes_values(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    config = tmp_path / ".env"
    config.write_text('DASHSCOPE_API_KEY="fake-private-value"\n')
    result = report(config=config, provider="qwen")
    assert result["selected_provider_configured"] is True
    assert "fake-private-value" not in json.dumps(result)
    assert result["api_credentials_verified"] is False and result["network_calls"] == 0
