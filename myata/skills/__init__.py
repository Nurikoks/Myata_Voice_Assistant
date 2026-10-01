"""Skills are everything Myata can do. See registry.py for how to add one."""

from myata.skills.base import ALL_PLATFORMS, Skill, SkillContext, SkillResult
from myata.skills.registry import SkillRegistry, build_registry, skill

__all__ = [
    "ALL_PLATFORMS",
    "Skill",
    "SkillContext",
    "SkillRegistry",
    "SkillResult",
    "build_registry",
    "skill",
]
