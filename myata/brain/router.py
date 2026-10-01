"""Fast path: match a command to a skill instantly, without the LLM.

Every example phrase of a skill is compared word by word with the command
(word order and word forms do not matter, filler words are ignored).
The router only answers when it is confident. Everything else goes to the LLM.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from myata.brain.text import content_words, words_match
from myata.skills.base import Skill

EXTRA_WORD_PENALTY = 0.8   # every unknown word in the command lowers confidence
AMBIGUITY_MARGIN = 0.05    # two different skills this close means "not sure"


@dataclass(frozen=True)
class Match:
    skill: Skill
    score: float


def phrase_score(command: list[str], phrase: list[str]) -> float:
    """Share of phrase words found in the command, lowered for extra words."""
    if not phrase or not command:
        return 0.0
    used: set[int] = set()
    for word in phrase:
        for i, candidate in enumerate(command):
            if i not in used and words_match(candidate, word):
                used.add(i)
                break
    coverage = len(used) / len(phrase)
    extra = len(command) - len(used)
    return coverage * EXTRA_WORD_PENALTY**extra


class Router:
    def __init__(self, skills: Iterable[Skill], threshold: float, stop_words: Iterable[str] = ()):
        self._threshold = threshold
        self._stop_words = frozenset(stop_words)
        self._phrases = [
            (content_words(p, self._stop_words), s)
            for s in skills
            if not s.needs_args  # skills with required arguments need the LLM
            for p in s.phrases
        ]

    def match(self, text: str) -> Match | None:
        command = content_words(text, self._stop_words)
        if not command:
            return None

        best: dict[str, Match] = {}
        for phrase, item in self._phrases:
            score = float(command == phrase) if item.exact else phrase_score(command, phrase)
            if item.name not in best or score > best[item.name].score:
                best[item.name] = Match(item, score)

        ranked = sorted(best.values(), key=lambda m: m.score, reverse=True)
        if not ranked or ranked[0].score < self._threshold:
            return None
        if len(ranked) > 1 and ranked[0].score - ranked[1].score < AMBIGUITY_MARGIN:
            return None
        return ranked[0]
