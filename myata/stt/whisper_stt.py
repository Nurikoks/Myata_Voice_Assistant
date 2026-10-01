"""Speech to text with faster-whisper (CTranslate2).

The model is loaded lazily by load(), which also runs one tiny transcription:
missing CUDA DLLs only fail on the first real computation, and we want that
to happen at startup, not on the user's first command.
"""

from __future__ import annotations

import logging
import shutil
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

import numpy as np

from myata.brain.text import normalize
from myata.config import SttConfig

log = logging.getLogger(__name__)

# faster-whisper needs these next to model.bin. Without preprocessor_config.json it
# assumes 80 mel bands, while large-v3 and turbo models use 128, and the text is garbage.
SIDE_FILES = ("preprocessor_config.json", "tokenizer.json")
RU_MODEL_DOWNLOAD = (
    'python -c "from huggingface_hub import snapshot_download; snapshot_download('
    "'coriollon/whisper-large-v3-turbo-russian', local_dir='models/whisper-turbo-ru', "
    "allow_patterns=['ct2_int8_float16/*', 'preprocessor_config.json', 'tokenizer.json'])\""
)


class SpeechToText(Protocol):
    def transcribe(self, audio: np.ndarray) -> str:
        """16 kHz mono float32 audio to text ("" if nothing useful was said)."""


class WhisperRecognizer:
    def __init__(self, config: SttConfig, sample_rate: int = 16000) -> None:
        self._config = config
        self._sample_rate = sample_rate
        self._model = None
        self.device = config.device

    def load(self) -> float:
        """Load the model and warm it up. Returns the time it took in seconds."""
        started = time.perf_counter()
        source = model_source(self._config.model)
        try:
            self._model = self._create(source, self._config.device, self._config.compute_type)
            self._warm_up()
        except (RuntimeError, OSError, ValueError) as e:
            if self._config.device == "cpu" or not self._config.cpu_fallback:
                raise
            log.warning("Whisper on %s failed (%s), falling back to CPU", self._config.device, e)
            print(f"Whisper не запустился на GPU ({e}). Перехожу на CPU, будет медленнее.")
            self._model = self._create(source, "cpu", self._config.cpu_compute_type)
            self.device = "cpu"
            self._warm_up()
        seconds = time.perf_counter() - started
        log.info("Whisper %s ready on %s in %.1f s", source, self.device, seconds)
        return seconds

    def _create(self, source: str, device: str, compute_type: str):
        from faster_whisper import WhisperModel

        return WhisperModel(
            source,
            device=device,
            compute_type=compute_type,
            download_root=self._config.download_root,
        )

    def _warm_up(self) -> None:
        silence = np.zeros(self._sample_rate // 2, dtype=np.float32)
        self._run(silence)

    def transcribe(self, audio: np.ndarray) -> str:
        if self._model is None:
            self.load()
        if audio.size == 0:
            return ""
        started = time.perf_counter()
        prompts = (self._config.hotwords, self._config.initial_prompt)
        text = clean_transcript(self._run(audio), self._config.hallucinations, prompts)
        log.info(
            "Whisper: %.1f s of audio in %.2f s: %r",
            audio.size / self._sample_rate,
            time.perf_counter() - started,
            text,
        )
        return text

    def _run(self, audio: np.ndarray) -> str:
        assert self._model is not None
        segments, _info = self._model.transcribe(
            audio,
            language=self._config.language,
            beam_size=self._config.beam_size,
            initial_prompt=self._config.initial_prompt,
            hotwords=self._config.hotwords,  # vocabulary hints: "Мята, ютуб, дискорд..."
            condition_on_previous_text=False,
            without_timestamps=True,
            vad_filter=False,  # our own VAD already cut the phrase
        )
        # segments is a generator: the actual work happens while iterating.
        return " ".join(s.text.strip() for s in segments).strip()


def model_source(model: str) -> str:
    """A local folder, or a name/repo id that faster-whisper downloads itself."""
    path = Path(model)
    if path.is_dir():
        complete_model_folder(path)
        return str(path)
    looks_local = path.is_absolute() or path.parts[0] in ("models", ".", "..") or "\\" in model
    if looks_local:
        raise FileNotFoundError(
            f"Whisper model folder not found: '{path.resolve()}'.\n"
            f"Russian turbo model: {RU_MODEL_DOWNLOAD}\n"
            "Or set stt.model in config.yaml to a name like large-v3-turbo."
        )
    return model


def complete_model_folder(path: Path) -> None:
    """Copy tokenizer and preprocessor files from the parent folder if they are missing.

    Some repos keep the CTranslate2 weights in a subfolder (ct2_int8_float16/) and
    these two files in the repo root.
    """
    for name in SIDE_FILES:
        target, source = path / name, path.parent / name
        if not target.exists() and source.is_file():
            shutil.copyfile(source, target)
            log.info("Copied %s into %s", name, path)
    if not (path / "preprocessor_config.json").exists():
        log.warning(
            "%s has no preprocessor_config.json; for large-v3 / turbo models "
            "recognition will be garbage", path,
        )


def clean_transcript(
    text: str, hallucinations: Iterable[str], prompts: Iterable[str | None] = ()
) -> str:
    """Drop the phrases Whisper invents on silence or noise ("Продолжение следует...").

    With hotwords or an initial prompt Whisper sometimes just repeats that hint
    on silence; such a result is dropped too.
    """
    flat = normalize(text)
    if not flat:
        return ""
    for phrase in hallucinations:
        if normalize(phrase) in flat:
            log.info("Dropped a Whisper hallucination: %r", text)
            return ""
    for prompt in prompts:
        if prompt and len(flat.split()) >= 3 and flat in normalize(prompt):
            log.info("Dropped an echo of the prompt: %r", text)
            return ""
    return text
