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


@dataclass(frozen=True)
class AssistantPhrases:
    greeting: str = "Мята на связи"
    listening: str = "Слушаю"
    not_understood: str = "Не понял команду"
    goodbye: str = "До связи, сэр"
    failed: str = "Не получилось, сэр"


@dataclass(frozen=True)
class AssistantConfig:
    name: str = "Мята"
    listen_window_sec: float = 6.0
    phrases: AssistantPhrases = field(default_factory=AssistantPhrases)


@dataclass(frozen=True)
class WakeConfig:
    words: tuple[str, ...] = ("мята", "миата", "ята", "матя")
    threshold: float = 0.75


@dataclass(frozen=True)
class RouterConfig:
    threshold: float = 0.6


@dataclass(frozen=True)
class AudioConfig:
    sample_rate: int = 16000
    block_size: int = 8000
    device: int | str | None = None


@dataclass(frozen=True)
class SttConfig:
    vosk_model_path: str = "models/vosk-model-small-ru-0.22"


@dataclass(frozen=True)
class TtsConfig:
    engine: str = "pyttsx3"
    rate: int = 180
    voice_hints: tuple[str, ...] = ("ru", "irina", "russian")


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
    audio: AudioConfig = field(default_factory=AudioConfig)
    stt: SttConfig = field(default_factory=SttConfig)
    tts: TtsConfig = field(default_factory=TtsConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    sites: tuple[SiteConfig, ...] = ()
    apps: tuple[AppConfig, ...] = ()


KNOWN_OS = {"windows", "linux"}
TTS_ENGINES = {"pyttsx3", "none"}


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
    ):
        if not 0.0 <= value <= 1.0:
            raise ConfigError(f"{where} must be between 0 and 1, got {value}")
    if config.tts.engine not in TTS_ENGINES:
        raise ConfigError(f"tts.engine must be one of {sorted(TTS_ENGINES)}")
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
