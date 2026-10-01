"""Windows implementation of the OS layer."""

from __future__ import annotations

import logging
import os
import subprocess
import time
import webbrowser
from collections.abc import Sequence
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

# Virtual key codes of the media keys
_MEDIA_VK = {"play_pause": 0xB3, "next": 0xB0, "previous": 0xB1, "stop": 0xB2}
_KEYEVENTF_EXTENDEDKEY = 0x0001
_KEYEVENTF_KEYUP = 0x0002
_CF_UNICODETEXT = 13


class WindowsLayer:
    name = "windows"

    def capabilities(self) -> frozenset[str]:
        caps = {MEDIA, POWER, CLIPBOARD}
        if has_module("pycaw"):
            caps.add(VOLUME)
        if has_module("mss"):
            caps.add(SCREENSHOT)
        return frozenset(caps)

    # ---------- apps and links ----------

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

    # ---------- sound ----------

    def get_volume(self) -> int:
        try:
            return round(self._endpoint().GetMasterVolumeLevelScalar() * 100)
        except Exception as e:  # comtypes raises COMError
            raise OSActionError(f"cannot read the volume: {e}") from e

    def set_volume(self, percent: int) -> None:
        try:
            endpoint = self._endpoint()
            endpoint.SetMute(0, None)
            endpoint.SetMasterVolumeLevelScalar(clamp_percent(percent) / 100, None)
        except Exception as e:
            raise OSActionError(f"cannot set the volume: {e}") from e

    def set_mute(self, muted: bool) -> None:
        try:
            self._endpoint().SetMute(int(muted), None)
        except Exception as e:
            raise OSActionError(f"cannot change mute: {e}") from e

    @staticmethod
    def _endpoint():
        from pycaw.pycaw import AudioUtilities

        device = AudioUtilities.GetSpeakers()
        endpoint = getattr(device, "EndpointVolume", None)
        if endpoint is not None:
            return endpoint
        # pycaw before 2025 returned a raw IMMDevice
        from ctypes import POINTER, cast

        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import IAudioEndpointVolume

        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))

    def media_key(self, key: str) -> None:
        import ctypes

        vk = _MEDIA_VK.get(key)
        if vk is None:
            raise OSActionError(f"unknown media key: {key}")
        user32 = ctypes.WinDLL("user32")
        user32.keybd_event(vk, 0, _KEYEVENTF_EXTENDEDKEY, 0)
        user32.keybd_event(vk, 0, _KEYEVENTF_EXTENDEDKEY | _KEYEVENTF_KEYUP, 0)

    # ---------- power ----------

    def power(self, action: str) -> None:
        if action == "shutdown":
            self._run(["shutdown", "/s", "/t", "0"])
        elif action == "reboot":
            self._run(["shutdown", "/r", "/t", "0"])
        elif action == "sleep":
            import ctypes

            # SetSuspendState(hibernate=False, force=False, disable_wake_events=False)
            if not ctypes.WinDLL("powrprof").SetSuspendState(0, 0, 0):
                raise OSActionError("SetSuspendState failed")
        else:
            raise OSActionError(f"unknown power action: {action}")

    @staticmethod
    def _run(argv: list[str]) -> None:
        try:
            subprocess.run(argv, check=True, capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError) as e:
            raise OSActionError(f"{argv[0]} failed: {e}") from e

    # ---------- clipboard and screen ----------

    def read_clipboard(self) -> str:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = wintypes.HANDLE
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]

        # Another program may hold the clipboard for a moment.
        for _ in range(10):
            if user32.OpenClipboard(None):
                break
            time.sleep(0.05)
        else:
            raise OSActionError("the clipboard is busy")
        try:
            handle = user32.GetClipboardData(_CF_UNICODETEXT)
            if not handle:
                return ""  # empty, or not text (a picture, files)
            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                raise OSActionError("cannot lock the clipboard data")
            try:
                return ctypes.wstring_at(pointer)
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()

    def screenshot(self, path: Path) -> None:
        mss_screenshot(path)
