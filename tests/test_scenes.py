import pytest

from myata.config import ConfigError
from myata.skills.base import SkillContext
from myata.skills.registry import build_registry
from tests.fakes import FakeOS, make_assistant, make_config

SCENE = {
    "name": "gaming",
    "phrases": ["игровой режим"],
    "reply": "Игровой режим включён, сэр",
    "steps": [
        {"launch": "discord"},
        {"launch": "league_of_legends"},  # Windows only
        {"open": "youtube"},
        {"volume": 40},
    ],
}


def test_scene_runs_every_step():
    assistant, tts, os_layer, _ = make_assistant(config=make_config(scenes=[SCENE]))
    assistant.handle_command("игровой режим")
    assert os_layer.launched == [["discord"], ["C:/Riot Games/RiotClientServices.exe"]]
    assert os_layer.opened == ["https://youtube.com"] and os_layer.volume == 40
    assert tts.spoken[-1] == "Игровой режим включён, сэр"


def test_steps_for_another_os_and_missing_capabilities_are_dropped():
    registry = build_registry("linux", make_config(scenes=[SCENE]), capabilities=set())
    scene = registry.get("scene_gaming")
    assert scene is not None
    os_layer = FakeOS("linux")
    scene.handler(SkillContext(os=os_layer, config=make_config(), text=""))
    assert os_layer.launched == [["discord"]] and os_layer.volume == 50  # no LoL, no volume


def test_partial_failure_is_reported():
    os_layer = FakeOS(fail_launch=True)
    assistant, tts, _, _ = make_assistant(os_layer, config=make_config(scenes=[SCENE]))
    assistant.handle_command("игровой режим")
    assert tts.spoken[-1] == "Игровой режим включён, сэр. Но не всё получилось, сэр."


def test_bad_scenes_are_rejected():
    bad_steps = [
        [{"launch": "photoshop"}],
        [{"open": "twitch"}],
        [{"volume": 150}],
        [{"media": "rewind"}],
        [{"launch": "discord", "volume": 10}],
        [],
    ]
    for steps in bad_steps:
        with pytest.raises(ConfigError):
            make_config(scenes=[{**SCENE, "steps": steps}])
