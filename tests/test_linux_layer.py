import subprocess
import tempfile
from pathlib import Path

import pytest

from myata.oslayer import CLIPBOARD, MEDIA, POWER, VOLUME, OSActionError
from myata.oslayer.cuda import LINUX_LIBRARIES, _prepare_linux
from myata.oslayer.linux import LinuxLayer


class FakeRun:
    """Stands in for subprocess.run and records the commands."""

    def __init__(self, stdout: str = "", returncode: int = 0) -> None:
        self.commands: list[list[str]] = []
        self.stdout = stdout
        self.returncode = returncode

    def __call__(self, argv, **kwargs):
        self.commands.append(list(argv))
        if kwargs.get("check") and self.returncode:
            raise subprocess.CalledProcessError(self.returncode, argv, "", "No players found")
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, "")


def layer(run=None, tools=("pactl", "playerctl", "systemctl", "xclip"), env=None):
    def which(name):
        return f"/usr/bin/{name}" if name in tools else None

    return LinuxLayer(run=run or FakeRun(), which=which, env=env or {})


def test_capabilities_follow_installed_tools():
    assert {VOLUME, MEDIA, POWER, CLIPBOARD} <= layer().capabilities()
    assert layer(tools=("systemctl",)).capabilities() & {VOLUME, MEDIA, CLIPBOARD} == set()


def test_volume_is_parsed_from_pactl():
    run = FakeRun("Volume: front-left: 28411 /  43% / -21.78 dB,   front-right: 28411 /  43%\n")
    assert layer(run).get_volume() == 43
    assert run.commands == [["pactl", "get-sink-volume", "@DEFAULT_SINK@"]]


def test_set_volume_unmutes_and_clamps():
    run = FakeRun()
    layer(run).set_volume(150)
    assert run.commands == [
        ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"],
        ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "100%"],
    ]


def test_media_and_power_commands():
    run = FakeRun()
    os_layer = layer(run)
    os_layer.media_key("play_pause")
    os_layer.power("sleep")
    os_layer.power("shutdown")
    assert run.commands == [
        ["playerctl", "play-pause"],
        ["systemctl", "suspend"],
        ["systemctl", "poweroff"],
    ]


def test_failed_tool_becomes_os_action_error():
    with pytest.raises(OSActionError):
        layer(FakeRun(returncode=1)).media_key("next")


def test_clipboard_x11_and_wayland():
    run = FakeRun("скопированный текст")
    assert layer(run).read_clipboard() == "скопированный текст"
    assert run.commands[0][0] == "xclip"
    run = FakeRun("text")
    wayland = layer(run, tools=("wl-paste", "xclip"), env={"WAYLAND_DISPLAY": "wayland-0"})
    wayland.read_clipboard()
    assert run.commands[0] == ["wl-paste", "--no-newline"]


def test_empty_clipboard_is_empty_text():
    assert layer(FakeRun(returncode=1)).read_clipboard() == ""


def test_cuda_libraries_are_preloaded_in_order():
    with tempfile.TemporaryDirectory() as tmp:
        for package, name in LINUX_LIBRARIES:
            folder = Path(tmp) / package / "lib"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / name).touch()
        loaded: list[str] = []
        _prepare_linux([tmp], load=loaded.append)
    expected = ["libcublasLt.so.12", "libcublas.so.12", "libcudnn.so.9"]
    assert [Path(p).name for p in loaded] == expected


def test_no_cuda_libraries_is_fine():
    assert _prepare_linux([], load=lambda path: None) == []
