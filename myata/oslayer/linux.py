"""Linux implementation of the OS layer (written for Linux Mint 22, Cinnamon on X11).

External tools, installed with apt (see README):
  pactl      volume (works with PipeWire through pipewire-pulse, Mint's default)
  playerctl  media keys (any player that supports MPRIS: browsers, Spotify, VLC)
  systemctl  shutdown, reboot, sleep (no sudo needed for the logged-in user)
  xclip      clipboard on X11 (wl-paste on Wayland, xsel also works)
A capability is only reported when its tool is installed, so skills that need
a missing tool are simply not registered.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from myata.oslayer.base import (
    CLIPBOARD,
    MEDIA,
    POWER,
    SCREENSHOT,
    VOLUME,
    LaunchError,
    OSActionError,
    clamp_percent,
    expand_argv,
    has_module,
    mss_screenshot,
)

log = logging.getLogger(__name__)

SINK = "@DEFAULT_SINK@"
_PERCENT = re.compile(r"(\d+)%")
_PLAYERCTL = {"play_pause": "play-pause", "next": "next", "previous": "previous", "stop": "stop"}
_SYSTEMCTL = {"shutdown": "poweroff", "reboot": "reboot", "sleep": "suspend"}

Runner = Callable[..., subprocess.CompletedProcess]


class LinuxLayer:
    name = "linux"

    def __init__(
        self,
        run: Runner = subprocess.run,
        which: Callable[[str], str | None] = shutil.which,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self._run_process = run
        self._which = which
        self._env = os.environ if env is None else env

    def capabilities(self) -> frozenset[str]:
        caps = set()
        if self._which("pactl"):
            caps.add(VOLUME)
        if self._which("playerctl"):
            caps.add(MEDIA)
        if self._which("systemctl"):
            caps.add(POWER)
        if self._clipboard_command():
            caps.add(CLIPBOARD)
        if has_module("mss") and not self._wayland():
            caps.add(SCREENSHOT)  # mss cannot capture a Wayland session
        return frozenset(caps)

    # ---------- apps and links ----------

    def launch(self, argv: Sequence[str]) -> None:
        if not argv:
            raise LaunchError("empty command")
        exe, *args = expand_argv(argv)
        resolved = self._which(exe)
        if resolved is None:
            raise LaunchError(f"'{exe}' is not installed or not in PATH")
        try:
            subprocess.Popen(
                [resolved, *args],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # the app keeps running after Myata exits
            )
        except OSError as e:
            raise LaunchError(f"cannot start '{exe}': {e}") from e

    def open_url(self, url: str) -> bool:
        return webbrowser.open(url)

    # ---------- sound ----------

    def get_volume(self) -> int:
        # "Volume: front-left: 28411 /  43% / -21.78 dB,   front-right: ..."
        match = _PERCENT.search(self._run("pactl", "get-sink-volume", SINK))
        if match is None:
            raise OSActionError("cannot parse the pactl output")
        return int(match.group(1))

    def set_volume(self, percent: int) -> None:
        self._run("pactl", "set-sink-mute", SINK, "0")
        self._run("pactl", "set-sink-volume", SINK, f"{clamp_percent(percent)}%")

    def set_mute(self, muted: bool) -> None:
        self._run("pactl", "set-sink-mute", SINK, "1" if muted else "0")

    def media_key(self, key: str) -> None:
        command = _PLAYERCTL.get(key)
        if command is None:
            raise OSActionError(f"unknown media key: {key}")
        self._run("playerctl", command)  # fails with "No players found" if nothing plays

    # ---------- power ----------

    def power(self, action: str) -> None:
        command = _SYSTEMCTL.get(action)
        if command is None:
            raise OSActionError(f"unknown power action: {action}")
        self._run("systemctl", command)

    # ---------- clipboard and screen ----------

    def read_clipboard(self) -> str:
        command = self._clipboard_command()
        if command is None:
            raise OSActionError("no clipboard tool: install xclip")
        try:
            result = self._run_process(command, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError) as e:
            raise OSActionError(f"{command[0]} failed: {e}") from e
        # xclip exits with an error when the clipboard is empty or holds a picture.
        return result.stdout if result.returncode == 0 else ""

    def screenshot(self, path: Path) -> None:
        mss_screenshot(path)

    # ---------- helpers ----------

    def _wayland(self) -> bool:
        return bool(self._env.get("WAYLAND_DISPLAY"))

    def _clipboard_command(self) -> list[str] | None:
        if self._wayland() and self._which("wl-paste"):
            return ["wl-paste", "--no-newline"]
        if self._which("xclip"):
            return ["xclip", "-selection", "clipboard", "-o"]
        if self._which("xsel"):
            return ["xsel", "--clipboard", "--output"]
        return None

    def _run(self, *argv: str) -> str:
        try:
            result = self._run_process(
                list(argv), capture_output=True, text=True, timeout=5, check=True
            )
        except subprocess.CalledProcessError as e:
            detail = (e.stderr or "").strip() or f"exit code {e.returncode}"
            raise OSActionError(f"{argv[0]} failed: {detail}") from e
        except (OSError, subprocess.SubprocessError) as e:
            raise OSActionError(f"{argv[0]} failed: {e}") from e
        return result.stdout
