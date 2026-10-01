"""Linux implementation of the OS layer."""

from __future__ import annotations

import shutil
import subprocess
import webbrowser
from collections.abc import Sequence

from myata.oslayer.base import LaunchError, expand_argv


class LinuxLayer:
    name = "linux"

    def launch(self, argv: Sequence[str]) -> None:
        if not argv:
            raise LaunchError("empty command")
        exe, *args = expand_argv(argv)
        resolved = shutil.which(exe)
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
