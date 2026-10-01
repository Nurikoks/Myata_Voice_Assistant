"""Load config.yaml into typed, read-only dataclasses.

Unknown keys and wrong types fail loudly at startup, so a typo in the config
does not turn into a strange bug ten minutes later.
"""

from __future__ import annotations

import dataclasses
import types
import typing
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class ConfigError(Exception):
    """Raised when the config file is missing or invalid."""


DEFAULT_SYSTEM_PROMPT = """\
Ты {name}, голосовой ассистент в стиле Джарвиса из фильма «Железный человек».
Ты вежливая, спокойная и немного ироничная. О себе говоришь в женском роде.
Обращайся к пользователю «сэр».
Отвечай по-русски, коротко: одно или два предложения.
Твой ответ будет озвучен голосом.
Поэтому не используй markdown, списки, эмодзи, ссылки и код.
Если пользователь просит что-то сделать и для этого есть инструмент, вызови инструмент.
Никогда не говори, что выполнила действие, если не вызвала инструмент.
Если подходящего инструмента нет, честно скажи, что пока так не умеешь.
Сегодня {date}, сейчас {time}."""


@dataclass(frozen=True)
class AssistantPhrases:
    greeting: str = "Мята на связи"
    listening: str = "Слушаю"
    not_understood: str = "Не поняла команду"
    goodbye: str = "До связи, сэр"
    failed: str = "Не получилось, сэр"
    confirm: str = "Вы уверены, сэр? Скажите да или нет."
    cancelled: str = "Отменяю"
    brain_offline: str = "Мой мозг сейчас не отвечает, сэр."


@dataclass(frozen=True)
class AssistantConfig:
    name: str = "Мята"
    listen_window_sec: float = 6.0
    confirm_timeout_sec: float = 15.0
    yes_words: tuple[str, ...] = ("да", "подтверждаю", "конечно", "давай", "ага", "точно")
    no_words: tuple[str, ...] = ("нет", "отмена", "отмени", "не")
    phrases: AssistantPhrases = field(default_factory=AssistantPhrases)


@dataclass(frozen=True)
class WakeConfig:
    # Vosk listens only for these words (a grammar). Whisper then has to hear one of them
    # too, compared with the fuzzy threshold below, before the phrase reaches the assistant.
    words: tuple[str, ...] = ("мята",)
    threshold: float = 0.85
    vosk_model_path: str = "models/vosk-model-small-ru-0.22"
    preroll_sec: float = 1.0


@dataclass(frozen=True)
class RouterConfig:
    threshold: float = 0.75
    stop_words: tuple[str, ...] = ("пожалуйста", "мне", "ка", "там", "сейчас", "а", "ну", "и")


@dataclass(frozen=True)
class LlmConfig:
    enabled: bool = True
    host: str = "http://localhost:11434"
    model: str = "qwen3.5:4b"
    think: bool | None = False
    temperature: float = 0.6
    num_ctx: int = 4096
    max_tokens: int = 256
    keep_alive: str = "30m"
    timeout_sec: float = 60.0
    max_reply_chars: int = 300
    history_turns: int = 6
    history_ttl_sec: float = 300.0
    system_prompt: str = DEFAULT_SYSTEM_PROMPT


@dataclass(frozen=True)
class AudioConfig:
    sample_rate: int = 16000
    block_size: int = 1600
    device: int | str | None = None
    output_device: int | str | None = None
    unmute_delay_sec: float = 0.2


@dataclass(frozen=True)
class VadConfig:
    model_path: str = "models/silero/silero_vad.jit"
    threshold: float = 0.5
    silence_ms: int = 700
    min_speech_ms: int = 200
    start_timeout_sec: float = 5.0
    max_phrase_sec: float = 15.0


DEFAULT_HALLUCINATIONS = (
    "продолжение следует",
    "субтитры сделал",
    "субтитры создавал",
    "редактор субтитров",
    "спасибо за просмотр",
    "подписывайтесь на канал",
    "dimatorzok",
)


@dataclass(frozen=True)
class SttConfig:
    model: str = "models/whisper-large-v3-turbo"
    download_root: str = "models/whisper"
    device: str = "cuda"
    compute_type: str = "int8_float16"
    cpu_compute_type: str = "int8"
    cpu_fallback: bool = True
    language: str = "ru"
    beam_size: int = 5
    initial_prompt: str | None = None
    hallucinations: tuple[str, ...] = DEFAULT_HALLUCINATIONS


@dataclass(frozen=True)
class SileroTtsConfig:
    model_path: str = "models/silero/v5_ru.pt"
    speaker: str = "xenia"
    sample_rate: int = 48000
    threads: int = 4
    put_accent: bool = True
    put_yo: bool = True
    put_stress_homo: bool = True
    put_yo_homo: bool = True


@dataclass(frozen=True)
class Pyttsx3Config:
    rate: int = 180
    voice_hints: tuple[str, ...] = ("ru", "irina", "russian")


@dataclass(frozen=True)
class TtsConfig:
    engine: str = "silero"
    replacements: dict[str, str] = field(default_factory=dict)
    silero: SileroTtsConfig = field(default_factory=SileroTtsConfig)
    pyttsx3: Pyttsx3Config = field(default_factory=Pyttsx3Config)


