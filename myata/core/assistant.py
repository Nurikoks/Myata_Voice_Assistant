"""The assistant core.

It only works with text, so it can be tested without a microphone:
the voice loop feeds it recognized phrases, the text mode feeds it typed ones.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from enum import Enum, auto

from myata.brain.router import Router
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
        router: Router,
        wake: WakeWordDetector,
        tts: TextToSpeech,
        os_layer: OSLayer,
        clock: Callable[[], float] = time.monotonic,
        output: Callable[[str], None] = print,
    ) -> None:
        self._config = config
        self._router = router
        self._wake = wake
        self._tts = tts
        self._os = os_layer
        self._clock = clock
        self._output = output
        self._active_until = 0.0

    def say(self, text: str) -> None:
        self._output(f"{self._config.assistant.name}: {text}")
        log.info("Say: %s", text)
        self._tts.speak(text)

    def greet(self) -> None:
        self.say(self._config.assistant.phrases.greeting)

    def on_utterance(self, text: str) -> Outcome:
        """Voice mode: react to a recognized phrase, which may contain the wake word."""
        self._output(f"Вы: {text}")
        has_wake, command = self._wake.split(text)

        if has_wake and not command:
            self.say(self._config.assistant.phrases.listening)
            self._active_until = self._clock() + self._config.assistant.listen_window_sec
            return Outcome.LISTENING

        if has_wake or self._clock() < self._active_until:
            self._active_until = 0.0
            return self.handle_command(command)

        log.debug("Ignored (no wake word): %s", text)
        return Outcome.IGNORED

    def handle_command(self, text: str) -> Outcome:
        """Run a command that is already addressed to the assistant."""
        match = self._router.match(text)
        if match is None:
            log.info("No skill for: %r", text)
            self.say(self._config.assistant.phrases.not_understood)
            return Outcome.HANDLED

        log.info("Skill %s (score %.2f) for %r", match.skill.name, match.score, text)
        ctx = SkillContext(os=self._os, config=self._config, text=normalize(text))
        try:
            result = match.skill.handler(ctx)
        except Exception:
            log.exception("Skill %s crashed", match.skill.name)
            result = SkillResult(self._config.assistant.phrases.failed, ok=False)

        self.say(result.speech)
        return Outcome.STOP if result.stop else Outcome.HANDLED
