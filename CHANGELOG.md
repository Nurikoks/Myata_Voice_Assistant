# Changelog

The project was rebuilt from a single script in stages. Each stage is one version.

## 0.5.0 (2026-10-02): portfolio

- GitHub Actions: ruff, and pytest on Windows and Ubuntu with Python 3.11 and 3.13
- README with architecture and voice loop diagrams, demo, tech stack and model licenses
- MIT license, project metadata in `pyproject.toml`, this changelog

## 0.4.5: fixes after the first voice tests

- fast router compares word lemmas (pymorphy3); numbers become arguments
  ("громкость 30" calls `set_volume(level=30)` without the LLM)
- "ещё раз" / "повтори" repeat the last safe action
- more ways to turn Myata off; the LLM may call hidden skills it saw in the history
- system prompt without the time, so Ollama can reuse its prompt cache
- Russian fine-tune of Whisper large-v3-turbo, vocabulary hints (hotwords)
- models load in parallel; startup shows how much of the LLM sits on the GPU
- per-phrase timing in the log

## 0.4.0: skills and Linux

- volume, media keys, shutdown / restart / sleep with voice confirmation
- notes, clipboard, screenshots, config-driven scenes ("игровой режим")
- several tool calls per command; data from skills goes back to the LLM for the answer
- skills declare the OS capabilities they need and are registered only where they work
- Linux layer (pactl, playerctl, systemctl, xclip), CUDA libraries preloaded on Linux

## 0.3.0: voice

- Vosk with a one-word grammar listens for the wake word
- Silero VAD records the phrase, faster-whisper recognizes it on the GPU
- Whisper must also hear the name, which filters out false wake-ups
- Silero TTS with number and Latin-word normalization, pyttsx3 as fallback
- voice loop as a state machine; the microphone is muted while Myata thinks or talks

## 0.2.0: brain

- local LLM through Ollama with tool calling and short dialog history
- fast path for known phrases, the LLM only when the fast path is not sure
- tool arguments validated against JSON schemas, voice confirmation for dangerous skills

## 0.1.0: package

- the original script refactored into the `myata` package
- YAML config with strict validation, logging, ruff and pytest
- all OS-specific code moved to `myata/oslayer/`