@dataclass(frozen=True)
class LoggingConfig:
    level: str = "INFO"
    console_level: str = "WARNING"
    file: str | None = "logs/myata.log"


@dataclass(frozen=True)
class SiteConfig:
    name: str
    url: str
    phrases: tuple[str, ...]
    reply: str
    description: str = ""


@dataclass(frozen=True)
class AppConfig:
    name: str
    phrases: tuple[str, ...]
    reply: str
    commands: dict[str, tuple[str, ...]]  # OS name -> argv
    description: str = ""


@dataclass(frozen=True)
class Config:
    assistant: AssistantConfig = field(default_factory=AssistantConfig)
    wake: WakeConfig = field(default_factory=WakeConfig)
    router: RouterConfig = field(default_factory=RouterConfig)
    llm: LlmConfig = field(default_factory=LlmConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    vad: VadConfig = field(default_factory=VadConfig)
    stt: SttConfig = field(default_factory=SttConfig)
    tts: TtsConfig = field(default_factory=TtsConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    sites: tuple[SiteConfig, ...] = ()
    apps: tuple[AppConfig, ...] = ()


KNOWN_OS = {"windows", "linux"}
TTS_ENGINES = {"silero", "pyttsx3", "none"}
STT_DEVICES = {"cuda", "cpu"}
SAMPLE_RATE = 16000  # Silero VAD and Whisper both want 16 kHz mono


def load_config(path: str | Path) -> Config:
    """Read a YAML file and turn it into a Config."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path.resolve()}")
    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"{path}: invalid YAML: {e}") from e
    return config_from_dict(data or {})


def config_from_dict(data: dict) -> Config:
    config = _build(Config, data, "")
    _validate(config)
    return config


def _validate(config: Config) -> None:
    for where, value in (
        ("wake.threshold", config.wake.threshold),
        ("router.threshold", config.router.threshold),
        ("vad.threshold", config.vad.threshold),
    ):
        if not 0.0 <= value <= 1.0:
            raise ConfigError(f"{where} must be between 0 and 1, got {value}")
    if config.llm.history_turns < 0 or config.llm.max_reply_chars < 20:
        raise ConfigError("llm.history_turns must be >= 0 and llm.max_reply_chars >= 20")
    if config.tts.engine not in TTS_ENGINES:
        raise ConfigError(f"tts.engine must be one of {sorted(TTS_ENGINES)}")
    if config.stt.device not in STT_DEVICES:
        raise ConfigError(f"stt.device must be one of {sorted(STT_DEVICES)}")
    if config.audio.sample_rate != SAMPLE_RATE:
        raise ConfigError(f"audio.sample_rate must be {SAMPLE_RATE}")
    if not config.wake.words:
        raise ConfigError("wake.words needs at least one word")
    if config.audio.block_size <= 0 or config.vad.silence_ms <= 0:
        raise ConfigError("audio.block_size and vad.silence_ms must be positive")
    for app in config.apps:
        unknown = set(app.commands) - KNOWN_OS
        if unknown:
            raise ConfigError(f"apps.{app.name}: unknown OS names: {sorted(unknown)}")
        for os_name, argv in app.commands.items():
            if not argv:
                raise ConfigError(f"apps.{app.name}.commands.{os_name} is empty")


def _build(cls: type, data: object, where: str) -> object:
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError(f"{where or 'config'}: expected a mapping")
    hints = typing.get_type_hints(cls)
    fields = dataclasses.fields(cls)
    unknown = set(data) - {f.name for f in fields}
    if unknown:
        raise ConfigError(f"{where or 'config'}: unknown keys: {', '.join(sorted(unknown))}")
    kwargs = {}
    for f in fields:
        key_path = f"{where}.{f.name}" if where else f.name
        if f.name in data:
            kwargs[f.name] = _convert(hints[f.name], data[f.name], key_path)
        elif f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
            raise ConfigError(f"{key_path}: required key is missing")
    return cls(**kwargs)


def _convert(tp: object, value: object, where: str) -> object:
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)

    if dataclasses.is_dataclass(tp):
        return _build(tp, value, where)
    if origin is tuple:
        if not isinstance(value, list):
            raise ConfigError(f"{where}: expected a list")
        return tuple(_convert(args[0], v, f"{where}[{i}]") for i, v in enumerate(value))
    if origin is dict:
        if not isinstance(value, dict):
            raise ConfigError(f"{where}: expected a mapping")
        return {str(k): _convert(args[1], v, f"{where}.{k}") for k, v in value.items()}
    if origin in (typing.Union, types.UnionType):
        if value is None and type(None) in args:
            return None
        for option in args:
            if option is not type(None) and _is_instance(value, option):
                return value
        raise ConfigError(f"{where}: unexpected value {value!r}")
    if tp is float and _is_instance(value, int):
        return float(value)
    if tp is str and isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(tp, type) and _is_instance(value, tp):
        return value
    name = getattr(tp, "__name__", str(tp))
    raise ConfigError(f"{where}: expected {name}, got {type(value).__name__}")


def _is_instance(value: object, tp: type) -> bool:
    # bool is a subclass of int in Python, but "true" is never a valid number here.
    if isinstance(value, bool) and tp is not bool:
        return False
    return isinstance(value, tp)
