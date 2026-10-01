"""Word forms for the fast router.

With pymorphy3 every word is reduced to its dictionary form ("открой" and
"открыть" both become "открыть"), so "громкость" and "громче" no longer look
alike. Without pymorphy3, or for words it does not know (brand names like
"ютуб"), the old prefix heuristic from text.py is used.
"""

from __future__ import annotations

import logging

from myata.brain.text import words_match

log = logging.getLogger(__name__)


class Morph:
    def __init__(self, analyzer=None) -> None:
        """analyzer: a pymorphy3.MorphAnalyzer, or None for the prefix heuristic only.

        Use Morph.load() to get pymorphy3 when it is installed.
        """
        self._analyzer = analyzer
        self._lemmas: dict[str, str] = {}
        self._known: dict[str, bool] = {}

    @classmethod
    def load(cls) -> Morph:
        try:
            import pymorphy3
        except ImportError:
            log.warning("pymorphy3 is not installed, the router uses a simpler word match")
            return cls()
        return cls(pymorphy3.MorphAnalyzer(lang="ru"))

    @property
    def available(self) -> bool:
        return self._analyzer is not None

    def lemma(self, word: str) -> str:
        if self._analyzer is None:
            return word
        if word not in self._lemmas:
            self._lemmas[word] = self._analyzer.parse(word)[0].normal_form.replace("ё", "е")
        return self._lemmas[word]

    def known(self, word: str) -> bool:
        if self._analyzer is None:
            return False
        if word not in self._known:
            self._known[word] = bool(self._analyzer.word_is_known(word))
        return self._known[word]

    def same(self, a: str, b: str) -> bool:
        """True for two forms of one word."""
        if a == b:
            return True
        if self._analyzer is None:
            return words_match(a, b)
        if self.lemma(a) == self.lemma(b):
            return True
        if self.known(a) and self.known(b):
            return False  # two real, different words: "громкость" is not "громче"
        return words_match(a, b)  # an unknown word: fall back to the prefix heuristic
