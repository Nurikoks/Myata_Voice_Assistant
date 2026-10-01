from myata.brain.history import History, Turn
from tests.fakes import FakeClock


def test_keeps_only_last_turns():
    history = History(max_turns=2, ttl_sec=300, clock=FakeClock())
    for i in range(3):
        history.add(Turn(f"вопрос {i}", f"ответ {i}"))
    contents = [m["content"] for m in history.messages()]
    assert contents == ["вопрос 1", "ответ 1", "вопрос 2", "ответ 2"]


def test_forgets_after_silence():
    clock = FakeClock()
    history = History(max_turns=6, ttl_sec=300, clock=clock)
    history.add(Turn("привет", "Здравствуйте, сэр"))
    clock.now += 301
    assert history.messages() == []


def test_actions_are_stored_as_tool_calls():
    history = History(max_turns=6, ttl_sec=300, clock=FakeClock())
    history.add(Turn("открой ютуб", "Открываю ютуб", "open_youtube", {}))
    user, call, result = history.messages()
    assert user == {"role": "user", "content": "открой ютуб"}
    assert call["tool_calls"][0]["function"]["name"] == "open_youtube"
    assert result == {"role": "tool", "content": "Открываю ютуб", "tool_name": "open_youtube"}


def test_disabled():
    history = History(max_turns=0, ttl_sec=300, clock=FakeClock())
    history.add(Turn("a", "b"))
    assert len(history) == 0
