import os

import pytest

from myata.oslayer import LaunchError, UnsupportedOSError, current_os_name, expand_argv
from myata.oslayer.linux import LinuxLayer


def test_current_os_name():
    assert current_os_name("win32") == "windows"
    assert current_os_name("linux") == "linux"
    with pytest.raises(UnsupportedOSError):
        current_os_name("darwin")


def test_expand_argv():
    os.environ["MYATA_TEST_DIR"] = "games"
    try:
        assert expand_argv(["$MYATA_TEST_DIR/lol", "--flag"]) == ["games/lol", "--flag"]
    finally:
        del os.environ["MYATA_TEST_DIR"]


def test_missing_program_raises():
    with pytest.raises(LaunchError):
        LinuxLayer().launch(["definitely-not-a-real-program-42"])
