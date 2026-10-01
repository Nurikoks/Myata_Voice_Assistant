import pytest

from myata.config import DEFAULT_HALLUCINATIONS
from myata.stt.whisper_stt import clean_transcript, model_source


def test_normal_text_is_kept():
    assert clean_transcript("Мята, открой ютуб.", DEFAULT_HALLUCINATIONS) == "Мята, открой ютуб."


def test_hallucinations_are_dropped():
    assert clean_transcript("Продолжение следует...", DEFAULT_HALLUCINATIONS) == ""
    assert clean_transcript("Субтитры сделал DimaTorzok", DEFAULT_HALLUCINATIONS) == ""


def test_punctuation_only_is_empty():
    assert clean_transcript(" ... ", DEFAULT_HALLUCINATIONS) == ""


def test_model_names_pass_through():
    assert model_source("large-v3-turbo") == "large-v3-turbo"
    assert model_source("coriollon/some-model") == "coriollon/some-model"


def test_missing_local_model_folder_is_reported():
    with pytest.raises(FileNotFoundError):
        model_source("models/no-such-whisper")
