from myata.core.assistant import Outcome
from tests.fakes import FakeLLM, FakeOS, danger_skill, make_assistant, text_reply, tool_reply


def test_wake_word_then_command():
    assistant, tts, os_layer, clock = make_assistant()
    assert assistant.on_utterance("мята") is Outcome.LISTENING
    assert tts.spoken == ["Слушаю"]
    clock.now += 3
    assert assistant.on_utterance("открой ютуб") is Outcome.HANDLED
    assert os_layer.opened == ["https://youtube.com"]
    assert tts.spoken[-1] == "Открываю ютуб"


def test_listen_window_expires():
    assistant, _, os_layer, clock = make_assistant()
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


def test_failed_launch_is_reported_honestly():
    assistant, tts, _, _ = make_assistant(FakeOS(fail_launch=True))
    assistant.handle_command("запусти лигу легенд")
    assert tts.spoken[-1] == "Не получилось, сэр"


def test_llm_runs_a_skill():
    llm = FakeLLM(tool_reply("launch_discord"))
    assistant, tts, os_layer, _ = make_assistant(llm=llm)
    assistant.handle_command("закинь мне дискорд")
    assert os_layer.launched == [["discord"]]
    assert tts.spoken[-1] == "Открываю дискорд"


def test_dialog_context_reaches_llm():
    llm = FakeLLM(tool_reply("launch_discord"))
    assistant, _, _, _ = make_assistant(llm=llm)
    assistant.handle_command("открой ютуб")          # fast path, stored in history
    assistant.handle_command("а теперь дискорд")     # goes to LLM with history
    messages, _ = llm.requests[0]
    assert messages[1]["content"] == "открой ютуб"
    assert messages[2]["tool_calls"][0]["function"]["name"] == "open_youtube"


def test_question_opens_window_without_wake_word():
    llm = FakeLLM(text_reply("Какой фильм, сэр?"), text_reply("Отличный выбор, сэр."))
    assistant, tts, _, clock = make_assistant(llm=llm)
    assistant.on_utterance("мята посоветуй фильм")
    clock.now += 3
    assert assistant.on_utterance("что-нибудь про космос") is Outcome.HANDLED
    assert tts.spoken[-1] == "Отличный выбор, сэр."


def test_dangerous_skill_needs_yes():
    calls: list[str] = []
    assistant, tts, _, clock = make_assistant(extra_skills=[danger_skill(calls)])
    assistant.on_utterance("мята форматируй диск")
    assert calls == [] and tts.spoken[-1] == "Вы уверены, сэр? Скажите да или нет."
    clock.now += 5
    assistant.on_utterance("да")                      # no wake word needed
    assert calls == ["boom"]


def test_dangerous_skill_cancelled():
    calls: list[str] = []
    assistant, tts, _, _ = make_assistant(extra_skills=[danger_skill(calls)])
    assistant.handle_command("форматируй диск")
    assistant.handle_command("нет")
    assert calls == [] and tts.spoken[-1] == "Отменяю"


def test_confirmation_expires():
    calls: list[str] = []
    assistant, _, _, clock = make_assistant(extra_skills=[danger_skill(calls)])
    assistant.handle_command("форматируй диск")
    clock.now += 60
    assistant.handle_command("да")                    # too late, treated as a new command
    assert calls == []


def test_reply_window_after_a_bare_name():
    assistant, _, os_layer, clock = make_assistant()
    assert assistant.reply_window == 0
    assistant.on_utterance("мята")
    assert assistant.reply_window == 6
    clock.now += 10                                   # slow answer: the loop already decided
    assert assistant.on_reply("открой ютуб") is Outcome.HANDLED
    assert os_layer.opened == ["https://youtube.com"]
    assert assistant.reply_window == 0


def test_stop_waiting():
    assistant, _, _, _ = make_assistant()
    assistant.on_utterance("мята")
    assistant.stop_waiting()
    assert assistant.reply_window == 0


def test_is_addressed():
    assistant, _, _, _ = make_assistant()
    assert assistant.is_addressed("Мята, который час?")
    assert not assistant.is_addressed("Мать, который час?")
