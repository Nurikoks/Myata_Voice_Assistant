"""Skill registry.

To add a skill, create a file in myata/skills/builtin/ and decorate a function:

    @skill(name="tell_time", description="Say the current time",
           phrases=["который час"])
    def tell_time(ctx: SkillContext) -> SkillResult: ...

Optional: parameters (JSON schema for the LLM), dangerous=True (voice confirmation),
llm=False (fast path only), exact=True (exact phrase only), platforms={"windows"}.

Every module in that folder is imported automatically, so the core does not change.
Websites and applications come from config.yaml (see factories.py).
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from collections.abc import Callable, Iterable, Iterator, Mapping
from typing import Any

from myata.config import Config
from myata.skills.base import ALL_PLATFORMS, NO_PARAMETERS, Handler, Skill
from myata.skills.factories import make_app_skill, make_site_skill

log = logging.getLogger(__name__)

_DECLARED: list[Skill] = []


def skill(
    *,
    name: str,
    description: str,
    phrases: Iterable[str],
    platforms: Iterable[str] = ALL_PLATFORMS,
    exact: bool = False,
    parameters: Mapping[str, Any] = NO_PARAMETERS,
    dangerous: bool = False,
    confirm: str = "",
    llm: bool = True,
) -> Callable[[Handler], Handler]:
    """Declare a skill. The function itself is returned unchanged."""

    def decorator(func: Handler) -> Handler:
        _DECLARED.append(
            Skill(
                name=name,
                description=description,
                phrases=tuple(phrases),
                handler=func,
                platforms=frozenset(platforms),
                exact=exact,
                parameters=parameters,
                dangerous=dangerous,
                confirm=confirm,
                llm=llm,
            )
        )
        return func

    return decorator


def load_builtin_skills() -> list[Skill]:
    """Import every module in myata.skills.builtin and return the declared skills."""
    package = importlib.import_module("myata.skills.builtin")
    for module in pkgutil.iter_modules(package.__path__):
        importlib.import_module(f"{package.__name__}.{module.name}")
    return list(_DECLARED)


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, item: Skill) -> None:
        if item.name in self._skills:
            raise ValueError(f"duplicate skill name: {item.name}")
        self._skills[item.name] = item

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def __iter__(self) -> Iterator[Skill]:
        return iter(self._skills.values())

    def __len__(self) -> int:
        return len(self._skills)


def build_registry(
    os_name: str, config: Config, declared: Iterable[Skill] | None = None
) -> SkillRegistry:
    """Collect the skills that work on this OS: code skills plus config skills."""
    registry = SkillRegistry()
    for item in load_builtin_skills() if declared is None else declared:
        if os_name in item.platforms:
            registry.register(item)
        else:
            log.info("Skill %s is not available on %s, skipped", item.name, os_name)

    for site in config.sites:
        registry.register(make_site_skill(site))

    for app in config.apps:
        argv = app.commands.get(os_name)
        if argv is None:
            log.info("App %s has no command for %s, skipped", app.name, os_name)
            continue
        registry.register(make_app_skill(app, argv, os_name))

    log.info("Registered %d skills: %s", len(registry), ", ".join(s.name for s in registry))
    return registry
