"""
platform_paths.py — OS-specific path helpers for AC Career GT Edition.

On Windows, Assetto Corsa stores its config and results in:
    ~/Documents/Assetto Corsa/

On Linux, AC runs via Steam Proton (Wine).  Config and results live inside
the Proton compat-data prefix:
    ~/.steam/steam/steamapps/compatdata/244210/pfx/drive_c/users/steamuser/Documents/Assetto Corsa/

Import this module in app.py and career_manager.py.
"""

import os
import platform
import re
from typing import List

# Steam App ID for Assetto Corsa
AC_STEAM_APPID = 244210

# Path segments from a Steam library root to AC's Documents folder inside Proton
_PROTON_SUBPATH = os.path.join(
    "steamapps", "compatdata", str(AC_STEAM_APPID),
    "pfx", "drive_c", "users", "steamuser", "Documents", "Assetto Corsa"
)

# Standard Steam root directories on Linux, checked in order
_STEAM_ROOTS = [
    os.path.expanduser("~/.steam/steam"),
    os.path.expanduser("~/.local/share/Steam"),
]


def is_linux() -> bool:
    return platform.system() == "Linux"


def is_windows() -> bool:
    return platform.system() == "Windows"


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        if not item:
            continue
        key = os.path.normcase(os.path.normpath(item))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _parse_steam_libraries(vdf_path: str) -> List[str]:
    """
    Read additional Steam library paths from libraryfolders.vdf.
    Returns a list of directory paths (may be empty if file not found or parse fails).
    """
    roots: List[str] = []
    if not os.path.isfile(vdf_path):
        return roots
    try:
        with open(vdf_path, encoding="utf-8", errors="ignore") as f:
            txt = f.read()
        for raw in re.findall(r'"path"\s*"([^"]+)"', txt, flags=re.IGNORECASE):
            roots.append(raw.replace("\\\\", "\\").strip())
    except Exception:
        pass
    return _dedupe_keep_order(roots)


def _candidate_install_paths_from_library(library_path: str) -> List[str]:
    return [
        os.path.join(library_path, "steamapps", "common", "assettocorsa"),
        os.path.join(library_path, "steamapps", "common", "Assetto Corsa"),
    ]


def _looks_like_ac_install(path: str) -> bool:
    return bool(path) and os.path.isfile(os.path.join(path, "acs.exe"))


def _linux_library_roots() -> List[str]:
    roots: List[str] = []
    for steam_root in _STEAM_ROOTS:
        roots.append(steam_root)  # default Steam library lives under Steam root
        vdf = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")
        roots.extend(_parse_steam_libraries(vdf))
    return _dedupe_keep_order(roots)


def _windows_steam_roots() -> List[str]:
    roots: List[str] = []

    # Common defaults
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base:
            roots.append(os.path.join(base, "Steam"))
    roots.extend([r"C:\Steam", r"D:\Steam", r"E:\Steam", r"F:\Steam"])

    # Registry-based Steam path
    try:
        import winreg  # type: ignore

        reg_locations = [
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamExe"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
        ]
        for hive, key_path, value_name in reg_locations:
            try:
                with winreg.OpenKey(hive, key_path) as k:
                    value, _ = winreg.QueryValueEx(k, value_name)
                    if isinstance(value, str) and value:
                        if value.lower().endswith(".exe"):
                            value = os.path.dirname(value)
                        roots.append(value)
            except Exception:
                continue
    except Exception:
        pass

    # Existing folders first, then fallbacks
    existing = [r for r in roots if os.path.isdir(r)]
    missing = [r for r in roots if not os.path.isdir(r)]
    return _dedupe_keep_order(existing + missing)


def _windows_library_roots() -> List[str]:
    libs: List[str] = []
    for steam_root in _windows_steam_roots():
        libs.append(steam_root)
        vdf = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")
        libs.extend(_parse_steam_libraries(vdf))
    return _dedupe_keep_order(libs)


def get_ac_install_candidates() -> List[str]:
    """
    Return likely AC install folders for this OS, ordered by confidence.
    """
    candidates: List[str] = []
    if is_linux():
        for library in _linux_library_roots():
            candidates.extend(_candidate_install_paths_from_library(library))
    else:
        for library in _windows_library_roots():
            candidates.extend(_candidate_install_paths_from_library(library))
    return _dedupe_keep_order(candidates)


def detect_ac_install_path() -> str:
    """
    Return the first AC install folder that contains acs.exe, else empty string.
    """
    for candidate in get_ac_install_candidates():
        if _looks_like_ac_install(candidate):
            return candidate
    return ""


def _find_proton_docs() -> str:
    """
    Search all known Steam library roots for AC's Proton Documents folder.
    Returns the first existing path, or a best-guess fallback if none found yet
    (AC may not have been launched yet, so the folder won't exist until first run).
    """
    all_roots = _linux_library_roots()
    for root in all_roots:
        candidate = os.path.join(root, _PROTON_SUBPATH)
        if os.path.isdir(candidate):
            return candidate
    # Fall back to the most common path even if it doesn't exist yet
    return os.path.join(_STEAM_ROOTS[0], _PROTON_SUBPATH)


def get_ac_docs_path(subfolder: str = "") -> str:
    """
    Return the path to the AC Documents folder (or a subfolder within it).

    Windows: ~/Documents/Assetto Corsa/<subfolder>
    Linux:   Proton compat-data path/<subfolder>

    Examples:
        get_ac_docs_path("cfg")     → .../Assetto Corsa/cfg
        get_ac_docs_path("results") → .../Assetto Corsa/results
        get_ac_docs_path()          → .../Assetto Corsa
    """
    if is_linux():
        base = _find_proton_docs()
    else:
        base = os.path.join(os.path.expanduser("~"), "Documents", "Assetto Corsa")

    if subfolder:
        return os.path.join(base, subfolder)
    return base


def get_default_ac_install_path() -> str:
    """
    Return the most likely AC install path for the current OS.
    Used as a hint in the setup screen when ac_install is empty.
    """
    detected = detect_ac_install_path()
    if detected:
        return detected

    candidates = get_ac_install_candidates()
    if candidates:
        return candidates[0]

    if is_linux():
        return os.path.join(_STEAM_ROOTS[0], "steamapps", "common", "assettocorsa")
    return r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa"


def get_webview_gui() -> str:
    """
    Return the pywebview gui= backend for the current OS.
    'edgechromium' on Windows (Edge WebView2, pre-installed on Win 10/11).
    'gtk'          on Linux  (requires libwebkit2gtk-4.0 or libwebkit2gtk-4.1).
    """
    return "gtk" if is_linux() else "edgechromium"
