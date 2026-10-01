from myata.core.assistant import Outcome
from myata.stt.vad import PhraseRecorder
from myata.voice.loop import AudioRing, Phase, VoiceLoop
from tests.fakes import (
    SPEECH,
    FakeMic,
    FakeSpotter,
    FakeSTT,
    FakeVad,
    danger_skill,
    make_assistant,
    pcm,
)


def make_loop(*texts, extra_skills=()):
    assistant, tts, os_layer, clock = make_assistant(extra_skills=extra_skills)
    mic, spotter = FakeMic(), FakeSpotter()
    stt = FakeSTT(mic, *texts)
    recorder = PhraseRecorder(
        FakeVad(),
        sample_rate=16000,
        threshold=0.5,
        silence_ms=700,
        min_speech_ms=200,
        max_phrase_sec=15,
    )
    loop = VoiceLoop(
        assistant=assistant,
        mic=mic,
        spotter=spotter,
        recorder=recorder,
        stt=stt,
        sample_rate=16000,
        preroll_sec=1.0,
        wake_timeout_sec=5.0,
        unmute_delay_sec=0.0,
        sleep=lambda _s: None,
    )
    return loop, spotter, stt, mic, tts, os_layer


def feed(loop, chunk: bytes, times: int = 1):
    outcome = None
    for _ in range(times):
        result = loop.step(chunk)
        outcome = result or outcome
    return outcome


def say(loop, speech_ms: int = 1500, silence_ms: int = 1000):
    """The user talks, then goes quiet. Feeds 100 ms blocks like the real microphone."""
    outcome = feed(loop, pcm(SPEECH, 100), speech_ms // 100)
    return feed(loop, pcm(0, 100), silence_ms // 100) or outcome


def test_wake_word_and_command_in_one_breath():
    loop, spotter, stt, mic, tts, os_layer = make_loop("Мята, открой ютуб.")
    feed(loop, pcm(0, 100), 5)                  # background silence
    assert loop.phase is Phase.WAKE
    spotter.arm()
    assert say(loop) is Outcome.HANDLED
    assert os_layer.opened == ["https://youtube.com"]
    assert stt.muted_while_busy == [True]       # the mic was off while she worked
    assert not mic.muted and loop.phase is Phase.WAKE


def test_preroll_keeps_the_start_of_the_phrase():
    loop, spotter, stt, *_ = make_loop("Мята, открой ютуб.")
    feed(loop, pcm(SPEECH, 100), 3)             # "мя-" before Vosk reacted
    spotter.arm()
    say(loop, speech_ms=500)
    assert stt.lengths[0] >= 16000 * 0.7        # the 300 ms before the trigger are there


def test_false_wake_word_is_ignored():
    loop, spotter, _, mic, tts, os_layer = make_loop("Мать, открой ютуб.")
    spotter.arm()
    assert say(loop) is Outcome.IGNORED
    assert os_layer.opened == [] and tts.spoken == []
    assert loop.phase is Phase.WAKE and not mic.muted


def test_bare_wake_word_then_command_without_name():
    loop, spotter, _, _, tts, os_layer = make_loop("Мята.", "Открой блокнот.")
    spotter.arm()
    assert say(loop) is Outcome.LISTENING
    assert tts.spoken == ["Слушаю"]
    assert loop.phase is Phase.COMMAND          # no wake word needed now
    assert say(loop) is Outcome.HANDLED
    assert os_layer.launched == [["notepad"]]


def test_silence_after_listening_goes_back_to_wake():
    loop, spotter, *_ = make_loop("Мята.")
    spotter.arm()
    say(loop)
    feed(loop, pcm(0, 100), 70)                 # 7 s of silence, window is 6 s
    assert loop.phase is Phase.WAKE
    assert loop._assistant.reply_window == 0


def test_confirmation_by_voice():
    calls: list[str] = []
    loop, spotter, *_ = make_loop(
        "Мята, выключи компьютер.", "Да.", extra_skills=[danger_skill(calls)]
    )
    spotter.arm()
    say(loop)
    assert calls == [] and loop.phase is Phase.COMMAND
    say(loop, speech_ms=400)
    assert calls == ["boom"]


def test_stop_ends_the_loop_and_keeps_mic_muted():
    loop, spotter, _, mic, _, _ = make_loop("Мята, стоп.")
    spotter.arm()
    assert say(loop) is Outcome.STOP
    assert mic.muted


def test_empty_recognition_is_ignored():
    loop, spotter, _, mic, tts, _ = make_loop("")
    spotter.arm()
    assert say(loop) is Outcome.IGNORED
    assert tts.spoken == [] and not mic.muted


def test_audio_ring_keeps_only_the_newest_audio():
    import numpy as np

    ring = AudioRing(1000)
    for i in range(5):
        ring.append(np.full(400, i, dtype=np.float32))
    audio = ring.take()
    assert len(audio) == 1000 and audio[-1] == 4 and audio[0] == 2
    assert len(ring.take()) == 0
