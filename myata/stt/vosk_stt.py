"""Vosk speech recognizer: turns a stream of audio chunks into phrases."""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


class VoskRecognizer:
    def __init__(self, model_path: str, sample_rate: int) -> None:
        path = Path(model_path)
        if not path.is_dir():
            raise FileNotFoundError(
                f"Vosk model not found at '{path.resolve()}'. Download "
                "vosk-model-small-ru-0.22 from https://alphacephei.com/vosk/models "
                "and unzip it there, or change stt.vosk_model_path in config.yaml."
            )
        from vosk import KaldiRecognizer, Model, SetLogLevel

        SetLogLevel(-1)  # hide Kaldi's own noisy logs, errors still raise exceptions
        self._recognizer = KaldiRecognizer(Model(str(path)), sample_rate)
        log.info("Vosk model loaded from %s", path)

    def accept(self, chunk: bytes) -> str:
        """Feed audio. Returns a finished phrase, or "" if the phrase is not over yet."""
        if not self._recognizer.AcceptWaveform(chunk):
            return ""
        return json.loads(self._recognizer.Result()).get("text", "")

    def reset(self) -> None:
        self._recognizer.Reset()
