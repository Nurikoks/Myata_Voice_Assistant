"""Tell the current time."""

from __future__ import annotations

from datetime import datetime

from myata.brain.text import plural_ru
from myata.skills.base import SkillContext, SkillResult
from myata.skills.registry import skill


def format_time(hour: int, minute: int) -> str:
    hours = f"{hour} {plural_ru(hour, ('час', 'часа', 'часов'))}"
    if minute == 0:
        return f"Сейчас {hours} ровно"
    minutes = f"{minute} {plural_ru(minute, ('минута', 'минуты', 'минут'))}"
    return f"Сейчас {hours} {minutes}"


@skill(
    name="tell_time",
    description="Say the current local time",
    phrases=["который час", "сколько времени"],
)
def tell_time(ctx: SkillContext) -> SkillResult:
    now = datetime.now()
    return SkillResult(format_time(now.hour, now.minute))
