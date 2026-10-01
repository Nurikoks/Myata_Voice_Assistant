import pytest

from myata.skills.base import Skill, SkillResult
from myata.skills.registry import SkillRegistry, build_registry
from tests.fakes import make_config


def _skill(name, platforms=frozenset({"windows", "linux"})):
    return Skill(name, "test", ("фраза",), lambda ctx: SkillResult("ok"), platforms)


def test_windows_only_app_is_skipped_on_linux():
    names = {s.name for s in build_registry("linux", make_config())}
    assert "launch_notepad" in names
    assert "launch_league_of_legends" not in names
    assert "tell_time" in names


def test_platform_filter_for_code_skills():
    declared = [_skill("everywhere"), _skill("win_only", frozenset({"windows"}))]
    names = {s.name for s in build_registry("linux", make_config(), declared)}
    assert "everywhere" in names
    assert "win_only" not in names


def test_duplicate_names_fail():
    registry = SkillRegistry()
    registry.register(_skill("same"))
    with pytest.raises(ValueError):
        registry.register(_skill("same"))
