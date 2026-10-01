import tempfile
from pathlib import Path

from tests.fakes import FakeLLM, FakeOS, make_assistant, make_config, text_reply, tool_reply


def notes_config(folder: str):
    return make_config(skills={"notes_file": str(Path(folder) / "notes.md")})


def test_add_and_read_notes_without_llm():
    with tempfile.TemporaryDirectory() as tmp:
        llm = FakeLLM(tool_reply("add_note", text="купить молоко"))
        assistant, tts, _, _ = make_assistant(llm=llm, config=notes_config(tmp))
        assistant.handle_command("запиши купить молоко")
        assert tts.spoken[-1] == "Записала, сэр"
        assert "купить молоко" in (Path(tmp) / "notes.md").read_text(encoding="utf-8")

        offline, tts2, _, _ = make_assistant(config=notes_config(tmp))
        offline.handle_command("прочитай заметки")
        assert tts2.spoken[-1] == "У вас 1 заметка. Последняя: купить молоко"


def test_notes_go_to_the_llm_for_the_answer():
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "notes.md").write_text("- 2026-10-01 10:00 | купить молоко\n", "utf-8")
        llm = FakeLLM(text_reply("В заметках одно дело: купить молоко, сэр."))
        assistant, tts, _, _ = make_assistant(llm=llm, config=notes_config(tmp))
        assistant.handle_command("что в заметках")       # fast path, then the LLM phrases it
        assert tts.spoken[-1] == "В заметках одно дело: купить молоко, сэр."
        messages, tools = llm.requests[0]
        assert tools == []                                # no tools while phrasing
        assert messages[-1]["role"] == "tool" and "купить молоко" in messages[-1]["content"]


def test_no_notes():
    with tempfile.TemporaryDirectory() as tmp:
        llm = FakeLLM()
        assistant, tts, _, _ = make_assistant(llm=llm, config=notes_config(tmp))
        assistant.handle_command("мои заметки")
        assert tts.spoken[-1] == "Заметок пока нет, сэр" and llm.requests == []


def test_clear_notes_asks_first():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "notes.md"
        path.write_text("- x | y\n", "utf-8")
        assistant, _, _, _ = make_assistant(config=notes_config(tmp))
        assistant.handle_command("очисти заметки")
        assert path.exists()
        assistant.handle_command("да")
        assert not path.exists()


def test_clipboard_is_explained_by_the_llm():
    os_layer = FakeOS()
    os_layer.clipboard = "Hello world"
    llm = FakeLLM(tool_reply("read_clipboard"), text_reply("Там написано «привет, мир», сэр."))
    assistant, tts, _, _ = make_assistant(os_layer, llm=llm)
    assistant.handle_command("переведи что я скопировал на русский")
    assert tts.spoken[-1] == "Там написано «привет, мир», сэр."
    messages, _ = llm.requests[1]
    assert messages[-3]["content"] == "переведи что я скопировал на русский"
    assert "Hello world" in messages[-1]["content"]


def test_clipboard_without_llm_reads_the_text():
    os_layer = FakeOS()
    os_layer.clipboard = "  код 1234  "
    assistant, tts, _, _ = make_assistant(os_layer)
    assistant.handle_command("что в буфере обмена")
    assert tts.spoken[-1] == "В буфере обмена: код 1234"


def test_empty_clipboard():
    assistant, tts, _, _ = make_assistant()
    assistant.handle_command("прочитай буфер обмена")
    assert tts.spoken[-1] == "В буфере обмена нет текста, сэр"


def test_screenshot_goes_to_the_configured_folder():
    with tempfile.TemporaryDirectory() as tmp:
        os_layer = FakeOS()
        assistant, tts, _, _ = make_assistant(
            os_layer, config=make_config(skills={"screenshots_dir": tmp})
        )
        assistant.handle_command("сделай скриншот")
        assert tts.spoken[-1] == "Скриншот сохранён, сэр"
        assert os_layer.screenshots[0].startswith(tmp) and os_layer.screenshots[0].endswith(".png")
