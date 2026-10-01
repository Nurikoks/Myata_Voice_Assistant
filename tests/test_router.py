from myata.brain.router import Router
from myata.skills.registry import build_registry
from tests.fakes import make_config


def make_router():
    config = make_config()
    return Router(build_registry("windows", config), config.router.threshold)


def test_exact_phrases():
    router = make_router()
    assert router.match("открой ютуб").skill.name == "open_youtube"
    assert router.match("сколько времени").skill.name == "tell_time"
    assert router.match("открой блокнот").skill.name == "launch_notepad"


def test_close_phrase_still_matches():
    assert make_router().match("открой пожалуйста ютуб").skill.name == "open_youtube"


def test_unknown_or_empty():
    router = make_router()
    assert router.match("расскажи анекдот про программистов") is None
    assert router.match("") is None
    assert router.match("!!!") is None


def test_stop_needs_exact_match():
    router = make_router()
    assert router.match("стоп").skill.name == "shutdown_assistant"
    match = router.match("стол")
    assert match is None or match.skill.name != "shutdown_assistant"
