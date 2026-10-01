"""Talking to a local LLM. Ollama is the only backend for now."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from myata.config import LlmConfig

log = logging.getLogger(__name__)

Message = Mapping[str, Any]
ToolSpec = Mapping[str, Any]


class LLMError(Exception):
    """The LLM server is down, the model is missing, or the request failed."""


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True)
class LLMReply:
    content: str
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)


class ChatModel(Protocol):
    def chat(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> LLMReply: ...

    def warm_up(self) -> float | None: ...


class OllamaChat:
    def __init__(self, config: LlmConfig, client: Any = None) -> None:
        if client is None:
            from ollama import Client

            client = Client(host=config.host, timeout=config.timeout_sec)
        self._client = client
        self._model = config.model
        self._think = config.think
        self._keep_alive = config.keep_alive
        self._timeout = config.timeout_sec
        self._options = {
            "temperature": config.temperature,
            "num_ctx": config.num_ctx,
            "num_predict": config.max_tokens,  # a looping model cannot hang Myata
        }

    def chat(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> LLMReply:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": list(messages),
            "options": self._options,
            "keep_alive": self._keep_alive,
        }
        if tools:
            kwargs["tools"] = list(tools)
        if self._think is not None:
            kwargs["think"] = self._think

        started = time.perf_counter()
        try:
            response = self._client.chat(**kwargs)
        except Exception as e:  # the client raises different errors for each failure
            raise LLMError(_describe(e, self._timeout)) from e
        elapsed = time.perf_counter() - started

        message = response.message
        calls = tuple(
            ToolCall(call.function.name, _parse_arguments(call.function.arguments))
            for call in (message.tool_calls or [])
        )
        log.info(
            "LLM answered in %.1f s (%d tool calls, %d chars)",
            elapsed, len(calls), len(message.content or ""),
        )
        return LLMReply(content=message.content or "", tool_calls=calls)

    def warm_up(self) -> float | None:
        """Load the model into memory now, so the first answer is not slow.

        Returns the load time in seconds, or None if the model is not available.
        """
        started = time.perf_counter()
        try:
            self._client.chat(model=self._model, messages=[], keep_alive=self._keep_alive)
        except Exception as e:
            log.warning(
                "LLM %s is not available (%s). Fast commands still work.",
                self._model, _describe(e, self._timeout),
            )
            return None
        elapsed = time.perf_counter() - started
        log.info("LLM %s loaded in %.1f s", self._model, elapsed)
        return elapsed


def _describe(error: Exception, timeout: float) -> str:
    name = type(error).__name__
    if "Timeout" in name:
        return (
            f"{name}: no answer in {timeout:.0f} s. The model may be running on the CPU "
            "or generating endlessly, check 'ollama ps'"
        )
    if isinstance(error, ConnectionError) or "Connect" in name:
        return f"{name}: cannot reach Ollama, is it running?"
    if "not found" in str(error).lower():
        return f"{name}: {error}. Run 'ollama pull' for this model"
    return f"{name}: {error}"


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return dict(raw) if isinstance(raw, Mapping) else {}
