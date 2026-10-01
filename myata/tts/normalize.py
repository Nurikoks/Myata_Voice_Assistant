"""Prepare text for a neural TTS voice.

Silero reads Cyrillic only: digits and Latin words have to be spelled out.
Numbers become words through num2words (if it is installed), and Latin names
are replaced using tts.replacements from config.yaml ("VS Code": "вэ эс код").
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping

log = logging.getLogger(__name__)

NumberSpeller = Callable[[int], str]

_TIME = re.compile(r"\b(\d{1,2}):(\d{2})\b")
_DECIMAL = re.compile(r"\b(\d+)[.,](\d+)\b")
_NUMBER = re.compile(r"\d+")

# "1 минута" must become "одна минута", not "один минута". num2words always gives
# the masculine form, so these feminine nouns fix "один"/"два" right before them.
_FEMININE = re.compile(
    r"\b(один|два)(\s+(?:минут|секунд|тысяч|недел|копе|штук|вкладк|задач|строк|ноч)\w*)",
    re.IGNORECASE,
)
_FEMININE_FORMS = {"один": "одна", "два": "две"}


def default_speller() -> NumberSpeller | None:
    try:
        from num2words import num2words
    except ImportError:
        log.warning("num2words is not installed, numbers will be read as digits")
        return None
    return lambda n: num2words(n, lang="ru")


def prepare_for_speech(
    text: str, replacements: Mapping[str, str], speller: NumberSpeller | None
) -> str:
    text = apply_replacements(text, replacements)
    if speller is not None:
        text = _TIME.sub(r"\1 \2", text)
        text = _DECIMAL.sub(r"\1 и \2", text)
        text = text.replace("%", " процентов")
        text = _NUMBER.sub(lambda m: speller(int(m.group())), text)
        text = _FEMININE.sub(_feminine, text)
    return " ".join(text.split())


def apply_replacements(text: str, replacements: Mapping[str, str]) -> str:
    # Longest first, so "VS Code" wins over "Code".
    for source in sorted(replacements, key=len, reverse=True):
        pattern = re.compile(rf"(?<!\w){re.escape(source)}(?!\w)", re.IGNORECASE)
        text = pattern.sub(replacements[source], text)
    return text


def _feminine(match: re.Match[str]) -> str:
    word = match.group(1)
    fixed = _FEMININE_FORMS[word.lower()]
    if word[0].isupper():
        fixed = fixed.capitalize()
    return fixed + match.group(2)
