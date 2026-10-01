"""Plays generated speech through the speakers."""

from __future__ import annotations

import numpy as np


class AudioPlayer:
    def __init__(self, device: int | str | None = None) -> None:
        self._device = device

    def play(self, audio: np.ndarray, sample_rate: int) -> None:
        """Play mono float audio and block until it is finished."""
        import sounddevice as sd  # lazy: tests and text mode do not need PortAudio

        sd.play(audio, sample_rate, device=self._device)
        sd.wait()


def pcm16_to_float(chunk: bytes) -> np.ndarray:
    """Raw 16-bit microphone bytes to float32 samples in [-1, 1]."""
    return np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
