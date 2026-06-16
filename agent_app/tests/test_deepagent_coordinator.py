from __future__ import annotations


def test_create_competition_paper_agent_uses_current_deepagents_api(monkeypatch, tmp_path):
    from agent_app.deepagent import coordinator
    from agent_app.services.run_store import RunStore

    captured = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("deepagents.create_deep_agent", fake_create_deep_agent)

    result = coordinator.create_competition_paper_agent(
        llm=object(),
        run_store=RunStore(tmp_path),
    )

    assert result is not None
    assert "system_prompt" in captured
    assert "instructions" not in captured
    assert captured["tools"]
    assert captured["middleware"]
