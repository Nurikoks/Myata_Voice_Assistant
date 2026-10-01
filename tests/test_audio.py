import numpy as np

from myata.audio.microphone import Microphone
from myata.audio.player import pcm16_to_float
from myata.oslayer.cuda import prepare_cuda_libraries


def test_muted_microphone_drops_audio():
    mic = Microphone(16000, 1600)
    mic._callback(b"\x01\x00" * 4, 4, None, None)
    mic.mute()
    mic._callback(b"\x02\x00" * 4, 4, None, None)
    mic.unmute()
    assert mic.read(timeout=0.01) == b"\x01\x00" * 4
    assert mic.read(timeout=0.01) is None


def test_pcm16_to_float():
    samples = pcm16_to_float(np.array([0, 16384, -32768], dtype=np.int16).tobytes())
    assert samples.dtype == np.float32
    assert list(samples) == [0.0, 0.5, -1.0]


def test_cuda_preparation_is_windows_only():
    assert prepare_cuda_libraries("linux") == []
