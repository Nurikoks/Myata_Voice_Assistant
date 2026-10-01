from myata.core.assistant import Outcome
from tests.fakes import FakeOS, make_assistant


def test_wake_word_then_command():
    assistant, tts, os_layer, clock = make_assistant()
    assert assistant.on_utterance("мята") is Outcome.LISTENING
    assert tts.spoken == ["Слушаю"]
    clock.now += 3
    assert assistant.on_utterance("открой ютуб") is Outcome.HANDLED
    assert os_layer.opened == ["https://youtube.com"]
    assert tts.spoken[-1] == "Открываю ютуб"


def test_listen_window_expires():
    assistant, tts, os_layer, clock = make_assistant()
    assistant.on_utterance("мята")
    clock.now += 7
    assert assistant.on_utterance("открой ютуб") is Outcome.IGNORED
    assert os_layer.opened == []


def test_speech_without_wake_word_is_ignored():
    assistant, tts, _, _ = make_assistant()
    assert assistant.on_utterance("открой ютуб") is Outcome.IGNORED
    assert tts.spoken == []


def test_wake_word_and_command_in_one_phrase():
    assistant, _, os_layer, _ = make_assistant()
    assert assistant.on_utterance("мята открой блокнот") is Outcome.HANDLED
    assert os_layer.launched == [["notepad"]]


def test_stop():
    assistant, tts, _, _ = make_assistant()
    assert assistant.on_utterance("мята стоп") is Outcome.STOP
    assert tts.spoken[-1] == "До связи, сэр"


def test_unknown_command():
    assistant, tts, _, _ = make_assistant()
    assert assistant.handle_command("спой песню про котиков") is Outcome.HANDLED
    assert tts.spoken[-1] == "Не понял команду"


def test_failed_launch_is_reported_honestly():
    assistant, tts, _, _ = make_assistant(FakeOS(fail_launch=True))
    assistant.handle_command("запусти лигу легенд")
    assert tts.spoken[-1] == "Не получилось, сэр"
