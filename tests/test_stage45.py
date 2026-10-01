"""Fixes after the first voice test of stage 4."""

import tempfile
from pathlib import Path
from types import SimpleNamespace

from myata.brain.llm import OllamaChat
from myata.brain.morph import Morph
from myata.config import DEFAULT_HALLUCINATIONS, LlmConfig
from myata.core.assistant import Outcome
from myata.stt.whisper_stt import clean_transcript, complete_model_folder
from tests.fakes import (
    FakeLLM,
    danger_skill,
    make_assistant,
    make_brain,
    text_reply,
    tool_reply,
)


class FakeAnalyzer:
    """A tiny pymorphy3 stand-in with a hand-made dictionary."""

    LEMMAS = {
        "громкость": "громкость", "громче": "громкий", "открой": "открыть",
        "открыть": "открыть", "заметки": "заметка", "заметках": "заметка",
    }

    def parse(self, word):
        return [SimpleNamespace(normal_form=self.LEMMAS.get(word, word))]

    def word_is_known(self, word):
        return word in self.LEMMAS


def test_morph_compares_dictionary_forms():
    morph = Morph(FakeAnalyzer())
    assert morph.same("открой", "открыть")
    assert morph.same("заметки", "заметках")
    assert not morph.same("громкость", "громче")    # the prefix heuristic said yes
    assert morph.same("ютубе", "ютуб")              # unknown word: prefix heuristic


def test_number_goes_to_set_volume_not_to_louder():
    assistant, tts, os_layer, _ = make_assistant()
    assistant.handle_command("сделай громкость 30")
    assert os_layer.volume == 30 and tts.spoken[-1] == "Громкость 30 процентов"
    assistant.handle_command("звук на 70 процентов")
    assert os_layer.volume == 70


def test_number_out_of_range_goes_to_the_llm():
    llm = FakeLLM(text_reply("Больше ста процентов нельзя, сэр."))
    assistant, tts, os_layer, _ = make_assistant(llm=llm)
    assistant.handle_command("громкость 150")
    assert os_layer.volume == 50 and len(llm.requests) == 1


def test_number_never_triggers_a_skill_without_numbers():
    brain, config = make_brain(None)
    assert brain.decide("открой блокнот 2").text == config.assistant.phrases.not_understood


def test_more_again():
    assistant, _, os_layer, _ = make_assistant()
    assistant.handle_command("повысь громкость")
    assistant.handle_command("повысь ещё раз")
    assistant.handle_command("ещё раз")
    assert os_layer.volume == 80


def test_nothing_to_repeat():
    assistant, tts, _, _ = make_assistant()
    assistant.handle_command("повтори")
    assert tts.spoken[-1] == "Пока нечего повторять, сэр"


def test_dangerous_actions_are_not_repeated():
    calls: list[str] = []
    assistant, tts, _, _ = make_assistant(extra_skills=[danger_skill(calls)])
    assistant.handle_command("форматируй диск")
    assistant.handle_command("да")
    assistant.handle_command("ещё раз")
    assert calls == ["boom"] and tts.spoken[-1] == "Пока нечего повторять, сэр"


def test_ways_to_turn_myata_off():
    for phrase in ("отключайся", "выключайся", "выключи себя"):
        assistant, _, _, _ = make_assistant()
        assert assistant.handle_command(phrase) is Outcome.STOP


def test_llm_may_call_hidden_skills_from_history():
    llm = FakeLLM(tool_reply("volume_down"))
    assistant, _, os_layer, _ = make_assistant(llm=llm)
    assistant.handle_command("ещё чише")              # misheard, goes to the LLM
    assert os_layer.volume == 40
    _, tools = llm.requests[0]
    assert "volume_down" not in {t["function"]["name"] for t in tools}


def test_llm_still_cannot_turn_myata_off():
    llm = FakeLLM(tool_reply("shutdown_assistant"))
    assistant, _, _, _ = make_assistant(llm=llm)
    assert assistant.handle_command("пора спать") is Outcome.HANDLED


def test_echo_of_hotwords_is_dropped():
    hotwords = "Мята, ютуб, дискорд, стим, блокнот"
    assert clean_transcript("Ютуб, дискорд, стим.", DEFAULT_HALLUCINATIONS, [hotwords]) == ""
    assert clean_transcript("Мята.", DEFAULT_HALLUCINATIONS, [hotwords]) == "Мята."
    assert clean_transcript("Открой дискорд", DEFAULT_HALLUCINATIONS, [hotwords]) != ""


def test_model_folder_gets_its_side_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "ct2").mkdir()
        (root / "preprocessor_config.json").write_text('{"feature_size": 128}', "utf-8")
        (root / "tokenizer.json").write_text("{}", "utf-8")
        complete_model_folder(root / "ct2")
        assert (root / "ct2" / "preprocessor_config.json").read_text("utf-8").endswith("128}")
        assert (root / "ct2" / "tokenizer.json").exists()


class PsClient:
    def __init__(self, size, size_vram):
        model = SimpleNamespace(model="qwen3.5:4b", size=size, size_vram=size_vram)
        self.response = SimpleNamespace(models=[model])

    def ps(self):
        return self.response


def test_gpu_share():
    assert OllamaChat(LlmConfig(), PsClient(4000, 4000)).gpu_share() == 1.0
    assert OllamaChat(LlmConfig(), PsClient(4000, 3000)).gpu_share() == 0.75
    assert OllamaChat(LlmConfig(), PsClient(4000, None)).gpu_share() == 0.0
