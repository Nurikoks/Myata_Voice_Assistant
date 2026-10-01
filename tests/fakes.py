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
from myata.oslayer import ALL_CAPABILITIES, LaunchError, OSActionError
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
    """Records every OS action instead of doing it."""

    def __init__(self, name: str = "windows", fail_launch: bool = False) -> None:
        self.name = name
        self.fail_launch = fail_launch
        self.fail_actions = False
        self.launched: list[list[str]] = []
        self.opened: list[str] = []
        self.volume = 50
        self.muted = False
        self.media: list[str] = []
        self.power_actions: list[str] = []
        self.clipboard = ""
        self.screenshots: list[str] = []

    def capabilities(self) -> frozenset[str]:
        return ALL_CAPABILITIES

    def launch(self, argv: Sequence[str]) -> None:
        if self.fail_launch:
            raise LaunchError("not found")
        self.launched.append(list(argv))

    def open_url(self, url: str) -> bool:
        self.opened.append(url)
        return True

    def _check(self) -> None:
        if self.fail_actions:
            raise OSActionError("broken")

    def get_volume(self) -> int:
        self._check()
        return self.volume

    def set_volume(self, percent: int) -> None:
        self._check()
        self.volume, self.muted = percent, False

    def set_mute(self, muted: bool) -> None:
        self._check()
        self.muted = muted

    def media_key(self, key: str) -> None:
        self._check()
        self.media.append(key)

    def power(self, action: str) -> None:
        self._check()
        self.power_actions.append(action)

    def read_clipboard(self) -> str:
        self._check()
        return self.clipboard

    def screenshot(self, path) -> None:
        self._check()
        self.screenshots.append(str(path))


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


def tools_reply(*calls: tuple[str, dict]) -> LLMReply:
    """Several tool calls in one answer: tools_reply(("a", {}), ("b", {"x": 1}))."""
    return LLMReply("", tuple(ToolCall(name, args) for name, args in calls))


def offline() -> LLMError:
    return LLMError("connection refused")


def make_config(**sections) -> Config:
    """TEST_CONFIG with some sections replaced, e.g. make_config(skills={...})."""
    return config_from_dict({**TEST_CONFIG, **sections})


def danger_skill(calls: list[str]) -> Skill:
    def handler(ctx):
        calls.append("boom")
        return SkillResult("Форматирую диск")

    return Skill(
        name="format_disk",
        description="Format the disk",
        phrases=("форматируй диск",),
        handler=handler,
        dangerous=True,
    )


def make_brain(llm=None, extra_skills=(), clock=None, config=None):
    config = config or make_config()
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


def make_assistant(os_layer: FakeOS | None = None, llm=None, extra_skills=(), config=None):
    os_layer = os_layer or FakeOS()
    tts, clock = FakeTTS(), FakeClock()
    brain, config = make_brain(llm, extra_skills, clock, config)
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


# ---------- voice loop doubles ----------

SPEECH = 8000  # int16 amplitude the fake VAD treats as speech
FRAME = 512


def pcm(level: int, ms: int, rate: int = 16000) -> bytes:
    """Raw 16-bit audio of constant level: loud enough = speech, 0 = silence."""
    import numpy as np

    return np.full(rate * ms // 1000, level, dtype=np.int16).tobytes()


class FakeVad:
    """Speech when the frame is loud, silence otherwise."""

    def __init__(self) -> None:
        self.resets = 0

    def probability(self, frame) -> float:
        return 1.0 if abs(float(frame.mean())) > 0.1 else 0.0

    def reset(self) -> None:
        self.resets += 1


class FakeMic:
    def __init__(self) -> None:
        self.muted = False
        self.mutes = 0

    def read(self, timeout: float = 0.5):
        return None

    def mute(self) -> None:
        self.muted = True
        self.mutes += 1

    def unmute(self) -> None:
        self.muted = False


class FakeSpotter:
    """Fires on any loud block while armed (arm() = the user said the wake word)."""

    def __init__(self) -> None:
        self.armed = False
        self.resets = 0

    def arm(self) -> None:
        self.armed = True

    def accept(self, chunk: bytes) -> bool:
        import numpy as np

        loud = np.abs(np.frombuffer(chunk, dtype=np.int16)).mean() > SPEECH / 2
        if self.armed and loud:
            self.armed = False
            return True
        return False

    def reset(self) -> None:
        self.resets += 1


class FakeSTT:
    def __init__(self, mic: FakeMic, *texts: str) -> None:
        self.texts = list(texts)
        self.mic = mic
        self.muted_while_busy: list[bool] = []
        self.lengths: list[int] = []

    def transcribe(self, audio) -> str:
        self.muted_while_busy.append(self.mic.muted)
        self.lengths.append(len(audio))
        return self.texts.pop(0)
