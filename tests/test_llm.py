from types import SimpleNamespace

import pytest

from myata.brain.llm import LLMError, OllamaChat
from myata.config import LlmConfig


def ollama_response(content="", calls=()):
    tool_calls = [
        SimpleNamespace(function=SimpleNamespace(name=name, arguments=args)) for name, args in calls
    ]
    return SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls or None))


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.kwargs = response, error, None

    def chat(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


def test_request_and_tool_calls():
    client = FakeClient(ollama_response(calls=[("web_search", '{"query": "котики"}')]))
    reply = OllamaChat(LlmConfig(), client).chat([{"role": "user", "content": "x"}], [{"t": 1}])
    assert reply.tool_calls[0].name == "web_search"
    assert reply.tool_calls[0].arguments == {"query": "котики"}  # JSON string is parsed
    assert client.kwargs["model"] == "qwen3.5:4b"
    assert client.kwargs["think"] is False
    assert client.kwargs["options"]["num_ctx"] == 4096
    assert client.kwargs["options"]["num_predict"] == 256


def test_text_answer_without_tools():
    client = FakeClient(ollama_response(content="Привет"))
    reply = OllamaChat(LlmConfig(), client).chat([], [])
    assert reply.content == "Привет" and reply.tool_calls == ()
    assert "tools" not in client.kwargs


def test_errors_become_llm_error():
    client = FakeClient(error=ConnectionError("Failed to connect to Ollama"))
    with pytest.raises(LLMError):
        OllamaChat(LlmConfig(), client).chat([], [])


def test_warm_up_never_raises():
    assert OllamaChat(LlmConfig(), FakeClient(error=ConnectionError("down"))).warm_up() is None
    assert OllamaChat(LlmConfig(), FakeClient(ollama_response())).warm_up() is not None
