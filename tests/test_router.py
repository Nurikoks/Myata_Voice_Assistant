from myata.brain.router import Router, phrase_score
from myata.skills.registry import build_registry
from tests.fakes import make_config


def make_router():
    config = make_config()
    registry = build_registry("windows", config)
    return Router(registry, config.router.threshold, config.router.stop_words)


def name_of(text):
    match = make_router().match(text)
    return match.skill.name if match else None


def test_exact_phrases():
    assert name_of("открой ютуб") == "open_youtube"
    assert name_of("сколько времени") == "tell_time"
    assert name_of("открой блокнот") == "launch_notepad"


def test_word_forms_order_and_filler_words():
    assert name_of("открой пожалуйста ютуб") == "open_youtube"
    assert name_of("сколько там сейчас времени") == "tell_time"
    assert name_of("ютуб открой") == "open_youtube"
    assert name_of("открыть ютуб") == "open_youtube"


def test_unsure_cases_go_to_llm():
    assert name_of("закинь мне ютуб") is None            # unknown verb
    assert name_of("открой ютуб и найди котиков") is None  # too many extra words
    assert name_of("расскажи анекдот") is None
    assert name_of("") is None
    assert name_of("!!!") is None


def test_stop_needs_exact_match():
    assert name_of("стоп") == "shutdown_assistant"
    assert name_of("стоп пожалуйста") == "shutdown_assistant"
    assert name_of("стол") is None


def test_skills_with_required_args_are_never_fast():
    assert name_of("найди котиков") is None


def test_phrase_score():
    assert phrase_score(["открой", "ютуб"], ["открой", "ютуб"]) == 1.0
    assert phrase_score(["открой"], ["открой", "ютуб"]) == 0.5
    assert phrase_score([], ["ютуб"]) == 0.0
