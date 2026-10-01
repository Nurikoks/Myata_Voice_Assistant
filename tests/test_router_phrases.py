from myata.brain.morph import Morph
from myata.brain.router import Router
from myata.config import load_config
from myata.skills.registry import build_registry
from tests.test_config import ROOT


def test_every_phrase_reaches_its_own_skill():
    """No two skills fight over a phrase from the real config.yaml.

    Uses pymorphy3 when it is installed, the prefix heuristic otherwise.
    """
    config = load_config(ROOT / "config.yaml")
    morph = Morph.load()
    for os_name in ("windows", "linux"):
        skills = list(build_registry(os_name, config))
        router = Router(skills, config.router.threshold, config.router.stop_words, morph)
        for item in skills:
            for phrase in item.phrases:
                command = f"{phrase} 30" if item.number_arg else phrase
                match = router.match(command)
                assert match is not None, f"{command!r} matched nothing on {os_name}"
                assert match.skill.name == item.name, f"{command!r} went to {match.skill.name}"
