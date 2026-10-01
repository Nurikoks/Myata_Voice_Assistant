"""The hybrid brain: fast path first, LLM when the fast path is not sure.

The brain only decides and phrases answers. It never runs skills itself, so the
assistant core stays in charge of safety (confirmations) and of talking to the user.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from myata.brain.history import Action, History, Turn, action_messages
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
class MultiCall:
    """Several skills at once: "открой дискорд и стим"."""

    calls: tuple[SkillCall, ...]


@dataclass(frozen=True)
class Reply:
    text: str


Decision = SkillCall | MultiCall | Reply


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
        self._tools = [tool_spec(s) for s in self._skills.values() if s.llm and s.tool]

    @property
    def has_llm(self) -> bool:
        return self._llm is not None

    def decide(self, text: str) -> Decision:
        match = self._router.match(text)
        if match is not None:
            try:
                args = validate_args(match.skill.parameters, match.args)
            except ArgsError as e:
                log.info("Fast path match %s rejected: %s", match.skill.name, e)
            else:
                log.info(
                    "Fast path: %s %s (score %.2f) for %r",
                    match.skill.name, args, match.score, text,
                )
                return SkillCall(match.skill, args, "fast")

        phrases = self._config.assistant.phrases
        if self._llm is None:
            return Reply(phrases.not_understood)

        try:
            reply = self._llm.chat(self._messages(text), self._tools)
        except LLMError as e:
            log.warning("LLM failed: %s", e)
            return Reply(phrases.brain_offline)

        calls = self._valid_calls(reply.tool_calls, text)
        if len(calls) == 1:
            return calls[0]
        if calls:
            return MultiCall(tuple(calls))

        speech = clean_for_speech(reply.content, self._config.llm.max_reply_chars)
        log.info("LLM answer for %r: %r", text, speech)
        return Reply(speech or phrases.not_understood)

    def _valid_calls(self, tool_calls: Iterable[Any], text: str) -> list[SkillCall]:
        calls: list[SkillCall] = []
        seen: set[str] = set()
        for call in tool_calls:
            # Hidden skills (tool=False) are accepted: the model learns their names
            # from the dialog history. Only llm=False skills are forbidden.
            item = self._skills.get(call.name)
            if item is None or not item.llm:
                log.warning("LLM called an unknown or forbidden tool: %s", call.name)
                continue
            try:
                args = validate_args(item.parameters, call.arguments)
            except ArgsError as e:
                log.warning("LLM gave bad arguments for %s: %s", call.name, e)
                continue
            key = f"{item.name}{sorted(args.items())}"
            if key in seen:
                continue  # small models sometimes repeat the same call
            seen.add(key)
            if len(calls) == self._config.llm.max_tool_calls:
                log.warning("LLM asked for more than %d tools, the rest is ignored", len(calls))
                break
            log.info("LLM tool call: %s %s for %r", item.name, args, text)
            calls.append(SkillCall(item, args, "llm"))
        return calls

    def phrase(self, user_text: str, actions: Sequence[Action]) -> str | None:
        """Second LLM pass: turn the skills' results (data) into an answer.

        Returns None when there is no LLM or it failed; the caller then uses the
        skills' own phrases. No tools are offered here, so text from the results
        (a copied web page, for example) cannot make the model run anything.
        """
        if self._llm is None:
            return None
        messages = self._messages(user_text) + action_messages(tuple(actions))
        try:
            reply = self._llm.chat(messages, [])
        except LLMError as e:
            log.warning("LLM could not phrase the result: %s", e)
            return None
        speech = clean_for_speech(reply.content, self._config.llm.max_reply_chars)
        log.info("LLM phrased the result for %r: %r", user_text, speech)
        return speech or None

    def remember(
        self,
        user_text: str,
        reply: str,
        actions: Sequence[Action] = (),
        phrased: bool = False,
    ) -> None:
        self._history.add(Turn(user_text, reply, tuple(actions), phrased))

    def _messages(self, text: str) -> list[dict[str, Any]]:
        system = build_system_prompt(
            self._config.llm.system_prompt, self._config.assistant.name, self._now()
        )
        return [
            {"role": "system", "content": system},
            *self._history.messages(),
            {"role": "user", "content": text},
        ]
