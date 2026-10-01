import pytest

from myata.tts.normalize import apply_replacements, prepare_for_speech

WORDS = {1: "один", 2: "два", 5: "пять", 14: "четырнадцать", 21: "двадцать один", 30: "тридцать"}


def spell(n: int) -> str:
    return WORDS[n]


def test_replacements_are_case_insensitive_and_longest_first():
    replacements = {"Code": "код", "VS Code": "вэ эс код"}
    assert apply_replacements("Открываю vs code", replacements) == "Открываю вэ эс код"


def test_replacements_only_match_whole_words():
    assert apply_replacements("Steamworks и Steam", {"Steam": "стим"}) == "Steamworks и стим"


def test_numbers_become_words():
    text = prepare_for_speech("Сейчас 14 часов 5 минут", {}, spell)
    assert text == "Сейчас четырнадцать часов пять минут"


def test_feminine_nouns():
    assert prepare_for_speech("1 минута", {}, spell) == "одна минута"
    assert prepare_for_speech("21 минута и 2 секунды", {}, spell) == (
        "двадцать одна минута и две секунды"
    )
    assert prepare_for_speech("1 час 2 часа", {}, spell) == "один час два часа"


def test_clock_time():
    assert prepare_for_speech("Встреча в 14:30", {}, spell) == "Встреча в четырнадцать тридцать"


def test_without_speller_digits_stay():
    assert prepare_for_speech("Сейчас 14 часов", {}, None) == "Сейчас 14 часов"


def test_real_num2words():
    pytest.importorskip("num2words")
    from myata.tts.normalize import default_speller

    speller = default_speller()
    assert prepare_for_speech("2 минуты", {}, speller) == "две минуты"
