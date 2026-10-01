"""The assistant core.

It only works with text, so it can be tested without a microphone:
the voice loop feeds it recognized phrases, the text mode feeds it typed ones.
The brain decides what to do; the core runs skills, asks for confirmation
before dangerous ones and talks to the user.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from enum import Enum, auto

from myata.brain.brain import Brain, Reply, SkillCall
from myata.brain.text import normalize
from myata.config import Config
from myata.oslayer import OSLayer
from myata.skills.base import SkillContext, SkillResult
from myata.tts.base import TextToSpeech
from myata.wake.detector import WakeWordDetector

log = logging.getLogger(__name__)


class Outcome(Enum):
    IGNORED = auto()    # speech without the wake word
    LISTENING = auto()  # only the name was said, waiting for a command
    HANDLED = auto()    # a command was processed (even if it failed)
    STOP = auto()       # the assistant should shut down


class Assistant:
    def __init__(
        self,
        *,
        config: Config,
        brain: Brain,
        wake: WakeWordDetector,
        tts: TextToSpeech,
        os_layer: OSLayer,
        clock: Callable[[], float] = time.monotonic,
        output: Callable[[str], None] = print,
    ) -> None:
        self._config = config
        self._brain = brain
        self._wake = wake
        self._tts = tts
        self._os = os_layer
        self._clock = clock
        self._output = output
        self._active_until = 0.0
        self._pending: tuple[str, SkillCall] | None = None
        self._pending_until = 0.0

    # ---------- talking ----------

    def say(self, text: str) -> None:
        self._output(f"{self._config.assistant.name}: {text}")
        log.info("Say: %s", text)
        self._tts.speak(text)

    def greet(self) -> None:
        self.say(self._config.assistant.phrases.greeting)

    def _listen_without_wake_word(self, seconds: float) -> None:
        self._active_until = self._clock() + seconds

    # ---------- input ----------

    def on_utterance(self, text: str) -> Outcome:
        """Voice mode: react to a recognized phrase, which may contain the wake word."""
        self._output(f"Вы: {text}")
        has_wake, command = self._wake.split(text)

        if has_wake and not command:
            self.say(self._config.assistant.phrases.listening)
            self._listen_without_wake_word(self._config.assistant.listen_window_sec)
            return Outcome.LISTENING

        if has_wake or self._clock() < self._active_until:
            self._active_until = 0.0
            return self.handle_command(command)

        log.debug("Ignored (no wake word): %s", text)
        return Outcome.IGNORED

    def handle_command(self, text: str) -> Outcome:
        """Run a command that is already addressed to the assistant."""
        if self._pending is not None:
            if self._clock() <= self._pending_until:
                return self._answer_confirmation(text)
            log.info("Confirmation for %s expired", self._pending[1].skill.name)
            self._pending = None

        decision = self._brain.decide(text)
        if isinstance(decision, Reply):
            self.say(decision.text)
            self._brain.remember(text, decision.text)
            if decision.text.rstrip().endswith("?"):
                # Myata asked something, let the user answer without the wake word.
                self._listen_without_wake_word(self._config.assistant.listen_window_sec)
            return Outcome.HANDLED
        return self._start(text, decision)

    # ---------- skills ----------

    def _start(self, user_text: str, call: SkillCall) -> Outcome:
        if not call.skill.dangerous:
            return self._execute(user_text, call)
        timeout = self._config.assistant.confirm_timeout_sec
        self._pending = (user_text, call)
        self._pending_until = self._clock() + timeout
        self.say(call.skill.confirm or self._config.assistant.phrases.confirm)
        self._listen_without_wake_word(timeout)
        return Outcome.HANDLED

    def _answer_confirmation(self, text: str) -> Outcome:
        assert self._pending is not None
        user_text, call = self._pending
        self._pending = None
        self._active_until = 0.0
        words = set(normalize(text).split())
        yes = words & set(self._config.assistant.yes_words)
        no = words & set(self._config.assistant.no_words)
        if yes and not no:
            log.info("Confirmed: %s", call.skill.name)
            return self._execute(user_text, call)
        log.info("Not confirmed: %s (answer %r)", call.skill.name, text)
        self.say(self._config.assistant.phrases.cancelled)
        return Outcome.HANDLED

    def _execute(self, user_text: str, call: SkillCall) -> Outcome:
        ctx = SkillContext(
            os=self._os, config=self._config, text=normalize(user_text), args=call.args
        )
        try:
            result = call.skill.handler(ctx)
        except Exception:
            log.exception("Skill %s crashed", call.skill.name)
            result = SkillResult(self._config.assistant.phrases.failed, ok=False)

        self.say(result.speech)
        self._brain.remember(user_text, result.speech, call)
        return Outcome.STOP if result.stop else Outcome.HANDLED
