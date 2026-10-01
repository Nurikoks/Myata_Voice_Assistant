"""Silero TTS (v5_ru by default) on the CPU, played through sounddevice.

The model is one torch.package file in models/silero/, loaded without
torch.hub, so it works fully offline. Model licence: CC BY-NC 4.0.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from pathlib import Path

from myata.audio.player import AudioPlayer
from myata.config import SileroTtsConfig
from myata.tts.normalize import NumberSpeller, default_speller, prepare_for_speech

log = logging.getLogger(__name__)

MODEL_URL = "https://models.silero.ai/models/tts/ru/{name}"


class SileroTTS:
    def __init__(
        self,
        config: SileroTtsConfig,
        player: AudioPlayer,
        replacements: Mapping[str, str],
        speller: NumberSpeller | None = None,
    ) -> None:
        path = Path(config.model_path)
        if not path.is_file():
            raise FileNotFoundError(
                f"Silero TTS model not found at '{path.resolve()}'. Download it with:\n"
                f"Invoke-WebRequest {MODEL_URL.format(name=path.name)} "
                f"-OutFile {config.model_path}"
            )
        import torch

        started = time.perf_counter()
        torch.set_num_threads(config.threads)
        self._model = torch.package.PackageImporter(str(path)).load_pickle("tts_models", "model")
        self._model.to(torch.device("cpu"))
        self._config = config
        self._player = player
        self._replacements = dict(replacements)
        self._speller = speller or default_speller()
        self._synthesize("Проверка.")  # the first call is slow, do it now
        seconds = time.perf_counter() - started
        log.info("Silero TTS %s (%s) ready in %.1f s", path.name, config.speaker, seconds)

    def speak(self, text: str) -> None:
        text = prepare_for_speech(text, self._replacements, self._speller)
        if not text:
            return
        started = time.perf_counter()
        audio = self._synthesize(text)
        log.info(
            "Silero: %d chars in %.2f s, %.1f s of speech",
            len(text), time.perf_counter() - started, len(audio) / self._config.sample_rate,
        )
        self._player.play(audio, self._config.sample_rate)

    def _synthesize(self, text: str):
        c = self._config
        audio = self._model.apply_tts(
            text=text,
            speaker=c.speaker,
            sample_rate=c.sample_rate,
            put_accent=c.put_accent,
            put_yo=c.put_yo,
            put_stress_homo=c.put_stress_homo,
            put_yo_homo=c.put_yo_homo,
        )
        return audio.numpy()
