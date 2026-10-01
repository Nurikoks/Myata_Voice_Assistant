"""What the rest of Myata needs from the operating system."""

from __future__ import annotations

import importlib.util
import logging
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

log = logging.getLogger(__name__)

# Capabilities: a skill that needs one of these is registered only if the OS layer has it.
VOLUME = "volume"
MEDIA = "media"
POWER = "power"
CLIPBOARD = "clipboard"
SCREENSHOT = "screenshot"
ALL_CAPABILITIES = frozenset({VOLUME, MEDIA, POWER, CLIPBOARD, SCREENSHOT})

MEDIA_KEYS = ("play_pause", "next", "previous", "stop")
POWER_ACTIONS = ("shutdown", "reboot", "sleep")


class OSActionError(Exception):
    """Raised when the OS could not do what was asked."""


class LaunchError(OSActionError):
    """Raised when an application cannot be started."""


class UnsupportedOSError(RuntimeError):
    """Raised on an OS that Myata does not support yet."""


class OSLayer(Protocol):
    name: str

    def capabilities(self) -> frozenset[str]:
        """What this machine can do (see the constants above)."""

    def launch(self, argv: Sequence[str]) -> None:
        """Start a program in the background. Raises LaunchError if it fails."""

    def open_url(self, url: str) -> bool:
        """Open a URL in the default browser. Returns False if it failed."""

    def get_volume(self) -> int:
        """Master volume, 0..100."""

    def set_volume(self, percent: int) -> None:
        """Set the master volume (0..100) and unmute."""

    def set_mute(self, muted: bool) -> None: ...

    def media_key(self, key: str) -> None:
        """Press a media key, one of MEDIA_KEYS."""

    def power(self, action: str) -> None:
        """Shut down, reboot or put the computer to sleep, one of POWER_ACTIONS."""

    def read_clipboard(self) -> str:
        """Text in the clipboard ("" if there is none)."""

    def screenshot(self, path: Path) -> None:
        """Save a screenshot of all monitors as a PNG file."""


def expand_argv(argv: Sequence[str]) -> list[str]:
    """Expand ~ and environment variables (%VAR% on Windows, $VAR everywhere)."""
    return [os.path.expandvars(os.path.expanduser(arg)) for arg in argv]


def clamp_percent(value: int) -> int:
    return max(0, min(100, int(value)))


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def mss_screenshot(path: Path) -> None:
    """Screenshot of all monitors with mss (works on Windows and on Linux with X11)."""
    import mss

    path.parent.mkdir(parents=True, exist_ok=True)
    factory = getattr(mss, "MSS", None) or mss.mss  # mss 10.2+ renamed the factory
    try:
        with factory() as sct:
            sct.shot(mon=-1, output=str(path))
    except Exception as e:  # mss raises ScreenShotError and plain OS errors
        raise OSActionError(f"screenshot failed: {e}") from e
