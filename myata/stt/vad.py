"""Voice activity detection: record a phrase until the speaker goes quiet.

SileroVad wraps the Silero VAD model (one ~2 MB TorchScript file).
PhraseRecorder holds the "when is the phrase over" logic. It only needs a
function that returns a speech probability for a 32 ms frame, so it is tested
with a fake instead of the real model.
"""

from __future__ import annotations

import logging
from enum import Enum, auto
from pathlib import Path
from typing import Protocol

import numpy as np

log = logging.getLogger(__name__)

FRAME_SIZE = 512  # Silero VAD works on 512-sample frames at 16 kHz (32 ms)


class SpeechDetector(Protocol):
    def probability(self, frame: np.ndarray) -> float:
        """Speech probability (0..1) for one frame of FRAME_SIZE float32 samples."""

    def reset(self) -> None:
        """Forget the context of the previous phrase."""


class SileroVad:
    def __init__(self, model_path: str, sample_rate: int) -> None:
        path = Path(model_path)
        if not path.is_file():
            raise FileNotFoundError(
                f"Silero VAD model not found at '{path.resolve()}'. Download it with:\n"
                "Invoke-WebRequest https://raw.githubusercontent.com/snakers4/silero-vad/"
                f"master/src/silero_vad/data/silero_vad.jit -OutFile {model_path}"
            )
        import torch

        self._torch = torch
        self._model = torch.jit.load(str(path), map_location="cpu")
        self._model.eval()
        self._sample_rate = sample_rate
        log.info("Silero VAD loaded from %s", path)

    def probability(self, frame: np.ndarray) -> float:
        with self._torch.no_grad():
            return float(self._model(self._torch.from_numpy(frame), self._sample_rate).item())

    def reset(self) -> None:
        self._model.reset_states()


class PhraseStatus(Enum):
    RECORDING = auto()  # keep feeding audio
    DONE = auto()       # the speaker finished, take audio()
    TIMEOUT = auto()    # nobody started talking


class PhraseRecorder:
    def __init__(
        self,
        detector: SpeechDetector,
        *,
        sample_rate: int,
        threshold: float,
        silence_ms: int,
        min_speech_ms: int,
        max_phrase_sec: float,
        pad_ms: int = 300,
    ) -> None:
        self._detector = detector
        self._threshold = threshold
        frame_ms = FRAME_SIZE * 1000 / sample_rate
        self._sample_rate = sample_rate
        self._silence_frames = max(1, round(silence_ms / frame_ms))
        self._min_speech_frames = max(1, round(min_speech_ms / frame_ms))
        self._max_frames = max(1, round(max_phrase_sec * 1000 / frame_ms))
        self._pad_frames = round(pad_ms / frame_ms)
        self._timeout_frames = 0
        self._frames: list[np.ndarray] = []
        self._leftover = np.zeros(0, dtype=np.float32)
        self._speech_frames = 0
        self._first_speech: int | None = None
        self._silence_run = 0
        self._status = PhraseStatus.RECORDING

    def start(self, start_timeout_sec: float) -> None:
        """Begin a new phrase. Gives up if no speech starts within the timeout."""
        frame_sec = FRAME_SIZE / self._sample_rate
        self._timeout_frames = max(1, round(start_timeout_sec / frame_sec))
        self._frames = []
        self._leftover = np.zeros(0, dtype=np.float32)
        self._speech_frames = 0
        self._first_speech = None
        self._silence_run = 0
        self._status = PhraseStatus.RECORDING
        self._detector.reset()

    @property
    def started(self) -> bool:
        """True once enough speech was heard to count as a phrase."""
        return self._speech_frames >= self._min_speech_frames

    def feed(self, samples: np.ndarray) -> PhraseStatus:
        """Feed float32 audio of any length."""
        if self._status is not PhraseStatus.RECORDING:
            return self._status
        data = np.concatenate([self._leftover, samples.astype(np.float32, copy=False)])
        whole = len(data) // FRAME_SIZE * FRAME_SIZE
        self._leftover = data[whole:]
        for start in range(0, whole, FRAME_SIZE):
            self._status = self._feed_frame(data[start : start + FRAME_SIZE])
            if self._status is not PhraseStatus.RECORDING:
                break
        return self._status

    def _feed_frame(self, frame: np.ndarray) -> PhraseStatus:
        self._frames.append(frame)
        if self._detector.probability(frame) >= self._threshold:
            if self._first_speech is None:
                self._first_speech = len(self._frames) - 1
            self._speech_frames += 1
            self._silence_run = 0
        else:
            self._silence_run += 1

        if self.started:
            if self._silence_run >= self._silence_frames:
                return PhraseStatus.DONE
            if len(self._frames) >= self._max_frames:
                log.info("Phrase cut at the %d-frame limit", self._max_frames)
                return PhraseStatus.DONE
        elif len(self._frames) >= self._timeout_frames:
            return PhraseStatus.TIMEOUT
        return PhraseStatus.RECORDING

    def audio(self) -> np.ndarray:
        """The recorded phrase, without the long silence before it."""
        if not self._frames:
            return np.zeros(0, dtype=np.float32)
        first = max(0, (self._first_speech or 0) - self._pad_frames)
        return np.concatenate(self._frames[first:])
