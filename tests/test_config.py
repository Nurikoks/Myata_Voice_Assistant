from pathlib import Path

import pytest

from myata.config import ConfigError, config_from_dict, load_config

ROOT = Path(__file__).resolve().parents[1]


def test_repo_config_is_valid():
    config = load_config(ROOT / "config.yaml")
    assert config.assistant.name == "Мята"
    assert any(app.name == "league_of_legends" for app in config.apps)
    assert "{name}" in config.llm.system_prompt


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
