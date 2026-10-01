from myata.wake.detector import WakeWordDetector

detector = WakeWordDetector(["мята", "миата", "ята", "Матя"], 0.75)
strict = WakeWordDetector(["мята"], 0.85)


def test_wake_words():
    assert detector.is_wake("мята")
    assert detector.is_wake("Мята")
    assert detector.is_wake("матя")  # config words are normalized too
    assert not detector.is_wake("мама")
    assert not detector.is_wake("открой")


def test_split():
    assert detector.split("мята открой ютуб") == (True, "открой ютуб")
    assert detector.split("Мята") == (True, "")
    assert detector.split("открой ютуб") == (False, "открой ютуб")


def test_words_before_the_name_are_dropped():
    assert strict.split("ну вот, Мята, открой ютуб.") == (True, "открой ютуб")


def test_strict_threshold_rejects_mat():
    assert not strict.is_wake("мать")
    assert strict.is_wake("Мята,")
