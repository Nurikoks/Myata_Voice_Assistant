"""What the rest of Myata needs from the operating system."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Protocol


class LaunchError(Exception):
    """Raised when an application cannot be started."""


class UnsupportedOSError(RuntimeError):
    """Raised on an OS that Myata does not support yet."""


class OSLayer(Protocol):
    name: str

    def launch(self, argv: Sequence[str]) -> None:
        """Start a program in the background. Raises LaunchError if it fails."""

    def open_url(self, url: str) -> bool:
        """Open a URL in the default browser. Returns False if it failed."""


def expand_argv(argv: Sequence[str]) -> list[str]:
    """Expand ~ and environment variables (%VAR% on Windows, $VAR everywhere)."""
    return [os.path.expandvars(os.path.expanduser(arg)) for arg in argv]
