"""Control the assistant itself."""

from __future__ import annotations

from myata.skills.base import SkillContext, SkillResult
from myata.skills.registry import skill

REPEAT_SKILL = "repeat_last"


@skill(
    name="shutdown_assistant",
    description="Turn the assistant off",
    phrases=[
        "выключись", "отключись", "стоп", "отключайся", "выключайся",
        "выключи себя", "отключи себя",
    ],
    exact=True,  # fuzzy matching made "стол" (0.75 similar to "стоп") turn Myata off
    llm=False,   # only an explicit command turns Myata off, never a guess of the LLM
)
def shutdown_assistant(ctx: SkillContext) -> SkillResult:
    return SkillResult(ctx.config.assistant.phrases.goodbye, stop=True)


@skill(
    name=REPEAT_SKILL,
    description="Repeat the last action",
    phrases=["ещё раз", "повтори", "повтори ещё раз", "давай ещё раз", "сделай ещё раз"],
    llm=False,  # the assistant core replaces it with the last action, see core/assistant.py
)
def repeat_last(ctx: SkillContext) -> SkillResult:
    # Only reached when there is nothing to repeat.
    return SkillResult("Пока нечего повторять, сэр", ok=False)
