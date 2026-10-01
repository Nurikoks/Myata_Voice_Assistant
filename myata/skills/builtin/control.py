"""Control the assistant itself."""

from __future__ import annotations

from myata.skills.base import SkillContext, SkillResult
from myata.skills.registry import skill


@skill(
    name="shutdown_assistant",
    description="Turn the assistant off",
    phrases=["выключись", "отключись", "стоп"],
    exact=True,  # fuzzy matching made "стол" (0.75 similar to "стоп") turn Myata off
    llm=False,   # only an explicit command turns Myata off, never a guess of the LLM
)
def shutdown_assistant(ctx: SkillContext) -> SkillResult:
    return SkillResult(ctx.config.assistant.phrases.goodbye, stop=True)
