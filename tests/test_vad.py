import numpy as np

from myata.stt.vad import FRAME_SIZE, PhraseRecorder, PhraseStatus
from tests.fakes import FakeVad


def recorder(**overrides):
    options = dict(
        sample_rate=16000, threshold=0.5, silence_ms=700, min_speech_ms=200, max_phrase_sec=15
    )
    options.update(overrides)
    rec = PhraseRecorder(FakeVad(), **options)
    rec.start(start_timeout_sec=2)
    return rec


def audio(level: float, ms: int) -> np.ndarray:
    return np.full(16 * ms, level, dtype=np.float32)


def test_phrase_ends_after_silence():
    rec = recorder()
    assert rec.feed(audio(0.5, 1000)) is PhraseStatus.RECORDING
    assert rec.feed(audio(0.0, 500)) is PhraseStatus.RECORDING
    assert rec.feed(audio(0.0, 300)) is PhraseStatus.DONE


def test_short_pause_does_not_end_the_phrase():
    rec = recorder()
    rec.feed(audio(0.5, 500))
    rec.feed(audio(0.0, 400))
    assert rec.feed(audio(0.5, 500)) is PhraseStatus.RECORDING


def test_timeout_when_nobody_speaks():
    rec = recorder()
    assert rec.feed(audio(0.0, 1900)) is PhraseStatus.RECORDING
    assert rec.feed(audio(0.0, 200)) is PhraseStatus.TIMEOUT


def test_click_is_not_speech():
    rec = recorder()
    rec.feed(audio(0.5, 64))                    # two frames, shorter than min_speech_ms
    assert rec.feed(audio(0.0, 2000)) is PhraseStatus.TIMEOUT


def test_long_phrase_is_cut():
    rec = recorder(max_phrase_sec=1)
    assert rec.feed(audio(0.5, 1100)) is PhraseStatus.DONE


def test_audio_drops_long_silence_before_speech():
    rec = recorder()
    rec.feed(audio(0.0, 1500))
    rec.feed(audio(0.5, 500))
    rec.feed(audio(0.0, 800))
    out = rec.audio()
    assert len(out) < 16 * (300 + 500 + 800 + 100)  # 300 ms pad, not 1.5 s of silence
    assert out.max() == np.float32(0.5)


def test_odd_block_sizes_are_split_into_frames():
    rec = recorder()
    for _ in range(10):
        rec.feed(audio(0.5, 100))              # 1600 samples, not a multiple of 512
    assert len(rec.audio()) % FRAME_SIZE == 0
    assert rec.started
