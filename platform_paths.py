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


def _parse_steam_libraries() -> list:
    """
    Read additional Steam library paths from libraryfolders.vdf.
    Returns a list of directory paths (may be empty if file not found or parse fails).
    """
    vdf_path = os.path.expanduser("~/.steam/steam/steamapps/libraryfolders.vdf")
    roots = []
    if not os.path.isfile(vdf_path):
        return roots
    try:
        with open(vdf_path, encoding="utf-8") as f:
            for line in f:
                # Lines look like:   "path"    "/home/user/games/Steam"
                if '"path"' in line.lower():
                    parts = line.strip().split('"')
                    # parts[1]='path', parts[3]='/actual/path'
                    if len(parts) >= 4:
                        roots.append(parts[3])
    except Exception:
        pass
    return roots


def _find_proton_docs() -> str:
    """
    Search all known Steam library roots for AC's Proton Documents folder.
    Returns the first existing path, or a best-guess fallback if none found yet
    (AC may not have been launched yet, so the folder won't exist until first run).
    """
    all_roots = _STEAM_ROOTS + _parse_steam_libraries()
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
    if is_linux():
        for root in _STEAM_ROOTS:
            candidate = os.path.join(root, "steamapps", "common", "assettocorsa")
            if os.path.isdir(candidate):
                return candidate
        # Return the most common path as a fallback hint
        return os.path.join(_STEAM_ROOTS[0], "steamapps", "common", "assettocorsa")
    return r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa"


def get_webview_gui() -> str:
    """
    Return the pywebview gui= backend for the current OS.
    'edgechromium' on Windows (Edge WebView2, pre-installed on Win 10/11).
    'gtk'          on Linux  (requires libwebkit2gtk-4.0 or libwebkit2gtk-4.1).
    """
    return "gtk" if is_linux() else "edgechromium"
