from myata.core.assistant import Outcome
from myata.skills.registry import build_registry
from tests.fakes import FakeLLM, FakeOS, make_assistant, make_config, tool_reply

NOW = {"power_delay_sec": 0}


def test_louder_and_quieter():
    assistant, tts, os_layer, _ = make_assistant()
    assistant.handle_command("сделай громче")
    assert os_layer.volume == 60 and tts.spoken[-1] == "Громкость 60 процентов"
    assistant.handle_command("потише")
    assert os_layer.volume == 50


def test_volume_stays_in_range():
    os_layer = FakeOS()
    os_layer.volume = 95
    assistant, _, _, _ = make_assistant(os_layer)
    assistant.handle_command("громче")
    assert os_layer.volume == 100


def test_mute_and_unmute():
    assistant, tts, os_layer, _ = make_assistant()
    assistant.handle_command("выключи звук")
    assert os_layer.muted and tts.spoken[-1] == "Звук выключен"
    assistant.handle_command("включи звук")
    assert not os_layer.muted


def test_llm_sets_exact_volume_even_with_extra_arguments():
    llm = FakeLLM(tool_reply("set_volume", level=30, mute=False, direction="up"))
    assistant, tts, os_layer, _ = make_assistant(llm=llm)
    assistant.handle_command("сделай звук на тридцать")
    assert os_layer.volume == 30 and tts.spoken[-1] == "Громкость 30 процентов"


def test_media_keys():
    assistant, _, os_layer, _ = make_assistant()
    assistant.handle_command("поставь на паузу")
    assistant.handle_command("следующий трек")
    assert os_layer.media == ["play_pause", "next"]


def test_broken_sound_is_reported():
    os_layer = FakeOS()
    os_layer.fail_actions = True
    assistant, tts, _, _ = make_assistant(os_layer)
    assistant.handle_command("громче")
    assert tts.spoken[-1] == "Не получилось, сэр"


def test_shutdown_needs_confirmation():
    assistant, tts, os_layer, _ = make_assistant(config=make_config(skills=NOW))
    assistant.handle_command("выключи компьютер")
    assert os_layer.power_actions == [] and tts.spoken[-1].startswith("Выключить компьютер")
    assistant.handle_command("да")
    assert os_layer.power_actions == ["shutdown"]


def test_power_dry_run():
    config = make_config(skills={"power_dry_run": True, "power_delay_sec": 0})
    assistant, tts, os_layer, _ = make_assistant(config=config)
    assistant.handle_command("спящий режим")
    assert assistant.handle_command("да") is Outcome.HANDLED
    assert os_layer.power_actions == [] and "тренировка" in tts.spoken[-1]


def test_skills_without_capability_are_not_registered():
    names = {s.name for s in build_registry("linux", make_config(), capabilities={"power"})}
    assert "shutdown_computer" in names
    assert "volume_up" not in names and "read_clipboard" not in names
    assert "read_notes" in names  # needs nothing from the OS
