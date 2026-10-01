"""Command line entry point: python -m myata [--text] [--speak] [--list-skills]."""

from __future__ import annotations

import argparse
import logging
import sys

from myata import __version__
from myata.app import build_assistant, run_text, run_voice
from myata.config import ConfigError, load_config
from myata.logging_setup import setup_logging
from myata.oslayer import UnsupportedOSError

log = logging.getLogger("myata")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="myata", description="Offline voice assistant")
    parser.add_argument("--config", default="config.yaml", help="path to config.yaml")
    parser.add_argument("--text", action="store_true", help="type commands instead of speaking")
    parser.add_argument("--speak", action="store_true", help="in text mode, also say answers")
    parser.add_argument("--list-skills", action="store_true", help="print skills and exit")
    parser.add_argument("--debug", action="store_true", help="show debug logs in the console")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        return 2

    console_level = "DEBUG" if args.debug else config.logging.console_level
    setup_logging(config.logging.level, console_level, config.logging.file)

    try:
        if args.list_skills:
            _, registry = build_assistant(config, speak=False)
            for item in registry:
                print(f"{item.name:<28} {item.description}")
        elif args.text:
            run_text(config, speak=args.speak)
        else:
            run_voice(config)
    except KeyboardInterrupt:
        log.info("Stopped with Ctrl+C")
    except (FileNotFoundError, UnsupportedOSError) as e:
        log.error("%s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
