from myata.brain.speech import clean_for_speech


def test_markdown_lists_and_emoji_are_removed():
    text = "**Конечно, сэр!** 😊\n- первый пункт\n- второй пункт\n`код`"
    assert clean_for_speech(text, 300) == "Конечно, сэр! первый пункт. второй пункт. код."


def test_think_block_and_links_are_removed():
    text = "<think>долгие размышления</think>Готово, сэр. Подробнее: https://example.com"
    assert clean_for_speech(text, 300) == "Готово, сэр. Подробнее:"


def test_long_text_is_cut_at_sentence_end():
    text = "Первое предложение. " * 30
    result = clean_for_speech(text, 100)
    assert len(result) <= 100
    assert result.endswith(".")


def test_empty():
    assert clean_for_speech("", 300) == ""
    assert clean_for_speech("<think>только мысли</think>", 300) == ""
