"""Test doubles: no microphone, no speakers, no real apps."""

from __future__ import annotations

from collections.abc import Sequence

from myata.brain.router import Router
from myata.config import Config, config_from_dict
from myata.core.assistant import Assistant
from myata.oslayer import LaunchError
from myata.skills.registry import build_registry
from myata.wake.detector import WakeWordDetector

TEST_CONFIG = {
    "sites": [
        {
            "name": "youtube",
            "url": "https://youtube.com",
            "phrases": ["открой ютуб", "включи ютуб"],
            "reply": "Открываю ютуб",
        }
    ],
    "apps": [
        {
            "name": "notepad",
            "phrases": ["открой блокнот"],
            "reply": "Открываю блокнот",
            "commands": {"windows": ["notepad"], "linux": ["xed"]},
        },
        {
            "name": "league_of_legends",
            "phrases": ["запусти лигу легенд"],
            "reply": "Запускаю Лигу Легенд, сэр",
            "commands": {"windows": ["C:/Riot Games/RiotClientServices.exe"]},
        },
    ],
}


class FakeTTS:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str) -> None:
        self.spoken.append(text)


class FakeOS:
    def __init__(self, name: str = "windows", fail_launch: bool = False) -> None:
        self.name = name
        self.fail_launch = fail_launch
        self.launched: list[list[str]] = []
        self.opened: list[str] = []

    def launch(self, argv: Sequence[str]) -> None:
        if self.fail_launch:
            raise LaunchError("not found")
        self.launched.append(list(argv))

    def open_url(self, url: str) -> bool:
        self.opened.append(url)
        return True


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make_config() -> Config:
    return config_from_dict(TEST_CONFIG)


def make_assistant(os_layer: FakeOS | None = None):
    config = make_config()
    os_layer = os_layer or FakeOS()
    tts, clock = FakeTTS(), FakeClock()
    registry = build_registry(os_layer.name, config)
    assistant = Assistant(
        config=config,
        router=Router(registry, config.router.threshold),
        wake=WakeWordDetector(config.wake.words, config.wake.threshold),
        tts=tts,
        os_layer=os_layer,
        clock=clock,
        output=lambda _text: None,
    )
    return assistant, tts, os_layer, clock
