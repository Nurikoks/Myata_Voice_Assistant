"""Make the pip-installed NVIDIA libraries visible to CTranslate2 (faster-whisper).

Call prepare_cuda_libraries() before faster_whisper or torch is imported.

Windows: the nvidia-cublas-cu12 / nvidia-cudnn-cu12 wheels put their DLLs into
site-packages/nvidia/<package>/bin, and Windows does not look there on its own.
We add those folders to the DLL search path and to PATH.

Linux: the same wheels keep their .so files in site-packages/nvidia/<package>/lib.
Changing LD_LIBRARY_PATH from inside Python is too late, so we load the
libraries ourselves with RTLD_GLOBAL. When CTranslate2 later asks for
"libcublas.so.12", the dynamic linker finds the already loaded copy.
"""

from __future__ import annotations

import ctypes
import importlib.util
import logging
import os
from collections.abc import Callable, Iterable
from pathlib import Path

from myata.oslayer import current_os_name

log = logging.getLogger(__name__)

WINDOWS_PACKAGES = ("cublas", "cudnn", "cuda_runtime", "cuda_nvrtc")
# Order matters: libcublas needs libcublasLt. cuDNN loads its sub-libraries itself.
LINUX_LIBRARIES = (
    ("cublas", "libcublasLt.so.12"),
    ("cublas", "libcublas.so.12"),
    ("cudnn", "libcudnn.so.9"),
)
INSTALL_HINT = 'pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"'

# Handles from os.add_dll_directory and ctypes: keep them for the whole run.
_handles: list[object] = []


def prepare_cuda_libraries(os_name: str | None = None) -> list[str]:
    """Return what was added or loaded (empty if nothing had to be done)."""
    os_name = os_name or current_os_name()
    locations = nvidia_locations()
    if os_name == "windows":
        return _prepare_windows(locations)
    return _prepare_linux(locations)


def nvidia_locations() -> list[str]:
    """Folders of the "nvidia" namespace package from the pip wheels."""
    spec = importlib.util.find_spec("nvidia")
    if spec is None or not spec.submodule_search_locations:
        return []
    return list(spec.submodule_search_locations)


def _prepare_windows(locations: Iterable[str]) -> list[str]:
    # torch and CTranslate2 both ship Intel's OpenMP runtime. Two copies in one
    # process stop the program with "OMP: Error #15" unless this is set.
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

    added = []
    for base in locations:
        for package in WINDOWS_PACKAGES:
            folder = Path(base) / package / "bin"
            if not folder.is_dir():
                continue
            _handles.append(os.add_dll_directory(str(folder)))  # type: ignore[attr-defined]
            os.environ["PATH"] = f"{folder}{os.pathsep}{os.environ.get('PATH', '')}"
            added.append(str(folder))
    if added:
        log.info("CUDA DLL folders added: %s", added)
    else:
        log.warning("No pip NVIDIA libraries found. For GPU recognition run: %s", INSTALL_HINT)
    return added


def _prepare_linux(
    locations: Iterable[str], load: Callable[[str], object] | None = None
) -> list[str]:
    load = load or (lambda path: ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL))
    loaded = []
    for package, name in LINUX_LIBRARIES:
        for base in locations:
            library = Path(base) / package / "lib" / name
            if not library.is_file():
                continue
            try:
                _handles.append(load(str(library)))
            except OSError as e:
                log.warning("Cannot load %s: %s", library, e)
                continue
            loaded.append(str(library))
            break
    if loaded:
        log.info("CUDA libraries preloaded: %s", loaded)
    else:
        log.info("No pip NVIDIA libraries found, relying on system CUDA (%s)", INSTALL_HINT)
    return loaded
