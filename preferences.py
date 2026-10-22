# ═══════════════════════════════════════════════════════
# preferences.py  –  Per-user app preferences (stored with QSettings)
# ═══════════════════════════════════════════════════════

from PyQt6.QtCore import QSettings

# key: (default, type)
DEFAULTS = {
    "light_mode":        (False, bool),  # light colour scheme for the main window
    "language":          ("en", str),    # "en" | "sw" – saved only; translations not implemented yet
    "startup_page":      ("Map", str),   # "Map" | "Nodes" | "History"
    "map_zoom":          (14, int),      # folium zoom level for the map page
    "show_sos_radius":   (True, bool),   # red circle around SOS nodes on the map
    "time_format_24h":   (True, bool),   # 24-hour vs 12-hour timestamps
    "retention_hours":   (48, int),      # how long node/notification data is kept
    "confirm_logout":    (True, bool),   # ask before logging out
}


def _store() -> QSettings:
    return QSettings("SafeTrack", "SafeTrack")


def load(username: str) -> dict:
    """Return this user's preferences, falling back to defaults."""
    s = _store()
    s.beginGroup(f"prefs/{username}")
    prefs = {}
    for key, (default, typ) in DEFAULTS.items():
        prefs[key] = s.value(key, default, type=typ)
    s.endGroup()
    return prefs


def save(username: str, prefs: dict):
    s = _store()
    s.beginGroup(f"prefs/{username}")
    for key in DEFAULTS:
        if key in prefs:
            s.setValue(key, prefs[key])
    s.endGroup()
    s.sync()


def format_time(timestamp: str, use_24h: bool) -> str:
    """Format a DB timestamp ("YYYY-MM-DD HH:MM:SS") for display."""
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(str(timestamp))
    except ValueError:
        return str(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S" if use_24h else "%Y-%m-%d %I:%M:%S %p")


def clear(username: str):
    """Remove a user's saved preferences (e.g. after deleting their account)."""
    s = _store()
    s.remove(f"prefs/{username}")
    s.sync()


def load_last_language() -> str:
    """Language last chosen on this computer (used by the login screen)."""
    return _store().value("last_language", "en", type=str)


def save_last_language(code: str):
    s = _store()
    s.setValue("last_language", code)
    s.sync()
