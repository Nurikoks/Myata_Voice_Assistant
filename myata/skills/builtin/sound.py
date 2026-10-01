"""Volume and media keys."""

from __future__ import annotations

import logging

from myata.brain.text import plural_ru
from myata.oslayer import MEDIA, MEDIA_KEYS, VOLUME, OSActionError
from myata.skills.base import SkillContext, SkillResult
from myata.skills.registry import skill

log = logging.getLogger(__name__)


def say_volume(level: int) -> str:
    return f"Громкость {level} {plural_ru(level, ('процент', 'процента', 'процентов'))}"


def _failed(ctx: SkillContext, error: OSActionError) -> SkillResult:
    log.warning("Sound action failed: %s", error)
    return SkillResult(ctx.config.assistant.phrases.failed, ok=False)


def _change_volume(ctx: SkillContext, delta: int) -> SkillResult:
    try:
        level = max(0, min(100, ctx.os.get_volume() + delta))
        ctx.os.set_volume(level)
    except OSActionError as e:
        return _failed(ctx, e)
    return SkillResult(say_volume(level))


def _mute(ctx: SkillContext, muted: bool) -> SkillResult:
    try:
        ctx.os.set_mute(muted)
    except OSActionError as e:
        return _failed(ctx, e)
    return SkillResult("Звук выключен" if muted else "Звук включён")


@skill(
    name="volume_up",
    description="Make the sound louder",
    phrases=[
        "громче", "погромче", "сделай громче", "прибавь звук", "увеличь громкость",
        "повысь громкость", "подними громкость",
    ],
    requires=[VOLUME],
    tool=False,  # not listed for the LLM (it has set_volume), fewer tools for a small model
)
def volume_up(ctx: SkillContext) -> SkillResult:
    return _change_volume(ctx, ctx.config.skills.volume_step)


@skill(
    name="volume_down",
    description="Make the sound quieter",
    phrases=[
        "тише", "потише", "сделай тише", "убавь звук", "уменьши громкость",
        "понизь громкость", "опусти громкость",
    ],
    requires=[VOLUME],
    tool=False,
)
def volume_down(ctx: SkillContext) -> SkillResult:
    return _change_volume(ctx, -ctx.config.skills.volume_step)


@skill(
    name="mute_sound",
    description="Mute the sound",
    phrases=["выключи звук", "отключи звук", "без звука"],
    requires=[VOLUME],
    tool=False,
)
def mute_sound(ctx: SkillContext) -> SkillResult:
    return _mute(ctx, True)


@skill(
    name="unmute_sound",
    description="Unmute the sound",
    phrases=["включи звук", "верни звук"],
    requires=[VOLUME],
    tool=False,
)
def unmute_sound(ctx: SkillContext) -> SkillResult:
    return _mute(ctx, False)


@skill(
    name="set_volume",
    description=(
        "Change the computer's sound volume (громкость, звук). Give level for an exact "
        "value, or direction to make it a bit louder or quieter, or mute to turn sound off/on."
    ),
    # Only used by the fast path together with a number: "громкость 30", "сделай звук на 50"
    phrases=["громкость", "звук", "сделай громкость", "поставь громкость", "сделай звук"],
    number_arg="level",
    requires=[VOLUME],
    parameters={
        "type": "object",
        "properties": {
            "level": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Volume in percent",
            },
            "direction": {"type": "string", "enum": ["up", "down"]},
            "mute": {"type": "boolean", "description": "true to mute, false to unmute"},
        },
    },
)
def set_volume(ctx: SkillContext) -> SkillResult:
    # Small models often fill every argument ({"level": 50, "mute": false}),
    # so the order of these checks matters.
    if ctx.args.get("mute") is True:
        return _mute(ctx, True)
    if "level" in ctx.args:
        level = int(ctx.args["level"])
        try:
            ctx.os.set_volume(level)
        except OSActionError as e:
            return _failed(ctx, e)
        return SkillResult(say_volume(level))
    if "direction" in ctx.args:
        step = ctx.config.skills.volume_step
        return _change_volume(ctx, -step if ctx.args["direction"] == "down" else step)
    return _mute(ctx, False)


def _press(ctx: SkillContext, key: str, reply: str) -> SkillResult:
    try:
        ctx.os.media_key(key)
    except OSActionError as e:
        return _failed(ctx, e)
    return SkillResult(reply)


MEDIA_REPLIES = {
    "play_pause": "Готово",
    "next": "Следующий трек",
    "previous": "Предыдущий трек",
    "stop": "Остановила",
}


@skill(
    name="media_play_pause",
    description="Pause or resume music or video",
    phrases=["пауза", "поставь на паузу", "сними с паузы", "плей"],
    requires=[MEDIA],
    tool=False,
)
def media_play_pause(ctx: SkillContext) -> SkillResult:
    return _press(ctx, "play_pause", MEDIA_REPLIES["play_pause"])


@skill(
    name="media_next",
    description="Next track",
    phrases=["следующий трек", "следующая песня", "переключи трек"],
    requires=[MEDIA],
    tool=False,
)
def media_next(ctx: SkillContext) -> SkillResult:
    return _press(ctx, "next", MEDIA_REPLIES["next"])


@skill(
    name="media_previous",
    description="Previous track",
    phrases=["предыдущий трек", "предыдущая песня"],
    requires=[MEDIA],
    tool=False,
)
def media_previous(ctx: SkillContext) -> SkillResult:
    return _press(ctx, "previous", MEDIA_REPLIES["previous"])


@skill(
    name="media_control",
    description=(
        "Control the music or video that is playing (музыка, трек, видео): "
        "play_pause toggles pause, next and previous switch tracks, stop stops it."
    ),
    phrases=[],
    requires=[MEDIA],
    parameters={
        "type": "object",
        "properties": {"action": {"type": "string", "enum": list(MEDIA_KEYS)}},
        "required": ["action"],
    },
)
def media_control(ctx: SkillContext) -> SkillResult:
    action = ctx.args["action"]
    return _press(ctx, action, MEDIA_REPLIES[action])
