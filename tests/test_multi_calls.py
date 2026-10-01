from myata.brain.brain import MultiCall, SkillCall
from myata.brain.llm import LLMReply, ToolCall
from tests.fakes import (
    FakeLLM,
    danger_skill,
    make_assistant,
    make_brain,
    make_config,
    offline,
    text_reply,
    tool_reply,
    tools_reply,
)


def test_two_apps_in_one_command():
    llm = FakeLLM(tools_reply(("launch_discord", {}), ("launch_notepad", {})))
    assistant, tts, os_layer, _ = make_assistant(llm=llm)
    assistant.handle_command("открой дискорд и блокнот")
    assert os_layer.launched == [["discord"], ["notepad"]]
    assert tts.spoken[-1] == "Открываю дискорд. Открываю блокнот."


def test_repeated_calls_are_merged_and_limited():
    calls = [("launch_discord", {})] * 2
    calls += [("launch_notepad", {}), ("open_youtube", {}), ("tell_time", {})]
    brain, _ = make_brain(FakeLLM(tools_reply(*calls)))
    decision = brain.decide("сделай всё")
    assert isinstance(decision, MultiCall)
    names = [c.skill.name for c in decision.calls]
    assert names == ["launch_discord", "launch_notepad", "open_youtube"]  # max_tool_calls = 3


def test_one_valid_call_among_bad_ones_is_a_single_call():
    reply = LLMReply("", (ToolCall("rm_rf", {}), ToolCall("launch_discord", {})))
    brain, _ = make_brain(FakeLLM(reply))
    decision = brain.decide("дискорд")
    assert isinstance(decision, SkillCall) and decision.skill.name == "launch_discord"


def test_one_confirmation_for_a_batch_with_a_dangerous_skill():
    calls: list[str] = []
    llm = FakeLLM(tools_reply(("launch_discord", {}), ("format_disk", {})))
    assistant, tts, os_layer, _ = make_assistant(llm=llm, extra_skills=[danger_skill(calls)])
    assistant.handle_command("открой дискорд и отформатируй диск")
    assert os_layer.launched == [] and calls == []
    assistant.handle_command("да")
    assert os_layer.launched == [["discord"]] and calls == ["boom"]


def test_phrasing_falls_back_when_llm_fails():
    llm = FakeLLM(tool_reply("read_clipboard"), offline())
    assistant, tts, os_layer, _ = make_assistant(llm=llm)
    os_layer.clipboard = "текст"
    assistant.handle_command("переведи то что я скопировал")
    assert tts.spoken[-1] == "В буфере обмена: текст"


def test_phrased_question_opens_the_reply_window():
    llm = FakeLLM(tool_reply("read_clipboard"), text_reply("Перевести его, сэр?"))
    assistant, _, os_layer, _ = make_assistant(llm=llm)
    os_layer.clipboard = "hello"
    assistant.handle_command("что это за текст я скопировал")
    assert assistant.reply_window > 0


def test_history_gets_all_actions():
    both = tools_reply(("launch_discord", {}), ("launch_notepad", {}))
    llm = FakeLLM(both, tool_reply("tell_time"))
    assistant, _, _, _ = make_assistant(llm=llm)
    assistant.handle_command("открой дискорд и блокнот")
    assistant.handle_command("а сколько сейчас на часах")
    messages, _ = llm.requests[1]
    names = [c["function"]["name"] for c in messages[2]["tool_calls"]]
    assert names == ["launch_discord", "launch_notepad"]
    assert make_config().llm.max_tool_calls == 3
