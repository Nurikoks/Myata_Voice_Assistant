from myata.brain.router import Router
from myata.config import load_config
from myata.skills.registry import build_registry
from tests.test_config import ROOT


def test_every_phrase_reaches_its_own_skill():
    """No two skills fight over a phrase from the real config.yaml."""
    config = load_config(ROOT / "config.yaml")
    for os_name in ("windows", "linux"):
        skills = list(build_registry(os_name, config))
        router = Router(skills, config.router.threshold, config.router.stop_words)
        for item in skills:
            for phrase in item.phrases:
                match = router.match(phrase)
                assert match is not None, f"{phrase!r} matched nothing on {os_name}"
                assert match.skill.name == item.name, f"{phrase!r} went to {match.skill.name}"
