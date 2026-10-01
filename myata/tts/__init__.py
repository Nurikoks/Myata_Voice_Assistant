"""Text to speech engines."""

from __future__ import annotations

from myata.config import TtsConfig
from myata.tts.base import NullTTS, TextToSpeech

__all__ = ["NullTTS", "TextToSpeech", "create_tts"]


def create_tts(config: TtsConfig) -> TextToSpeech:
    if config.engine == "none":
        return NullTTS()
    from myata.tts.pyttsx3_tts import Pyttsx3TTS

    return Pyttsx3TTS(rate=config.rate, voice_hints=config.voice_hints)
