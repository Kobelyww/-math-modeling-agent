import pytest

from agent_app.services.deepseek_generation import DeepSeekGenerationService


class FakeChatModel:
    def __init__(self, content):
        self.content = content
        self.messages = []

    def invoke(self, messages):
        self.messages.append(messages)
        return type("Msg", (), {"content": self.content})()


def test_generate_json_parses_model_response():
    service = DeepSeekGenerationService(FakeChatModel('{"selected_model":"binomial"}'))

    result = service.generate_json("planner", [{"role": "user", "content": "plan"}])

    assert result == {"selected_model": "binomial"}


def test_generate_markdown_returns_text():
    service = DeepSeekGenerationService(FakeChatModel("# Section\n\nText"))

    result = service.generate_markdown("writer", [{"role": "user", "content": "write"}])

    assert result.startswith("# Section")


def test_generate_json_strips_fenced_json():
    service = DeepSeekGenerationService(FakeChatModel('```json\n{"ok": true}\n```'))

    result = service.generate_json("planner", [{"role": "user", "content": "plan"}])

    assert result == {"ok": True}


def test_generate_json_strips_plain_fenced_json():
    service = DeepSeekGenerationService(FakeChatModel('```\n{"ok": true}\n```'))

    result = service.generate_json("planner", [{"role": "user", "content": "plan"}])

    assert result == {"ok": True}


def test_generate_markdown_accepts_plain_string_response():
    class PlainStringModel:
        def invoke(self, messages):
            return "# Plain"

    service = DeepSeekGenerationService(PlainStringModel())

    result = service.generate_markdown("writer", [{"role": "user", "content": "write"}])

    assert result == "# Plain"


def test_generate_json_raises_clear_error_for_invalid_json():
    service = DeepSeekGenerationService(FakeChatModel("not-json"))

    with pytest.raises(ValueError, match="planner.*JSON"):
        service.generate_json("planner", [{"role": "user", "content": "plan"}])


def test_generate_json_does_not_mutate_messages():
    messages = [{"role": "user", "content": "plan"}]
    service = DeepSeekGenerationService(FakeChatModel('{"ok": true}'))

    service.generate_json("planner", messages)

    assert messages == [{"role": "user", "content": "plan"}]
