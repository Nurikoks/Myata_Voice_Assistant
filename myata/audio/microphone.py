"""Reads raw 16-bit mono audio from the microphone into a queue."""

from __future__ import annotations

import logging
import queue

log = logging.getLogger(__name__)


class Microphone:
    def __init__(self, sample_rate: int, block_size: int, device: int | str | None = None):
        self._sample_rate = sample_rate
        self._block_size = block_size
        self._device = device
        self._queue: queue.Queue[bytes] = queue.Queue()
        self._stream = None

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
        log.info("Microphone started (%d Hz)", self._sample_rate)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        log.info("Microphone stopped")

    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            log.warning("Audio input status: %s", status)
        self._queue.put(bytes(indata))

    def read(self, timeout: float = 0.5) -> bytes | None:
        """Next audio chunk, or None after the timeout.

        A timeout instead of a blocking get() lets Ctrl+C work on Windows.
        """
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear(self) -> None:
        """Drop buffered audio, so Myata does not hear her own voice."""
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return
