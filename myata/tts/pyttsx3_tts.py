"""pyttsx3 engine: robotic, but works everywhere. Kept as a fallback in stage 3."""

from __future__ import annotations

import logging
from collections.abc import Iterable

log = logging.getLogger(__name__)


class Pyttsx3TTS:
    def __init__(self, rate: int, voice_hints: Iterable[str]) -> None:
        self._rate = rate
        self._hints = tuple(h.lower() for h in voice_hints)
        self._voice_id: str | None = None
        self._voice_searched = False

    def speak(self, text: str) -> None:
        import pyttsx3

        # A new engine for every phrase: workaround for pyttsx3 going silent
        # after the first runAndWait() on Windows.
        engine = pyttsx3.init()
        if not self._voice_searched:
            self._voice_id = self._find_voice(engine)
            self._voice_searched = True
        if self._voice_id:
            engine.setProperty("voice", self._voice_id)
        engine.setProperty("rate", self._rate)
        engine.say(text)
        engine.runAndWait()

    def _find_voice(self, engine) -> str | None:
        for voice in engine.getProperty("voices"):
            name = f"{voice.name} {voice.id}".lower()
            if any(hint in name for hint in self._hints):
                log.info("Using TTS voice: %s", voice.name)
                return voice.id
        log.warning("No voice matched %s, using the default one", self._hints)
        return None
