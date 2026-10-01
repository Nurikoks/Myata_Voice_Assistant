"""The interface every TTS engine follows."""

from __future__ import annotations

from typing import Protocol


class TextToSpeech(Protocol):
    def speak(self, text: str) -> None:
        """Say the text out loud. Blocks until speech is finished."""


class NullTTS:
    """Silent engine for text mode and tests."""

    def speak(self, text: str) -> None:
        pass
