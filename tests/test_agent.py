# -*- coding: utf-8 -*-
from app.engine import agent


def test_agent_status_never_exposes_api_key(monkeypatch, tmp_path):
    monkeypatch.setattr(agent, "agent_cfg", lambda: {"api_key_file": "app/agent_key.local", "base_url": "https://example.test/v1"})
    monkeypatch.setattr(agent, "ROOT", tmp_path)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "agent_key.local").write_text("secret-value", encoding="utf-8")
    monkeypatch.delenv("SENSENOVA_API_KEY", raising=False)
    status = agent.agent_status()
    assert status["configured"] is True
    assert status["key_source"] == "local_file"
    assert "secret" not in repr(status)


def test_agent_status_prefers_environment_key(monkeypatch, tmp_path):
    monkeypatch.setattr(agent, "agent_cfg", lambda: {"api_key_file": "app/no-file"})
    monkeypatch.setattr(agent, "ROOT", tmp_path)
    monkeypatch.setenv("SENSENOVA_API_KEY", "environment-secret")
    status = agent.agent_status()
    assert status["configured"] is True
    assert status["key_source"] == "environment"
    assert "environment-secret" not in repr(status)
