from pathlib import Path

import pytest

from myata.config import ConfigError, config_from_dict, load_config

ROOT = Path(__file__).resolve().parents[1]


def test_repo_config_is_valid():
    config = load_config(ROOT / "config.yaml")
    assert config.assistant.name == "Мята"
    assert any(app.name == "league_of_legends" for app in config.apps)
    assert "{name}" in config.llm.system_prompt
    assert config.wake.words == ("мята",)
    assert config.tts.engine == "silero"
    assert config.tts.silero.model_path.endswith("v5_ru.pt")
    assert config.tts.replacements["VS Code"] == "вэ эс код"
    assert config.scenes[0].name == "gaming"
    assert config.skills.power_dry_run is False


def test_defaults_without_file_content():
    config = config_from_dict({})
    assert config.router.threshold == 0.75
    assert config.llm.model == "qwen3.5:4b"
    assert config.sites == ()


def test_unknown_key():
    with pytest.raises(ConfigError):
        config_from_dict({"router": {"treshold": 0.5}})


def test_wrong_type():
    with pytest.raises(ConfigError):
        config_from_dict({"audio": {"sample_rate": "fast"}})


def test_threshold_range():
    with pytest.raises(ConfigError):
        config_from_dict({"router": {"threshold": 6}})


def test_unknown_os_in_app():
    app = {"name": "x", "phrases": ["x"], "reply": "x", "commands": {"macos": ["x"]}}
    with pytest.raises(ConfigError):
        config_from_dict({"apps": [app]})


def test_sample_rate_must_be_16k():
    with pytest.raises(ConfigError):
        config_from_dict({"audio": {"sample_rate": 44100}})


def test_unknown_tts_engine_and_device():
    with pytest.raises(ConfigError):
        config_from_dict({"tts": {"engine": "festival"}})
    with pytest.raises(ConfigError):
        config_from_dict({"stt": {"device": "tpu"}})


def test_initial_prompt_can_be_null_or_text():
    assert config_from_dict({"stt": {"initial_prompt": None}}).stt.initial_prompt is None
    assert config_from_dict({"stt": {"initial_prompt": "Мята"}}).stt.initial_prompt == "Мята"
