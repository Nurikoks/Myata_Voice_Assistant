"""Fast path: match a command to a skill instantly, without the LLM.

Every example phrase of a skill is compared word by word with the command
(word order and word forms do not matter, filler words are ignored).
The router only answers when it is confident. Everything else goes to the LLM.

Numbers are arguments, not words: "громкость 30" only matches skills that take
a number (number_arg), and a command with a number never matches the others.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from myata.brain.morph import Morph
from myata.brain.text import content_words, words_match
from myata.skills.base import Skill

EXTRA_WORD_PENALTY = 0.8   # every unknown word in the command lowers confidence
AMBIGUITY_MARGIN = 0.05    # two different skills this close means "not sure"


@dataclass(frozen=True)
class Match:
    skill: Skill
    score: float
    args: dict[str, Any] = field(default_factory=dict)


def phrase_score(command: list[str], phrase: list[str], same=None) -> float:
    """Share of phrase words found in the command, lowered for extra words."""
    if not phrase or not command:
        return 0.0
    same = same or words_match
    used: set[int] = set()
    for word in phrase:
        for i, candidate in enumerate(command):
            if i not in used and same(candidate, word):
                used.add(i)
                break
    coverage = len(used) / len(phrase)
    extra = len(command) - len(used)
    return coverage * EXTRA_WORD_PENALTY**extra


class Router:
    def __init__(
        self,
        skills: Iterable[Skill],
        threshold: float,
        stop_words: Iterable[str] = (),
        morph: Morph | None = None,
    ):
        self._threshold = threshold
        self._morph = morph or Morph()
        self._stop_words = frozenset(stop_words)
        self._stop_lemmas = frozenset(self._morph.lemma(w) for w in self._stop_words)
        self._phrases = [
            (self._words(p), s)
            for s in skills
            if not s.needs_args  # skills with required arguments need the LLM
            for p in s.phrases
        ]

    def _words(self, text: str) -> list[str]:
        words = content_words(text, self._stop_words)
        return [w for w in words if self._morph.lemma(w) not in self._stop_lemmas]

    def match(self, text: str) -> Match | None:
        words = self._words(text)
        numbers = [int(w) for w in words if w.isdigit()]
        command = [w for w in words if not w.isdigit()]
        if not command:
            return None

        best: dict[str, Match] = {}
        for phrase, item in self._phrases:
            if bool(numbers) != (item.number_arg is not None):
                continue
            if item.exact:
                score = float(command == phrase and not numbers)
            else:
                score = phrase_score(command, phrase, self._morph.same)
            if item.name not in best or score > best[item.name].score:
                args = {item.number_arg: numbers[0]} if item.number_arg else {}
                best[item.name] = Match(item, score, args)

        ranked = sorted(best.values(), key=lambda m: m.score, reverse=True)
        if not ranked or ranked[0].score < self._threshold:
            return None
        if len(ranked) > 1 and ranked[0].score - ranked[1].score < AMBIGUITY_MARGIN:
            return None
        return ranked[0]
