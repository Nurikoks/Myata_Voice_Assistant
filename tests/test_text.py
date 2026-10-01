from myata.brain.text import content_words, normalize, plural_ru, words_match
from myata.skills.builtin.clock import format_time


def test_normalize():
    assert normalize("  Мята, ОТКРОЙ Ютуб!  ") == "мята открой ютуб"
    assert normalize("ещё") == "еще"


def test_content_words():
    assert content_words("Открой, пожалуйста, ютуб", frozenset({"пожалуйста"})) == [
        "открой",
        "ютуб",
    ]


def test_words_match():
    assert words_match("ютуб", "ютубе")
    assert words_match("открой", "открыть")
    assert words_match("времени", "время")
    assert words_match("лигу", "лига")
    assert words_match("час", "часа")
    assert not words_match("стол", "стоп")
    assert not words_match("стим", "стиль")
    assert not words_match("закинь", "запусти")


def test_plural_ru():
    forms = ("час", "часа", "часов")
    assert plural_ru(1, forms) == "час"
    assert plural_ru(3, forms) == "часа"
    assert plural_ru(5, forms) == "часов"
    assert plural_ru(11, forms) == "часов"
    assert plural_ru(21, forms) == "час"
    assert plural_ru(22, forms) == "часа"


def test_format_time():
    assert format_time(1, 21) == "Сейчас 1 час 21 минута"
    assert format_time(22, 3) == "Сейчас 22 часа 3 минуты"
    assert format_time(11, 12) == "Сейчас 11 часов 12 минут"
    assert format_time(14, 0) == "Сейчас 14 часов ровно"
