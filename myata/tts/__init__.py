"""Text to speech engines."""

from __future__ import annotations

import logging

from myata.config import TtsConfig
from myata.tts.base import FallbackTTS, NullTTS, TextToSpeech

__all__ = ["FallbackTTS", "NullTTS", "TextToSpeech", "create_tts"]

log = logging.getLogger(__name__)


def create_tts(config: TtsConfig, output_device: int | str | None = None) -> TextToSpeech:
    if config.engine == "none":
        return NullTTS()

    from myata.tts.pyttsx3_tts import Pyttsx3TTS

    backup = Pyttsx3TTS(rate=config.pyttsx3.rate, voice_hints=config.pyttsx3.voice_hints)
    if config.engine == "pyttsx3":
        return backup

    try:
        from myata.audio.player import AudioPlayer
        from myata.tts.silero_tts import SileroTTS

        main = SileroTTS(config.silero, AudioPlayer(output_device), config.replacements)
    except Exception as e:  # missing torch, missing model file, broken model...
        log.warning("Silero TTS is not available: %s", e)
        print(f"Голос Silero не загрузился ({e}). Говорю голосом pyttsx3.")
        return backup
    return FallbackTTS(main, backup)
