"""The voice loop as an explicit state machine.

WAKE     only the cheap Vosk spotter listens for "мята"; the last second of
         audio is kept in a pre-roll buffer.
COMMAND  Silero VAD records the phrase until the user goes quiet. After the
         wake word the pre-roll goes first, so "мята, открой ютуб" said in one
         breath is not cut. When Myata waits for an answer (she asked a question
         or needs "да"/"нет"), recording starts right away, without the wake word.
BUSY     Whisper, the brain and the voice are working; the microphone is muted,
         so Myata never hears herself.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable
from enum import Enum, auto
from typing import Protocol

import numpy as np

from myata.audio.player import pcm16_to_float
from myata.core.assistant import Assistant, Outcome
from myata.stt.vad import PhraseRecorder, PhraseStatus
from myata.stt.whisper_stt import SpeechToText
from myata.wake.spotter import WakeSpotter

log = logging.getLogger(__name__)


class Phase(Enum):
    WAKE = auto()
    COMMAND = auto()
    BUSY = auto()


class AudioRing:
    """Keeps only the newest max_samples of audio."""

    def __init__(self, max_samples: int) -> None:
        self._max = max_samples
        self._chunks: deque[np.ndarray] = deque()
        self._size = 0

    def append(self, samples: np.ndarray) -> None:
        self._chunks.append(samples)
        self._size += len(samples)
        while self._chunks and self._size - len(self._chunks[0]) >= self._max:
            self._size -= len(self._chunks.popleft())

    def take(self) -> np.ndarray:
        """Return everything kept so far and empty the buffer."""
        if not self._chunks:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(list(self._chunks))[-self._max :]
        self.clear()
        return audio

    def clear(self) -> None:
        self._chunks.clear()
        self._size = 0


class MutableMic(Protocol):
    """What the loop needs from the microphone (see audio/microphone.py)."""

    def read(self, timeout: float = 0.5) -> bytes | None: ...

    def mute(self) -> None: ...

    def unmute(self) -> None: ...


class VoiceLoop:
    def __init__(
        self,
        *,
        assistant: Assistant,
        mic: MutableMic,
        spotter: WakeSpotter,
        recorder: PhraseRecorder,
        stt: SpeechToText,
        sample_rate: int,
        preroll_sec: float,
        wake_timeout_sec: float,
        unmute_delay_sec: float,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._assistant = assistant
        self._mic = mic
        self._spotter = spotter
        self._recorder = recorder
        self._stt = stt
        self._preroll = AudioRing(round(preroll_sec * sample_rate))
        self._wake_timeout = wake_timeout_sec
        self._unmute_delay = unmute_delay_sec
        self._sleep = sleep
        self._after_wake_word = False
        self.phase = Phase.WAKE
        self._listen()

    def run(self) -> None:
        while True:
            chunk = self._mic.read()
            if chunk is not None and self.step(chunk) is Outcome.STOP:
                return

    def step(self, chunk: bytes) -> Outcome | None:
        """Process one microphone block. Returns an outcome when a phrase was handled."""
        if self.phase is Phase.BUSY:
            return None  # cannot normally happen: the mic is muted while busy
        samples = pcm16_to_float(chunk)

        if self.phase is Phase.WAKE:
            self._preroll.append(samples)
            if self._spotter.accept(chunk):
                log.info("Wake word spotted, recording the phrase")
                self._record(after_wake_word=True, timeout=self._wake_timeout)
                self._recorder.feed(self._preroll.take())
            return None

        status = self._recorder.feed(samples)
        if status is PhraseStatus.RECORDING:
            return None
        if status is PhraseStatus.TIMEOUT:
            log.info("Nobody spoke, back to waiting for the wake word")
            if not self._after_wake_word:
                self._assistant.stop_waiting()
            self._listen()
            return None
        return self._handle(self._recorder.audio())

    def _handle(self, audio: np.ndarray) -> Outcome:
        self.phase = Phase.BUSY
        self._mic.mute()
        outcome = Outcome.IGNORED
        started = time.perf_counter()
        try:
            text = self._transcribe(audio)
            recognized = time.perf_counter()
            outcome = self._dispatch(text)
            # One line per phrase, to see where the time goes. "reply" includes the
            # brain (fast path or LLM), the skills and speaking the answer out loud.
            log.info(
                "Timing: STT %.2f s, reply %.2f s (%s)",
                recognized - started, time.perf_counter() - recognized, outcome.name,
            )
        finally:
            if outcome is not Outcome.STOP:
                self._sleep(self._unmute_delay)  # let the speaker's echo die out
                self._mic.unmute()
                self._listen()
        return outcome

    def _transcribe(self, audio: np.ndarray) -> str:
        try:
            return self._stt.transcribe(audio)
        except Exception:
            log.exception("Speech recognition failed")
            return ""

    def _dispatch(self, text: str) -> Outcome:
        if not text:
            return Outcome.IGNORED
        if self._after_wake_word:
            if not self._assistant.is_addressed(text):
                log.info("False wake word, Whisper heard: %r", text)
                return Outcome.IGNORED
            return self._assistant.on_utterance(text)
        return self._assistant.on_reply(text)

    def _listen(self) -> None:
        """Choose the next phase: an open reply window means recording right away."""
        window = self._assistant.reply_window
        if window > 0:
            self._record(after_wake_word=False, timeout=window)
            return
        self.phase = Phase.WAKE
        self._spotter.reset()
        self._preroll.clear()

    def _record(self, *, after_wake_word: bool, timeout: float) -> None:
        self.phase = Phase.COMMAND
        self._after_wake_word = after_wake_word
        self._recorder.start(timeout)
