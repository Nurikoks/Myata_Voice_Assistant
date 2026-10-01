"""Fast path: match a command to a skill without any LLM.

Stage 1 keeps the old behaviour (whole phrase vs. example phrases).
Stage 2 makes it smarter and sends unsure cases to the LLM.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from myata.brain.text import normalize, similarity
from myata.skills.base import Skill


@dataclass(frozen=True)
class Match:
    skill: Skill
    score: float


class Router:
    def __init__(self, skills: Iterable[Skill], threshold: float) -> None:
        self._threshold = threshold
        self._phrases = [(normalize(p), s) for s in skills for p in s.phrases]

    def match(self, text: str) -> Match | None:
        text = normalize(text)
        if not text:
            return None
        best: Match | None = None
        for phrase, item in self._phrases:
            score = float(text == phrase) if item.exact else similarity(text, phrase)
            if best is None or score > best.score:
                best = Match(item, score)
        if best is not None and best.score >= self._threshold:
            return best
        return None
