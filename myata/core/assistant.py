"""The assistant core.

It only works with text, so it can be tested without a microphone:
the voice loop feeds it recognized phrases, the text mode feeds it typed ones.
The brain decides what to do; the core runs skills, asks for confirmation
before dangerous ones and talks to the user.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable
from enum import Enum, auto

from myata.brain.brain import Brain, MultiCall, Reply, SkillCall
from myata.brain.history import Action
from myata.brain.text import normalize
from myata.config import Config
from myata.oslayer import OSLayer
from myata.skills.base import SkillContext, SkillResult
from myata.tts.base import TextToSpeech
from myata.wake.detector import WakeWordDetector

log = logging.getLogger(__name__)

HISTORY_RESULT_CHARS = 500  # long results (clipboard text) are cut in the dialog history


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
        self._pending: tuple[str, tuple[SkillCall, ...]] | None = None
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

    @property
    def reply_window(self) -> float:
        """Seconds left to answer without the wake word (0 when Myata is not waiting)."""
        return max(0.0, self._active_until - self._clock())

    def stop_waiting(self) -> None:
        """The user did not answer in time."""
        self._active_until = 0.0

    def is_addressed(self, text: str) -> bool:
        """True if the phrase contains Myata's name."""
        return self._wake.split(text)[0]

    def _start_listening(self) -> Outcome:
        self.say(self._config.assistant.phrases.listening)
        self._listen_without_wake_word(self._config.assistant.listen_window_sec)
        return Outcome.LISTENING

    # ---------- input ----------

    def on_utterance(self, text: str) -> Outcome:
        """Voice mode: react to a recognized phrase, which may contain the wake word."""
        self._output(f"Вы: {text}")
        has_wake, command = self._wake.split(text)

        if has_wake and not command:
            return self._start_listening()

        if has_wake or self._clock() < self._active_until:
            self._active_until = 0.0
            return self.handle_command(command)

        log.debug("Ignored (no wake word): %s", text)
        return Outcome.IGNORED

    def on_reply(self, text: str) -> Outcome:
        """Voice mode: an answer recorded inside the reply window, no wake word needed.

        The voice loop decides that the window was open when recording started,
        so a long answer or slow recognition does not make Myata ignore it.
        """
        self._output(f"Вы: {text}")
        has_wake, command = self._wake.split(text)
        if has_wake and not command:
            return self._start_listening()
        self._active_until = 0.0
        return self.handle_command(command)

    def handle_command(self, text: str) -> Outcome:
        """Run a command that is already addressed to the assistant."""
        if self._pending is not None:
            if self._clock() <= self._pending_until:
                return self._answer_confirmation(text)
            log.info("Confirmation for %s expired", _names(self._pending[1]))
            self._pending = None

        decision = self._brain.decide(text)
        if isinstance(decision, Reply):
            self.say(decision.text)
            self._brain.remember(text, decision.text)
            if decision.text.rstrip().endswith("?"):
                # Myata asked something, let the user answer without the wake word.
                self._listen_without_wake_word(self._config.assistant.listen_window_sec)
            return Outcome.HANDLED
        calls = decision.calls if isinstance(decision, MultiCall) else (decision,)
        return self._start(text, calls)

    # ---------- skills ----------

    def _start(self, user_text: str, calls: tuple[SkillCall, ...]) -> Outcome:
        dangerous = [call for call in calls if call.skill.dangerous]
        if not dangerous:
            return self._execute(user_text, calls)
        # One confirmation covers the whole batch.
        timeout = self._config.assistant.confirm_timeout_sec
        self._pending = (user_text, calls)
        self._pending_until = self._clock() + timeout
        self.say(dangerous[0].skill.confirm or self._config.assistant.phrases.confirm)
        self._listen_without_wake_word(timeout)
        return Outcome.HANDLED

    def _answer_confirmation(self, text: str) -> Outcome:
        assert self._pending is not None
        user_text, calls = self._pending
        self._pending = None
        self._active_until = 0.0
        words = set(normalize(text).split())
        yes = words & set(self._config.assistant.yes_words)
        no = words & set(self._config.assistant.no_words)
        if yes and not no:
            log.info("Confirmed: %s", _names(calls))
            return self._execute(user_text, calls)
        log.info("Not confirmed: %s (answer %r)", _names(calls), text)
        self.say(self._config.assistant.phrases.cancelled)
        return Outcome.HANDLED

    def _execute(self, user_text: str, calls: tuple[SkillCall, ...]) -> Outcome:
        results = [(call, self._run(user_text, call)) for call in calls]
        actions = [
            Action(call.skill.name, dict(call.args), result.data or result.speech)
            for call, result in results
        ]

        # Skills with data (notes, clipboard) are answered by the LLM, which sees
        # the user's question and the data. Without the LLM their own phrase is used.
        speech = None
        if any(result.data for _, result in results):
            speech = self._brain.phrase(user_text, actions)
        phrased = speech is not None
        if speech is None:
            speech = join_sentences(result.speech for _, result in results)

        self.say(speech)
        short = [Action(a.name, a.args, a.result[:HISTORY_RESULT_CHARS]) for a in actions]
        self._brain.remember(user_text, speech, short, phrased)
        if phrased and speech.rstrip().endswith("?"):
            self._listen_without_wake_word(self._config.assistant.listen_window_sec)
        return Outcome.STOP if any(result.stop for _, result in results) else Outcome.HANDLED

    def _run(self, user_text: str, call: SkillCall) -> SkillResult:
        ctx = SkillContext(
            os=self._os, config=self._config, text=normalize(user_text), args=call.args
        )
        try:
            return call.skill.handler(ctx)
        except Exception:
            log.exception("Skill %s crashed", call.skill.name)
            return SkillResult(self._config.assistant.phrases.failed, ok=False)


def _names(calls: tuple[SkillCall, ...]) -> str:
    return ", ".join(call.skill.name for call in calls)


def join_sentences(parts: Iterable[str]) -> str:
    """Join the skills' phrases: "Открываю дискорд. Запускаю стим." """
    sentences: list[str] = []
    for part in parts:
        part = part.strip()
        if part and part not in sentences:  # two failures should not say it twice
            sentences.append(part)
    if len(sentences) <= 1:
        return sentences[0] if sentences else ""
    return " ".join(s if s[-1] in ".!?" else f"{s}." for s in sentences)
