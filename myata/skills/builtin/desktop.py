"""Clipboard and screenshots."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from myata.oslayer import CLIPBOARD, SCREENSHOT, OSActionError
from myata.skills.base import SkillContext, SkillResult
from myata.skills.registry import skill

log = logging.getLogger(__name__)

SPOKEN_CLIPBOARD_CHARS = 200


@skill(
    name="read_clipboard",
    description=(
        "Get the text the user copied (буфер обмена). Use it to read, explain, "
        "translate or summarize the copied text."
    ),
    phrases=["что в буфере обмена", "прочитай буфер обмена", "что я скопировал"],
    requires=[CLIPBOARD],
)
def read_clipboard(ctx: SkillContext) -> SkillResult:
    try:
        text = ctx.os.read_clipboard().strip()
    except OSActionError as e:
        log.warning("Cannot read the clipboard: %s", e)
        return SkillResult(ctx.config.assistant.phrases.failed, ok=False)
    if not text:
        return SkillResult("В буфере обмена нет текста, сэр")
    limit = ctx.config.skills.clipboard_max_chars
    # The text goes to the LLM only as data: during that call it has no tools,
    # so copied text cannot make Myata run anything.
    return SkillResult(
        f"В буфере обмена: {text[:SPOKEN_CLIPBOARD_CHARS]}",
        data=f"Clipboard text ({len(text)} characters):\n{text[:limit]}",
    )


@skill(
    name="take_screenshot",
    description="Take a screenshot of the screen and save it to a file",
    phrases=["сделай скриншот", "скриншот", "сними экран"],
    requires=[SCREENSHOT],
)
def take_screenshot(ctx: SkillContext) -> SkillResult:
    folder = Path(ctx.config.skills.screenshots_dir).expanduser()
    path = folder / datetime.now().strftime("screenshot_%Y-%m-%d_%H-%M-%S.png")
    try:
        ctx.os.screenshot(path)
    except OSActionError as e:
        log.warning("Screenshot failed: %s", e)
        return SkillResult(ctx.config.assistant.phrases.failed, ok=False)
    log.info("Screenshot saved to %s", path)
    return SkillResult("Скриншот сохранён, сэр")
