"""Reads raw 16-bit mono audio from the microphone into a queue."""

from __future__ import annotations

import logging
import queue

log = logging.getLogger(__name__)


class Microphone:
    """Microphone with an explicit mute switch.

    While muted, the audio callback drops every block, so Myata never hears
    her own voice or what was said while she was busy thinking.
    """

    def __init__(self, sample_rate: int, block_size: int, device: int | str | None = None):
        self._sample_rate = sample_rate
        self._block_size = block_size
        self._device = device
        self._queue: queue.Queue[bytes] = queue.Queue()
        self._stream = None
        self._muted = False

    def __enter__(self) -> Microphone:
        import sounddevice as sd  # imported here so tests and CI do not need PortAudio

        self._stream = sd.RawInputStream(
            samplerate=self._sample_rate,
            blocksize=self._block_size,
            dtype="int16",
            channels=1,
            device=self._device,
            callback=self._callback,
        )
        self._stream.start()
        log.info(
            "Microphone started (%d Hz, %d samples per block)",
            self._sample_rate,
            self._block_size,
        )
        return self

    def __exit__(self, *exc: object) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        log.info("Microphone stopped")

    @property
    def muted(self) -> bool:
        return self._muted

    def mute(self) -> None:
        self._muted = True

    def unmute(self) -> None:
        self._muted = False

    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            log.warning("Audio input status: %s", status)
        if self._muted:
            return
        self._queue.put(bytes(indata))

    def read(self, timeout: float = 0.5) -> bytes | None:
        """Next audio block, or None after the timeout.

        A timeout instead of a blocking get() lets Ctrl+C work on Windows.
        """
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
