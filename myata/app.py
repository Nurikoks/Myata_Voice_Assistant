"""Wires all parts together and runs the voice or text loop."""

from __future__ import annotations

import logging
import time

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

    if speak:
        print("Загружаю голос...")
        started = time.perf_counter()
        tts = create_tts(config.tts, config.audio.output_device)
        print(f"Голос готов за {time.perf_counter() - started:.1f} с")
    else:
        tts = NullTTS()

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
        tts=tts,
        os_layer=os_layer,
    )
    return assistant, registry


def run_voice(config: Config, *, use_llm: bool = True) -> None:
    # Must run before faster_whisper or torch are imported (CUDA DLLs, OpenMP).
    from myata.oslayer.cuda import prepare_cuda_libraries

    prepare_cuda_libraries()

    from myata.audio.microphone import Microphone
    from myata.stt.vad import PhraseRecorder, SileroVad
    from myata.stt.whisper_stt import WhisperRecognizer
    from myata.voice.loop import VoiceLoop
    from myata.wake.spotter import VoskWakeSpotter

    rate = config.audio.sample_rate
    spotter = VoskWakeSpotter(config.wake.vosk_model_path, rate, config.wake.words)
    vad = SileroVad(config.vad.model_path, rate)

    print("Загружаю распознавание речи...")
    stt = WhisperRecognizer(config.stt, rate)
    seconds = stt.load()
    print(f"Whisper готов за {seconds:.1f} с ({stt.device})")

    assistant, _ = build_assistant(config, use_llm=use_llm)
    recorder = PhraseRecorder(
        vad,
        sample_rate=rate,
        threshold=config.vad.threshold,
        silence_ms=config.vad.silence_ms,
        min_speech_ms=config.vad.min_speech_ms,
        max_phrase_sec=config.vad.max_phrase_sec,
    )
    mic = Microphone(rate, config.audio.block_size, config.audio.device)

    assistant.greet()
    with mic:
        loop = VoiceLoop(
            assistant=assistant,
            mic=mic,
            spotter=spotter,
            recorder=recorder,
            stt=stt,
            sample_rate=rate,
            preroll_sec=config.wake.preroll_sec,
            wake_timeout_sec=config.vad.start_timeout_sec,
            unmute_delay_sec=config.audio.unmute_delay_sec,
        )
        print(f"Скажите «{config.wake.words[0]}» и команду. Ctrl+C для выхода.")
        loop.run()


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


def list_audio_devices() -> None:
    import sounddevice as sd

    print(sd.query_devices())
    print("\nНомер или имя устройства можно указать в audio.device / audio.output_device.")
