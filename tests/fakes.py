"""Test doubles: no microphone, no speakers, no real apps, no real LLM."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from myata.brain.brain import Brain
from myata.brain.history import History
from myata.brain.llm import LLMError, LLMReply, ToolCall
from myata.brain.router import Router
from myata.config import Config, config_from_dict
from myata.core.assistant import Assistant
from myata.oslayer import LaunchError
from myata.skills.base import Skill, SkillResult
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
            "name": "discord",
            "phrases": ["открой дискорд"],
            "reply": "Открываю дискорд",
            "commands": {"windows": ["discord"], "linux": ["discord"]},
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


class FakeLLM:
    """Returns prepared replies one by one and records what it was asked."""

    def __init__(self, *replies: LLMReply | Exception) -> None:
        self.replies = list(replies)
        self.requests: list[tuple[list, list]] = []

    def chat(self, messages, tools) -> LLMReply:
        self.requests.append((list(messages), list(tools)))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def warm_up(self) -> float | None:
        return 0.0


def text_reply(text: str) -> LLMReply:
    return LLMReply(text)


def tool_reply(name: str, **arguments) -> LLMReply:
    return LLMReply("", (ToolCall(name, arguments),))


def offline() -> LLMError:
    return LLMError("connection refused")


def make_config() -> Config:
    return config_from_dict(TEST_CONFIG)


def danger_skill(calls: list[str]) -> Skill:
    def handler(ctx):
        calls.append("boom")
        return SkillResult("Выключаю компьютер")

    return Skill(
        name="shutdown_pc",
        description="Turn off the computer",
        phrases=("выключи компьютер",),
        handler=handler,
        dangerous=True,
    )


def make_brain(llm=None, extra_skills=(), clock=None):
    config = make_config()
    registry = build_registry("windows", config)
    for item in extra_skills:
        registry.register(item)
    history = History(config.llm.history_turns, config.llm.history_ttl_sec, clock or FakeClock())
    brain = Brain(
        config=config,
        router=Router(registry, config.router.threshold, config.router.stop_words),
        skills=list(registry),
        llm=llm,
        history=history,
        now=lambda: datetime(2026, 10, 1, 14, 5),
    )
    return brain, config


def make_assistant(os_layer: FakeOS | None = None, llm=None, extra_skills=()):
    os_layer = os_layer or FakeOS()
    tts, clock = FakeTTS(), FakeClock()
    brain, config = make_brain(llm, extra_skills, clock)
    assistant = Assistant(
        config=config,
        brain=brain,
        wake=WakeWordDetector(config.wake.words, config.wake.threshold),
        tts=tts,
        os_layer=os_layer,
        clock=clock,
        output=lambda _text: None,
    )
    return assistant, tts, os_layer, clock
