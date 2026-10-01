"""Finds the assistant's name in a recognized phrase.

The Vosk spotter (wake/spotter.py) wakes Myata up cheaply. Whisper then
transcribes the phrase and this detector checks that the name is really there,
which filters out false alarms like "мать" that the small Vosk model hears as "мята".
"""

from __future__ import annotations

from collections.abc import Iterable

from myata.brain.text import normalize, similarity


class WakeWordDetector:
    def __init__(self, words: Iterable[str], threshold: float) -> None:
        self._words = tuple(normalize(w) for w in words)
        if not self._words:
            raise ValueError("at least one wake word is required")
        self._threshold = threshold

    def is_wake(self, word: str) -> bool:
        word = normalize(word)
        return max(similarity(word, w) for w in self._words) >= self._threshold

    def split(self, text: str) -> tuple[bool, str]:
        """Return (was the name said, the command after the name).

        Words before the name are dropped: in voice mode they are usually the
        end of an earlier phrase that got into the pre-roll buffer.
        """
        words = normalize(text).split()
        for i, word in enumerate(words):
            if self.is_wake(word):
                rest = [w for w in words[i + 1 :] if not self.is_wake(w)]
                return True, " ".join(rest)
        return False, " ".join(words)
