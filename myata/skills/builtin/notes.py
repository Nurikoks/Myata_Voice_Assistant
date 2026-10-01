"""Voice notes in a plain Markdown file (skills.notes_file in config.yaml)."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from myata.brain.text import plural_ru
from myata.skills.base import SkillContext, SkillResult
from myata.skills.registry import skill

log = logging.getLogger(__name__)


def _file(ctx: SkillContext) -> Path:
    return Path(ctx.config.skills.notes_file).expanduser()


def read_notes_file(path: Path) -> list[str]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line[2:] for line in lines if line.startswith("- ")]


@skill(
    name="add_note",
    description=(
        "Save a note or reminder text for later (запиши, запомни, заметка). "
        "Only for notes, not for search or apps."
    ),
    phrases=[],  # the note text comes from the LLM
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The note text, as the user said it"}
        },
        "required": ["text"],
    },
)
def add_note(ctx: SkillContext) -> SkillResult:
    path = _file(ctx)
    text = " ".join(str(ctx.args["text"]).split())
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(f"- {stamp} | {text}\n")
    except OSError as e:
        log.warning("Cannot write %s: %s", path, e)
        return SkillResult(ctx.config.assistant.phrases.failed, ok=False)
    return SkillResult("Записала, сэр")


@skill(
    name="read_notes",
    description="Read the user's saved notes (заметки) and answer questions about them",
    phrases=["прочитай заметки", "что в заметках", "мои заметки"],
)
def read_notes(ctx: SkillContext) -> SkillResult:
    notes = read_notes_file(_file(ctx))
    if not notes:
        return SkillResult("Заметок пока нет, сэр")
    last = notes[-ctx.config.skills.notes_to_read :]
    count = f"{len(notes)} {plural_ru(len(notes), ('заметка', 'заметки', 'заметок'))}"
    newest = last[-1].split("|", 1)[-1].strip()
    return SkillResult(
        f"У вас {count}. Последняя: {newest}",
        data=f"Saved notes ({len(notes)} total, newest last):\n" + "\n".join(last),
    )


@skill(
    name="clear_notes",
    description="Delete all saved notes",
    phrases=["удали все заметки", "очисти заметки"],
    dangerous=True,
    confirm="Удалить все заметки, сэр? Скажите да или нет.",
)
def clear_notes(ctx: SkillContext) -> SkillResult:
    path = _file(ctx)
    try:
        path.unlink(missing_ok=True)
    except OSError as e:
        log.warning("Cannot delete %s: %s", path, e)
        return SkillResult(ctx.config.assistant.phrases.failed, ok=False)
    return SkillResult("Заметки удалены")
