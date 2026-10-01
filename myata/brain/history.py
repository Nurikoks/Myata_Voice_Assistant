"""Short dialog memory, so Myata understands "а теперь дискорд"."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Turn:
    user: str
    reply: str
    tool_name: str | None = None
    tool_args: Mapping[str, Any] | None = None


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
            if turn.tool_name:
                args = dict(turn.tool_args or {})
                call = {"function": {"name": turn.tool_name, "arguments": args}}
                result.append({"role": "assistant", "content": "", "tool_calls": [call]})
                result.append({"role": "tool", "content": turn.reply, "tool_name": turn.tool_name})
            else:
                result.append({"role": "assistant", "content": turn.reply})
        return result

    def __len__(self) -> int:
        self._expire()
        return len(self._turns)

    def _expire(self) -> None:
        if self._turns and self._clock() - self._last > self._ttl:
            self._turns.clear()
