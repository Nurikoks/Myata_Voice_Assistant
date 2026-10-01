# Myata Voice Assistant

Myata (Мята) is an offline voice assistant that understands Russian.
Say "Мята" and a command, for example "Мята, открой ютуб", or just talk to her.

Simple commands run instantly. Free-form phrases ("закинь мне ютуб",
"найди на ютубе лоу-фай") and small talk go to a local LLM through Ollama.

> Work in progress. A full README with architecture diagram and demo comes in stage 5.

## How the voice works

1. A small Vosk model with a one-word grammar listens only for "мята".
2. Silero VAD records the phrase until you stop talking (the last second before
   the wake word is kept, so "мята, открой ютуб" in one breath is not cut).
3. faster-whisper (large-v3-turbo, GPU) turns the phrase into text and checks
   that the name is really there, which filters out false alarms.
4. The fast router or the LLM decides what to do, Silero TTS answers.

While Myata thinks or talks, the microphone is muted. If she asks a question
or needs "да"/"нет", you can answer without saying her name.

## What she can do

- open websites and launch apps from `config.yaml`, search Google or YouTube
- volume ("громче", "выключи звук", "сделай громкость 30"), media keys ("пауза", "следующий трек")
- shut down, restart or sleep the computer (always asks "да или нет" first)
- notes ("запиши купить молоко", "что в заметках"), read or translate the clipboard,
  screenshots
- scenes: one phrase runs several steps, e.g. "игровой режим" starts Discord and Steam
- several actions at once: "открой дискорд и стим"

Skills that return information (notes, clipboard) send it back to the LLM, which
answers the actual question ("переведи то, что я скопировал"). Without Ollama they
read the information out as is. A skill that needs something the system lacks
(no `playerctl` on Linux, for example) is simply not registered.

## Setup (Windows)

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[dev,voice]"
```

torch is installed from the CPU index on purpose: Silero runs on the CPU, and
Whisper uses the GPU through CTranslate2 with the `nvidia-cublas-cu12` and
`nvidia-cudnn-cu12` packages, not through torch.

Install [Ollama](https://ollama.com/download) and pull the model:

```powershell
ollama pull qwen3.5:4b
```

Download the models into `models/`:

```powershell
New-Item -ItemType Directory -Force models\silero | Out-Null
Invoke-WebRequest https://raw.githubusercontent.com/snakers4/silero-vad/master/src/silero_vad/data/silero_vad.jit -OutFile models\silero\silero_vad.jit
Invoke-WebRequest https://models.silero.ai/models/tts/ru/v5_ru.pt -OutFile models\silero\v5_ru.pt
python -c "from faster_whisper import download_model; download_model('large-v3-turbo', output_dir='models/whisper-large-v3-turbo')"
```

And `vosk-model-small-ru-0.22` from https://alphacephei.com/vosk/models,
unzipped to `models/vosk-model-small-ru-0.22`.

Silero TTS models are licensed CC BY-NC 4.0 (non-commercial use).

## Setup (Linux Mint 22)

```bash
sudo apt install python3-venv libportaudio2 espeak-ng libespeak1 pulseaudio-utils playerctl xclip
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[dev,voice]"
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3.5:4b
```

Install the NVIDIA driver through Driver Manager first. The CUDA libraries for
Whisper come from pip and are loaded by Myata itself, no `LD_LIBRARY_PATH` needed.
Models are downloaded the same way as on Windows (use `wget -O` or `curl -Lo`
instead of `Invoke-WebRequest`). Screenshots need an X11 session (the Mint default).
Check the Linux commands of your apps in `config.yaml`: Flatpak apps start with
`flatpak run <app id>`.

## Run

```powershell
python -m myata                 # voice mode
python -m myata --text          # type commands, no microphone needed
python -m myata --text --speak  # type commands, hear the answers
python -m myata --no-llm        # fast commands only, without Ollama
python -m myata --list-skills   # show what Myata can do on this OS
python -m myata --list-devices  # show microphones and speakers
```

Settings, phrases, models, voice, websites, apps and scenes are in `config.yaml`.
Notes are saved to `data/notes.md`.
Logs go to `logs/myata.log`.

## Development

```powershell
pytest
ruff check .
```

Tests need neither a microphone nor the voice models.

## Project layout

```
myata/
  __main__.py   command line entry point
  app.py        wires everything together, voice and text loops
  config.py     config.yaml into typed dataclasses
  core/         assistant logic (works on text only, easy to test)
  brain/        fast router, LLM client, dialog history, prompt
  skills/       skill registry, built-in skills, skills from config
  voice/        voice loop state machine (wake, record, busy)
  wake/         Vosk wake word spotter, wake word check in text
  stt/          Silero VAD and faster-whisper
  tts/          Silero TTS, pyttsx3 fallback, text normalization
  audio/        microphone input with mute, speaker output
  oslayer/      everything OS-specific (Windows, Linux, CUDA libraries)
tests/          tests that run without a microphone
```

### Adding a skill

Create a file in `myata/skills/builtin/`:

```python
from myata.skills.base import SkillContext, SkillResult
from myata.skills.registry import skill


@skill(name="say_hello", description="Greet the user", phrases=["привет"])
def say_hello(ctx: SkillContext) -> SkillResult:
    return SkillResult("Привет, сэр")
```

It is picked up automatically. To add a website, an app or a scene, just add it to `config.yaml`.

Skills can also take arguments from the LLM (`parameters=` with a JSON schema,
arguments are validated before the skill runs), ask for voice confirmation
(`dangerous=True`), need an OS capability (`requires=[VOLUME]`) and return
`SkillResult(speech, data=...)` to let the LLM phrase the answer.
Everything OS-specific goes into `myata/oslayer/`.
The LLM can only call registered skills, never shell commands.
