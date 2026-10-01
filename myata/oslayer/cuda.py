"""Make the pip-installed NVIDIA libraries visible to CTranslate2 (faster-whisper).

Call prepare_cuda_libraries() before faster_whisper or torch is imported.

Windows: the nvidia-cublas-cu12 / nvidia-cudnn-cu12 wheels put their DLLs into
site-packages/nvidia/<package>/bin, and Windows does not look there on its own.
We add those folders to the DLL search path and to PATH.

Linux: handled in stage 4 (the libraries must be on LD_LIBRARY_PATH before
Python starts, or preloaded with ctypes).
"""

from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path

from myata.oslayer import current_os_name

log = logging.getLogger(__name__)

NVIDIA_PACKAGES = ("cublas", "cudnn", "cuda_runtime", "cuda_nvrtc")

# Handles from os.add_dll_directory: the folder is removed from the search
# path when its handle is closed, so we keep them for the whole run.
_dll_handles: list[object] = []


def prepare_cuda_libraries(os_name: str | None = None) -> list[str]:
    """Return the folders that were added (empty if nothing had to be done)."""
    os_name = os_name or current_os_name()
    if os_name != "windows":
        return []

    # torch and CTranslate2 both ship Intel's OpenMP runtime. Two copies in one
    # process stop the program with "OMP: Error #15" unless this is set.
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

    added = []
    for folder in _nvidia_bin_folders():
        _dll_handles.append(os.add_dll_directory(str(folder)))  # type: ignore[attr-defined]
        os.environ["PATH"] = f"{folder}{os.pathsep}{os.environ.get('PATH', '')}"
        added.append(str(folder))
    if added:
        log.info("CUDA DLL folders added: %s", added)
    else:
        log.warning(
            "No pip NVIDIA libraries found. For GPU speech recognition run: "
            'pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"'
        )
    return added


def _nvidia_bin_folders() -> list[Path]:
    spec = importlib.util.find_spec("nvidia")
    if spec is None or not spec.submodule_search_locations:
        return []
    folders = []
    for base in spec.submodule_search_locations:
        for package in NVIDIA_PACKAGES:
            folder = Path(base) / package / "bin"
            if folder.is_dir():
                folders.append(folder)
    return folders
