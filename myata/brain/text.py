"""Small text helpers shared by the wake detector and the router."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

_NOT_WORD = re.compile(r"[^\w\s]")


def normalize(text: str) -> str:
    """Lowercase, treat ё as е, drop punctuation and extra spaces."""
    text = text.lower().replace("ё", "е")
    text = _NOT_WORD.sub(" ", text)
    return " ".join(text.split())


def similarity(a: str, b: str) -> float:
    """How alike two strings are, from 0.0 to 1.0."""
    return SequenceMatcher(None, a, b).ratio()


def plural_ru(n: int, forms: tuple[str, str, str]) -> str:
    """Pick the Russian word form for a number: (1 час, 2 часа, 5 часов)."""
    n = abs(n)
    if 11 <= n % 100 <= 14:
        return forms[2]
    if n % 10 == 1:
        return forms[0]
    if 2 <= n % 10 <= 4:
        return forms[1]
    return forms[2]


def content_words(text: str, stop_words: frozenset[str] = frozenset()) -> list[str]:
    """Normalized words without filler words like "пожалуйста"."""
    return [w for w in normalize(text).split() if w not in stop_words]


_ENDING_LETTERS = frozenset("аеиоуыэюяйь")


def words_match(a: str, b: str) -> bool:
    """True for forms of the same word: "ютуб" and "ютубе", "открой" and "открыть".

    A cheap replacement for a full morphological analyzer: two words match when
    they share a long enough beginning. Short words may only differ in ending
    letters, so "лигу" matches "лига" but "стол" does not match "стоп".
    """
    if a == b:
        return True
    common = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        common += 1
    shortest = min(len(a), len(b))
    if common < max(3, shortest - 2):
        return False
    return shortest >= 5 or set(a[common:] + b[common:]) <= _ENDING_LETTERS
