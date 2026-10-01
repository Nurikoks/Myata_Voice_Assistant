from myata.brain.brain import Reply, SkillCall
from tests.fakes import FakeLLM, make_brain, offline, text_reply, tool_reply


def test_fast_path_does_not_call_llm():
    llm = FakeLLM()
    brain, _ = make_brain(llm)
    decision = brain.decide("открой ютуб")
    assert isinstance(decision, SkillCall)
    assert decision.skill.name == "open_youtube"
    assert decision.source == "fast"
    assert llm.requests == []


def test_llm_tool_call_with_arguments():
    llm = FakeLLM(tool_reply("web_search", query="котики", site="youtube"))
    brain, _ = make_brain(llm)
    decision = brain.decide("найди на ютубе котиков")
    assert isinstance(decision, SkillCall)
    assert decision.skill.name == "web_search"
    assert decision.args == {"query": "котики", "site": "youtube"}
    assert decision.source == "llm"


def test_llm_free_answer_is_cleaned():
    brain, _ = make_brain(FakeLLM(text_reply("**Привет, сэр!** Чем помочь?")))
    assert brain.decide("как дела") == Reply("Привет, сэр! Чем помочь?")


def test_unknown_or_forbidden_tool_is_ignored():
    for name in ("rm_rf", "shutdown_assistant"):
        brain, config = make_brain(FakeLLM(tool_reply(name)))
        assert brain.decide("сделай что-нибудь") == Reply(config.assistant.phrases.not_understood)


def test_bad_arguments_are_rejected():
    brain, config = make_brain(FakeLLM(tool_reply("web_search", site="bing")))
    assert brain.decide("поищи") == Reply(config.assistant.phrases.not_understood)


def test_llm_offline():
    brain, config = make_brain(FakeLLM(offline()))
    assert brain.decide("как дела") == Reply(config.assistant.phrases.brain_offline)


def test_no_llm():
    brain, config = make_brain(None)
    assert brain.decide("как дела") == Reply(config.assistant.phrases.not_understood)


def test_prompt_tools_and_history():
    llm = FakeLLM(text_reply("Хорошо, сэр."), text_reply("Да, сэр."))
    brain, _ = make_brain(llm)
    brain.decide("как дела")
    brain.remember("как дела", "Хорошо, сэр.")
    brain.decide("точно?")

    messages, tools = llm.requests[1]
    system = messages[0]["content"]
    assert "Мята" in system and "1 октября 2026, четверг" in system
    assert "14:05" not in system  # the time would break Ollama's prompt cache every minute
    assert [m["content"] for m in messages[1:]] == ["как дела", "Хорошо, сэр.", "точно?"]
    names = {t["function"]["name"] for t in tools}
    assert "web_search" in names and "open_youtube" in names
    assert "shutdown_assistant" not in names  # fast path only


def test_time_placeholder_still_works():
    from datetime import datetime

    from myata.brain.prompt import build_system_prompt

    prompt = build_system_prompt("{name}: {time}", "Мята", datetime(2026, 10, 1, 9, 7))
    assert prompt == "Мята: 09:07"
