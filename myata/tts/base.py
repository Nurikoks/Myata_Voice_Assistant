"""The interface every TTS engine follows."""

from __future__ import annotations

import logging
from typing import Protocol

log = logging.getLogger(__name__)


class TextToSpeech(Protocol):
    def speak(self, text: str) -> None:
        """Say the text out loud. Blocks until speech is finished."""


class NullTTS:
    """Silent engine for text mode and tests."""

    def speak(self, text: str) -> None:
        pass


class FallbackTTS:
    """Speaks with the main engine and switches to the backup one if it fails."""

    def __init__(self, main: TextToSpeech, backup: TextToSpeech) -> None:
        self._main = main
        self._backup = backup

    def speak(self, text: str) -> None:
        try:
            self._main.speak(text)
        except Exception:
            log.exception("Main TTS failed, using the backup voice for %r", text)
            self._backup.speak(text)
