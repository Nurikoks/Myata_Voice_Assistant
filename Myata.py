import json
import queue
import subprocess
import time
import webbrowser
from datetime import datetime
from difflib import SequenceMatcher

import pyttsx3
import sounddevice as sd
from vosk import KaldiRecognizer, Model

MODEL_PATH = "vosk-model-small-ru-0.22"
SAMPLE_RATE = 16000
WAKE_WORDS = ["мята", "миата", "ята", "Матя"]  # как Vosk может его "услышать"
LISTEN_WINDOW = 6       # сколько секунд ждать команду после одного "Джарвис"
MATCH_THRESHOLD = 0.6   # насколько фраза должна быть похожа на команду (0..1)

LOL_PATH = r"C:\Riot Games\Riot Client\RiotClientServices.exe"


# ---------- действия ----------
def action(shell=None, url=None, reply=""):
    def run():
        if shell:
            subprocess.Popen(shell, shell=True)
        if url:
            webbrowser.open(url)
        return reply
    return run


def tell_time():
    now = datetime.now()
    return f"Сейчас {now.hour} часов {now.minute} минут"


EXIT = object()

# (варианты фразы, что делать)
COMMANDS = [
    (["открой лигу легенд", "запусти лигу легенд", "запусти лигу"],
     action(shell=f'"{LOL_PATH}" --launch-product=league_of_legends --launch-patchline=live',
            reply="Запускаю Лигу Легенд, сэр")),
    (["открой браузер", "запусти браузер"], action(shell="start chrome", reply="Открываю браузер")),
    (["открой ютуб", "включи ютуб"], action(url="https://youtube.com", reply="Открываю ютуб")),
    (["открой проводник"], action(shell="explorer", reply="Открываю проводник")),
    (["открой блокнот"], action(shell="notepad", reply="Открываю блокнот")),
    (["который час", "сколько времени"], tell_time),
    (["выключись", "отключись", "стоп"], EXIT),
]


# ---------- голос ----------
def speak(text):
    print("Мята:", text)
    engine = pyttsx3.init()  # новый движок каждый раз: обход бага pyttsx3 на Windows
    for v in engine.getProperty("voices"):
        name = (v.name + v.id).lower()
        if "ru" in name or "irina" in name or "russian" in name:
            engine.setProperty("voice", v.id)
            break
    engine.setProperty("rate", 180)
    engine.say(text)
    engine.runAndWait()


# ---------- распознавание ----------
def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()


def is_wake(word):
    return max(similar(word, w) for w in WAKE_WORDS) >= 0.75


def find_command(text):
    best, best_score = None, 0
    for phrases, func in COMMANDS:
        for p in phrases:
            score = similar(text, p)
            if score > best_score:
                best, best_score = func, score
    return best if best_score >= MATCH_THRESHOLD else None


def handle(text):
    """Возвращает False, если надо завершить работу."""
    func = find_command(text)
    if func is None:
        speak("Не понял команду")
    elif func is EXIT:
        speak("До связи, сэр")
        return False
    else:
        speak(func())
    return True


audio_q = queue.Queue()


def mic_callback(indata, frames, t, status):
    audio_q.put(bytes(indata))


def clear_queue():
    while not audio_q.empty():
        audio_q.get_nowait()


def main():
    model = Model(MODEL_PATH)
    rec = KaldiRecognizer(model, SAMPLE_RATE)
    active_until = 0
    speak("Джарвис на связи")

    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000, dtype="int16",
                           channels=1, callback=mic_callback):
        while True:
            if not rec.AcceptWaveform(audio_q.get()):
                continue
            text = json.loads(rec.Result()).get("text", "")
            if not text:
                continue
            print("Вы:", text)

            words = text.split()
            has_wake = any(is_wake(w) for w in words)
            command = " ".join(w for w in words if not is_wake(w))

            if has_wake and not command:          # сказали только "Джарвис"
                speak("Слушаю")
                active_until = time.time() + LISTEN_WINDOW
            elif has_wake or time.time() < active_until:
                active_until = 0
                if not handle(command):
                    break
            else:
                continue                          # речь без обращения к Джарвису
            clear_queue()                         # чтобы он не слушал сам себя
            rec.Reset()


if __name__ == "__main__":
    main()
