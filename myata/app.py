"""Wires all parts together and runs the voice or text loop."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor

from myata.brain.brain import Brain
from myata.brain.history import History
from myata.brain.llm import ChatModel, OllamaChat
from myata.brain.morph import Morph
from myata.brain.router import Router
from myata.config import Config
from myata.core.assistant import Assistant, Outcome
from myata.oslayer import get_os_layer
from myata.skills.registry import SkillRegistry, build_registry
from myata.tts import NullTTS, TextToSpeech, create_tts
from myata.wake.detector import WakeWordDetector

log = logging.getLogger(__name__)


def load_llm(config: Config) -> ChatModel | None:
    """Connect to Ollama and load the model into memory (it runs in its own process)."""
    if not config.llm.enabled:
        log.info("LLM is off in config.yaml, only fast commands work")
        return None
    llm = OllamaChat(config.llm)
    seconds = llm.warm_up()
    if seconds is None:
        print(f"Модель {config.llm.model} недоступна, работают только быстрые команды.")
        return llm
    share = llm.gpu_share()
    where = "" if share is None else f", {share:.0%} на GPU"
    print(f"Модель {config.llm.model} загружена за {seconds:.1f} с{where}")
    if share is not None and share < 0.99:
        print(
            "Внимание: часть модели работает на CPU, ответы будут медленными. "
            "Уменьшите llm.num_ctx или освободите видеопамять (игры, браузер)."
        )
        log.warning("LLM is only %.0f%% on the GPU", share * 100)
    return llm


def load_tts(config: Config) -> TextToSpeech:
    started = time.perf_counter()
    tts = create_tts(config.tts, config.audio.output_device)
    print(f"Голос готов за {time.perf_counter() - started:.1f} с")
    return tts


def build_assistant(
    config: Config,
    *,
    speak: bool = True,
    use_llm: bool = True,
    llm: ChatModel | None = None,
    tts: TextToSpeech | None = None,
) -> tuple[Assistant, SkillRegistry]:
    """Build the assistant. llm and tts can be passed in when they were loaded already."""
    os_layer = get_os_layer()
    capabilities = os_layer.capabilities()
    log.info("OS %s can do: %s", os_layer.name, ", ".join(sorted(capabilities)) or "nothing extra")
    registry = build_registry(os_layer.name, config, capabilities=capabilities)

    if llm is None and use_llm:
        llm = load_llm(config)
    if not use_llm:
        llm = None
    if tts is None:
        tts = load_tts(config) if speak else NullTTS()

    brain = Brain(
        config=config,
        router=Router(registry, config.router.threshold, config.router.stop_words, Morph.load()),
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
    started = time.perf_counter()
    print("Загружаю модели...")
    stt = WhisperRecognizer(config.stt, rate)

    # The slow parts load at the same time: Ollama works in its own process, and
    # CTranslate2 and torch release the GIL while they read files and set up the GPU.
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="load") as pool:
        llm_future = pool.submit(load_llm, config) if use_llm else None
        stt_future = pool.submit(stt.load)
        tts_future = pool.submit(load_tts, config)
        spotter = VoskWakeSpotter(config.wake.vosk_model_path, rate, config.wake.words)
        vad = SileroVad(config.vad.model_path, rate)
        print(f"Whisper готов за {stt_future.result():.1f} с ({stt.device})")
        llm = llm_future.result() if llm_future else None
        tts = tts_future.result()
    print(f"Всё загружено за {time.perf_counter() - started:.1f} с")

    assistant, _ = build_assistant(config, use_llm=use_llm, llm=llm, tts=tts)
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
