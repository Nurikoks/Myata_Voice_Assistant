"""OS-specific code lives here and nowhere else."""

from __future__ import annotations

import sys

from myata.oslayer.base import (
    ALL_CAPABILITIES,
    CLIPBOARD,
    MEDIA,
    MEDIA_KEYS,
    POWER,
    POWER_ACTIONS,
    SCREENSHOT,
    VOLUME,
    LaunchError,
    OSActionError,
    OSLayer,
    UnsupportedOSError,
    expand_argv,
)

__all__ = [
    "ALL_CAPABILITIES",
    "CLIPBOARD",
    "MEDIA",
    "MEDIA_KEYS",
    "POWER",
    "POWER_ACTIONS",
    "SCREENSHOT",
    "VOLUME",
    "LaunchError",
    "OSActionError",
    "OSLayer",
    "UnsupportedOSError",
    "current_os_name",
    "expand_argv",
    "get_os_layer",
]


def current_os_name(platform: str = sys.platform) -> str:
    if platform.startswith("win"):
        return "windows"
    if platform.startswith("linux"):
        return "linux"
    raise UnsupportedOSError(f"Myata does not support '{platform}' yet")


def get_os_layer() -> OSLayer:
    name = current_os_name()
    if name == "windows":
        from myata.oslayer.windows import WindowsLayer

        return WindowsLayer()
    from myata.oslayer.linux import LinuxLayer

    return LinuxLayer()
