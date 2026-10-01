"""OS-specific code lives here and nowhere else."""

from __future__ import annotations

import sys

from myata.oslayer.base import LaunchError, OSLayer, UnsupportedOSError, expand_argv

__all__ = [
    "LaunchError",
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
