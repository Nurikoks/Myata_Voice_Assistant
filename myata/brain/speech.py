"""Make LLM text safe to read out loud."""

from __future__ import annotations

import re

_THINK = re.compile(r"<think>.*?(</think>|$)", re.DOTALL)
_CODE = re.compile(r"```.*?(```|$)", re.DOTALL)
_URL = re.compile(r"https?://\S+")
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_MARKUP = re.compile(r"[*_`#>|~]")
_EMOJI = re.compile("[\U0001f000-\U0001faff\u2600-\u27bf\ufe0f\u200d]")
_SENTENCE_END = (".", "!", "?", "…")


def clean_for_speech(text: str, max_chars: int) -> str:
    text = _THINK.sub(" ", text)
    text = _CODE.sub(" ", text)
    text = _URL.sub(" ", text)

    sentences = []
    for line in text.splitlines():
        line = _BULLET.sub("", line)
        line = _EMOJI.sub("", _MARKUP.sub("", line))
        line = " ".join(line.split())
        if not line:
            continue
        if not line.endswith(_SENTENCE_END + (":", ",", ";")):
            line += "."
        sentences.append(line)
    text = " ".join(sentences)
    return _shorten(text, max_chars)


def _shorten(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    end = max(cut.rfind(mark) for mark in _SENTENCE_END)
    if end >= max_chars // 3:
        return cut[: end + 1]
    return cut.rsplit(" ", 1)[0] + "."
