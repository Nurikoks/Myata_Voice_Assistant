"""Short dialog memory, so Myata understands "а теперь дискорд"."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Action:
    """A skill that ran during a turn and what it returned."""

    name: str
    args: Mapping[str, Any] = field(default_factory=dict)
    result: str = ""


@dataclass(frozen=True)
class Turn:
    user: str
    reply: str
    actions: tuple[Action, ...] = ()
    phrased: bool = False  # the LLM wrote the reply from the tool results


class History:
    def __init__(
        self, max_turns: int, ttl_sec: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._turns: deque[Turn] = deque(maxlen=max_turns or None)
        self._enabled = max_turns > 0
        self._ttl = ttl_sec
        self._clock = clock
        self._last = 0.0

    def add(self, turn: Turn) -> None:
        if not self._enabled:
            return
        self._expire()
        self._turns.append(turn)
        self._last = self._clock()

    def clear(self) -> None:
        self._turns.clear()

    def messages(self) -> list[dict[str, Any]]:
        """History in Ollama chat format. Actions are stored as real tool calls,
        so the model keeps calling tools instead of just saying it did something."""
        self._expire()
        result: list[dict[str, Any]] = []
        for turn in self._turns:
            result.append({"role": "user", "content": turn.user})
            result.extend(action_messages(turn.actions))
            # After actions the reply is just the skills' own phrases, already in the
            # tool messages. It is added only when the LLM wrote it, to keep the context short.
            if not turn.actions or turn.phrased:
                result.append({"role": "assistant", "content": turn.reply})
        return result

    def __len__(self) -> int:
        self._expire()
        return len(self._turns)

    def _expire(self) -> None:
        if self._turns and self._clock() - self._last > self._ttl:
            self._turns.clear()


def action_messages(actions: tuple[Action, ...]) -> list[dict[str, Any]]:
    """One assistant message with all tool calls, then one tool message per result."""
    if not actions:
        return []
    calls = [{"function": {"name": a.name, "arguments": dict(a.args)}} for a in actions]
    messages: list[dict[str, Any]] = [{"role": "assistant", "content": "", "tool_calls": calls}]
    for a in actions:
        messages.append({"role": "tool", "content": a.result, "tool_name": a.name})
    return messages
