"""Logging: detailed log file plus a quiet console."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(level: str, console_level: str, log_file: str | None) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG)
    formatter = logging.Formatter(FORMAT)

    console = logging.StreamHandler()
    console.setLevel(console_level.upper())
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setLevel(level.upper())
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
