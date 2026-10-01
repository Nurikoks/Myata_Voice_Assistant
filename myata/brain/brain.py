"""The hybrid brain: fast path first, LLM when the fast path is not sure.

The brain only decides. It never runs skills itself, so the assistant core
stays in charge of safety (confirmations) and of talking to the user.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from myata.brain.history import History, Turn
from myata.brain.llm import ChatModel, LLMError
from myata.brain.prompt import build_system_prompt, tool_spec
from myata.brain.router import Router
from myata.brain.speech import clean_for_speech
from myata.config import Config
from myata.skills.args import ArgsError, validate_args
from myata.skills.base import Skill

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillCall:
    skill: Skill
    args: Mapping[str, Any] = field(default_factory=dict)
    source: str = "fast"   # "fast" or "llm"


@dataclass(frozen=True)
class Reply:
    text: str


Decision = SkillCall | Reply


class Brain:
    def __init__(
        self,
        *,
        config: Config,
        router: Router,
        skills: Iterable[Skill],
        llm: ChatModel | None,
        history: History,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._config = config
        self._router = router
        self._llm = llm
        self._history = history
        self._now = now
        self._skills = {s.name: s for s in skills}
        self._tools = [tool_spec(s) for s in self._skills.values() if s.llm]

    def decide(self, text: str) -> Decision:
        match = self._router.match(text)
        if match is not None:
            log.info("Fast path: %s (score %.2f) for %r", match.skill.name, match.score, text)
            return SkillCall(match.skill, {}, "fast")

        phrases = self._config.assistant.phrases
        if self._llm is None:
            return Reply(phrases.not_understood)

        try:
            reply = self._llm.chat(self._messages(text), self._tools)
        except LLMError as e:
            log.warning("LLM failed: %s", e)
            return Reply(phrases.brain_offline)

        for call in reply.tool_calls:
            item = self._skills.get(call.name)
            if item is None or not item.llm:
                log.warning("LLM called an unknown or forbidden tool: %s", call.name)
                continue
            try:
                args = validate_args(item.parameters, call.arguments)
            except ArgsError as e:
                log.warning("LLM gave bad arguments for %s: %s", call.name, e)
                continue
            log.info("LLM tool call: %s %s for %r", item.name, args, text)
            return SkillCall(item, args, "llm")

        speech = clean_for_speech(reply.content, self._config.llm.max_reply_chars)
        log.info("LLM answer for %r: %r", text, speech)
        return Reply(speech or phrases.not_understood)

    def remember(self, user_text: str, reply: str, call: SkillCall | None = None) -> None:
        if call is None:
            self._history.add(Turn(user_text, reply))
        else:
            self._history.add(Turn(user_text, reply, call.skill.name, dict(call.args)))

    def _messages(self, text: str) -> list[dict[str, Any]]:
        system = build_system_prompt(
            self._config.llm.system_prompt, self._config.assistant.name, self._now()
        )
        return [
            {"role": "system", "content": system},
            *self._history.messages(),
            {"role": "user", "content": text},
        ]
