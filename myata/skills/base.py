"""Data types shared by all skills."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from myata.config import Config
from myata.oslayer import OSLayer

ALL_PLATFORMS = frozenset({"windows", "linux"})


@dataclass(frozen=True)
class SkillResult:
    speech: str          # what Myata says back
    ok: bool = True      # False if the action failed
    stop: bool = False   # True if the assistant should shut down


@dataclass(frozen=True)
class SkillContext:
    os: OSLayer
    config: Config
    text: str            # normalized command text


Handler = Callable[[SkillContext], SkillResult]


@dataclass(frozen=True)
class Skill:
    name: str
    description: str             # also used as the tool description for the LLM in stage 2
    phrases: tuple[str, ...]     # example phrases for the fast path
    handler: Handler
    platforms: frozenset[str] = ALL_PLATFORMS
    exact: bool = False          # only an exact phrase match triggers it
