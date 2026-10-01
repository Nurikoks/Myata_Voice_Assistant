"""System prompt and tool descriptions for the LLM."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from myata.skills.base import Skill

_MONTHS = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)
_WEEKDAYS = ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье")


def build_system_prompt(template: str, name: str, now: datetime) -> str:
    # Plain replace instead of str.format, so braces elsewhere in the prompt are safe.
    date = f"{now.day} {_MONTHS[now.month - 1]} {now.year}, {_WEEKDAYS[now.weekday()]}"
    return (
        template.replace("{name}", name)
        .replace("{date}", date)
        .replace("{time}", now.strftime("%H:%M"))
    )


def tool_spec(skill: Skill) -> dict[str, Any]:
    """A skill in the tool format Ollama expects."""
    return {
        "type": "function",
        "function": {
            "name": skill.name,
            "description": skill.description,
            "parameters": dict(skill.parameters),
        },
    }
