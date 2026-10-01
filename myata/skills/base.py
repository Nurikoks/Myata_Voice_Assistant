"""Data types shared by all skills."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from myata.config import Config
from myata.oslayer import OSLayer

ALL_PLATFORMS = frozenset({"windows", "linux"})
NO_PARAMETERS: Mapping[str, Any] = {"type": "object", "properties": {}}


@dataclass(frozen=True)
class SkillResult:
    speech: str               # what Myata says back
    ok: bool = True           # False if the action failed
    stop: bool = False        # True if the assistant should shut down
    data: str | None = None   # facts for the LLM to phrase the answer; speech is the fallback


@dataclass(frozen=True)
class SkillContext:
    os: OSLayer
    config: Config
    text: str                                              # normalized command text
    args: Mapping[str, Any] = field(default_factory=dict)  # validated arguments


Handler = Callable[[SkillContext], SkillResult]


@dataclass(frozen=True)
class Skill:
    name: str
    description: str                 # shown to the LLM as the tool description
    phrases: tuple[str, ...]         # example phrases for the fast path (can be empty)
    handler: Handler
    platforms: frozenset[str] = ALL_PLATFORMS
    exact: bool = False              # fast path: only an exact phrase match triggers it
    parameters: Mapping[str, Any] = field(default_factory=lambda: NO_PARAMETERS)
    dangerous: bool = False          # ask for voice confirmation before running
    confirm: str = ""                # custom confirmation question
    llm: bool = True                 # the LLM may call this skill (False: never, e.g. "стоп")
    tool: bool = True                # listed in the LLM tools; hidden ones keep the list short
    requires: frozenset[str] = frozenset()  # OS capabilities it needs (oslayer.base)
    number_arg: str | None = None    # fast path: a number in the command goes to this argument

    @property
    def needs_args(self) -> bool:
        return bool(self.parameters.get("required"))
