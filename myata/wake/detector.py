"""Finds the assistant's name in a recognized phrase.

Stage 1 keeps the old logic (fuzzy match of every word). Stage 3 replaces it
with a Vosk grammar that only knows the wake word, which is far more precise.
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
        """Return (was the name said, the rest of the phrase without the name)."""
        words = normalize(text).split()
        rest = [w for w in words if not self.is_wake(w)]
        return len(rest) != len(words), " ".join(rest)
