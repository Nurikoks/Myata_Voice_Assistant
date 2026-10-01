"""Wake word spotting with Vosk restricted to a tiny grammar.

With the grammar ["мята", "[unk]"] the small Vosk model can only output the
name or "unknown", which makes it fast and much less jumpy than free recognition.
Partial results are checked too, so Myata reacts while the user is still talking.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from myata.brain.text import normalize

log = logging.getLogger(__name__)


class WakeSpotter(Protocol):
    def accept(self, chunk: bytes) -> bool:
        """Feed raw 16-bit audio. True when the wake word was heard."""

    def reset(self) -> None:
        """Forget the audio heard so far."""


class VoskWakeSpotter:
    def __init__(self, model_path: str, sample_rate: int, words: Iterable[str]) -> None:
        path = Path(model_path)
        if not path.is_dir():
            raise FileNotFoundError(
                f"Vosk model not found at '{path.resolve()}'. Download "
                "vosk-model-small-ru-0.22 from https://alphacephei.com/vosk/models "
                "and unzip it there, or change wake.vosk_model_path in config.yaml."
            )
        self._words = tuple(normalize(w) for w in words)
        _warn_about_unknown_words(path, self._words)

        from vosk import KaldiRecognizer, Model, SetLogLevel

        SetLogLevel(-1)  # hide Kaldi's own noisy logs, errors still raise exceptions
        grammar = json.dumps([*self._words, "[unk]"], ensure_ascii=False)
        self._recognizer = KaldiRecognizer(Model(str(path)), sample_rate, grammar)
        log.info("Vosk wake spotter loaded from %s, grammar %s", path, grammar)

    def accept(self, chunk: bytes) -> bool:
        if self._recognizer.AcceptWaveform(chunk):
            text = json.loads(self._recognizer.Result()).get("text", "")
        else:
            text = json.loads(self._recognizer.PartialResult()).get("partial", "")
        if any(word in self._words for word in text.split()):
            log.debug("Vosk heard the wake word: %r", text)
            self.reset()
            return True
        return False

    def reset(self) -> None:
        self._recognizer.Reset()


def _warn_about_unknown_words(model_path: Path, words: tuple[str, ...]) -> None:
    """Vosk silently ignores grammar words that are not in the model's vocabulary."""
    vocabulary_file = model_path / "graph" / "words.txt"
    if not vocabulary_file.is_file():
        return
    with vocabulary_file.open(encoding="utf-8") as f:
        vocabulary = {line.split(maxsplit=1)[0] for line in f if line.strip()}
    missing = [w for w in words if w not in vocabulary]
    if missing:
        log.warning("Wake words missing in the Vosk vocabulary, they will never fire: %s", missing)
