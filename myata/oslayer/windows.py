"""Windows implementation of the OS layer."""

from __future__ import annotations

import os
import subprocess
import webbrowser
from collections.abc import Sequence

from myata.oslayer.base import LaunchError, expand_argv


class WindowsLayer:
    name = "windows"

    def launch(self, argv: Sequence[str]) -> None:
        if not argv:
            raise LaunchError("empty command")
        exe, *args = expand_argv(argv)
        try:
            # ShellExecute understands both full paths and short names like "chrome"
            # (through the App Paths registry), just like "start chrome" did before,
            # but without a shell. It raises OSError if the program is not found.
            os.startfile(exe, arguments=subprocess.list2cmdline(args))  # type: ignore[attr-defined]
        except OSError as e:
            raise LaunchError(f"cannot start '{exe}': {e}") from e

    def open_url(self, url: str) -> bool:
        return webbrowser.open(url)
