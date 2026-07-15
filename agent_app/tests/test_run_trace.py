import json

import pytest

from agent_app.services.run_trace import RunTraceWriter


def test_trace_writer_saves_routing_and_redacts_secrets(tmp_path):
    writer = RunTraceWriter(tmp_path)

    path = writer.write_json(
        "routing_decision.json",
        {
            "route": "generic_cumcm_contract_workflow",
            "api_key": "sk-secret-value",
            "nested": {"authorization": "Bearer token-value"},
        },
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["route"] == "generic_cumcm_contract_workflow"
    assert payload["api_key"] == "[REDACTED]"
    assert payload["nested"]["authorization"] == "[REDACTED]"


def test_trace_writer_appends_stage_events(tmp_path):
    writer = RunTraceWriter(tmp_path)

    writer.append_event("plan_model", {"status": "started"})
    writer.append_event("plan_model", {"status": "completed"})

    lines = (tmp_path / "trace" / "stage_events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["stage"] == "plan_model"
    assert json.loads(lines[1])["payload"]["status"] == "completed"


def test_trace_writer_rejects_symlink_escape(tmp_path):
    writer = RunTraceWriter(tmp_path)
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    link_path = tmp_path / "trace" / "link"
    link_path.parent.mkdir()
    try:
        link_path.symlink_to(outside_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are not supported: {exc}")

    with pytest.raises(ValueError):
        writer.write_text("link/escaped.txt", "outside write")

    assert not (outside_dir / "escaped.txt").exists()


def test_trace_writer_rejects_final_path_symlink_escape(tmp_path):
    writer = RunTraceWriter(tmp_path)
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("original", encoding="utf-8")
    linked_file = tmp_path / "trace" / "linked.txt"
    linked_file.parent.mkdir()
    try:
        linked_file.symlink_to(outside_file)
    except OSError as exc:
        pytest.skip(f"file symlinks are not supported: {exc}")

    with pytest.raises(ValueError):
        writer.write_text("linked.txt", "new")

    assert outside_file.read_text(encoding="utf-8") == "original"


def test_trace_writer_redacts_common_secret_key_variants(tmp_path):
    writer = RunTraceWriter(tmp_path)

    path = writer.write_json(
        "secrets.json",
        {
            "password": "p-value",
            "client_secret": "client-value",
            "refresh_token": "refresh-value",
            "id_token": "id-value",
            "private_key": "private-value",
            "session_cookie": "cookie-value",
            "x-api-key": "api-value",
            "openai_api_key": "openai-value",
            "nested": [{"label": "visible", "service-token": "service-value"}],
        },
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["password"] == "[REDACTED]"
    assert payload["client_secret"] == "[REDACTED]"
    assert payload["refresh_token"] == "[REDACTED]"
    assert payload["id_token"] == "[REDACTED]"
    assert payload["private_key"] == "[REDACTED]"
    assert payload["session_cookie"] == "[REDACTED]"
    assert payload["x-api-key"] == "[REDACTED]"
    assert payload["openai_api_key"] == "[REDACTED]"
    assert payload["nested"][0]["label"] == "visible"
    assert payload["nested"][0]["service-token"] == "[REDACTED]"
