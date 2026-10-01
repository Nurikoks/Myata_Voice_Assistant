# Myata Voice Assistant

Myata (Мята) is an offline voice assistant that understands Russian.
Say "Мята" and a command, for example "Мята, открой ютуб", or just talk to her.

Simple commands run instantly. Free-form phrases ("закинь мне ютуб",
"найди на ютубе лоу-фай") and small talk go to a local LLM through Ollama.

> Work in progress. A full README with architecture diagram and demo comes in stage 5.

## Setup (Windows)

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Install [Ollama](https://ollama.com/download) and pull the model:

```powershell
ollama pull qwen3.5:4b
```

Download `vosk-model-small-ru-0.22` from https://alphacephei.com/vosk/models
and unzip it to `models/vosk-model-small-ru-0.22`.

## Run

```powershell
python -m myata                 # voice mode
python -m myata --text          # type commands, no microphone needed
python -m myata --text --speak  # type commands, hear the answers
python -m myata --no-llm        # fast commands only, without Ollama
python -m myata --list-skills   # show what Myata can do on this OS
```

Settings, phrases, websites and apps are in `config.yaml`. Logs go to `logs/myata.log`.

## Development

```powershell
pytest
ruff check .
```

## Project layout

```
myata/
  __main__.py   command line entry point
  app.py        wires everything together, voice and text loops
  config.py     config.yaml into typed dataclasses
  core/         assistant logic (works on text only, easy to test)
  brain/        fast router, LLM client, dialog history, prompt
  skills/       skill registry, built-in skills, skills from config
  wake/         wake word detection
  stt/          speech to text (Vosk)
  tts/          text to speech (pyttsx3)
  audio/        microphone input
  oslayer/      everything OS-specific (Windows, Linux)
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

It is picked up automatically. To add a website or an app, just add it to `config.yaml`.

Skills can also take arguments from the LLM (`parameters=` with a JSON schema,
arguments are validated before the skill runs) and ask for voice confirmation
(`dangerous=True`). The LLM can only call registered skills, never shell commands.
