"""Wires all parts together and runs the voice or text loop."""

from __future__ import annotations

import logging

from myata.brain.brain import Brain
from myata.brain.history import History
from myata.brain.llm import ChatModel, OllamaChat
from myata.brain.router import Router
from myata.config import Config
from myata.core.assistant import Assistant, Outcome
from myata.oslayer import get_os_layer
from myata.skills.registry import SkillRegistry, build_registry
from myata.tts import NullTTS, create_tts
from myata.wake.detector import WakeWordDetector

log = logging.getLogger(__name__)


def build_assistant(
    config: Config, *, speak: bool = True, use_llm: bool = True
) -> tuple[Assistant, SkillRegistry]:
    os_layer = get_os_layer()
    registry = build_registry(os_layer.name, config)

    llm: ChatModel | None = None
    if use_llm and config.llm.enabled:
        llm = OllamaChat(config.llm)
        print(f"Загружаю модель {config.llm.model}...")
        seconds = llm.warm_up()
        if seconds is not None:
            print(f"Модель загружена за {seconds:.1f} с")
    else:
        log.info("LLM is off, only fast commands work")

    brain = Brain(
        config=config,
        router=Router(registry, config.router.threshold, config.router.stop_words),
        skills=list(registry),
        llm=llm,
        history=History(config.llm.history_turns, config.llm.history_ttl_sec),
    )
    assistant = Assistant(
        config=config,
        brain=brain,
        wake=WakeWordDetector(config.wake.words, config.wake.threshold),
        tts=create_tts(config.tts) if speak else NullTTS(),
        os_layer=os_layer,
    )
    return assistant, registry


def run_voice(config: Config, *, use_llm: bool = True) -> None:
    from myata.audio.microphone import Microphone
    from myata.stt.vosk_stt import VoskRecognizer

    recognizer = VoskRecognizer(config.stt.vosk_model_path, config.audio.sample_rate)
    assistant, _ = build_assistant(config, use_llm=use_llm)
    mic = Microphone(config.audio.sample_rate, config.audio.block_size, config.audio.device)

    assistant.greet()
    with mic:
        while True:
            chunk = mic.read()
            if chunk is None:
                continue
            text = recognizer.accept(chunk)
            if not text:
                continue
            outcome = assistant.on_utterance(text)
            if outcome is Outcome.STOP:
                return
            if outcome is not Outcome.IGNORED:
                mic.clear()  # skip what was recorded while Myata was thinking and talking
                recognizer.reset()


def run_text(config: Config, *, speak: bool = False, use_llm: bool = True) -> None:
    """Chat in the console: no microphone needed, no wake word needed."""
    assistant, _ = build_assistant(config, speak=speak, use_llm=use_llm)
    assistant.greet()
    while True:
        try:
            text = input("Вы: ").strip()
        except EOFError:
            return
        if text and assistant.handle_command(text) is Outcome.STOP:
            return
