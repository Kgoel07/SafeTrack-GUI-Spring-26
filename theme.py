# ═══════════════════════════════════════════════════════
# theme.py  –  Light mode for the main window
#
# The app's colours are hard-coded (dark) in each widget's stylesheet.
# Rather than duplicating every stylesheet, light mode rewrites the dark
# colours to light equivalents.  An application-wide event filter catches
# widgets that are created or restyled later (e.g. refreshed cards), and the
# original dark stylesheet is kept so switching back is lossless.
# ═══════════════════════════════════════════════════════

import re

from PyQt6.QtCore import QObject, QEvent
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtWidgets import QApplication, QWidget, QAbstractButton

# dark colour -> light colour  (accent colours are intentionally left alone)
_COLOR_MAP = {
    # backgrounds
    "#060a13": "#f1f5f9",   # app background
    "#0b1120": "#ffffff",   # sidebar
    "#0f172b": "#ffffff",   # panels
    "#0f1724": "#ffffff",   # cards
    "#0b1220": "#f8fafc",   # settings cards / read-only inputs
    "#0d1526": "#ffffff",   # inputs
    "#0f1a30": "#ffffff",   # focused inputs
    "#162040": "#e0e7ff",   # hover
    "#1e293b": "#e2e8f0",
    "#172554": "#dbeafe",
    "#052e16": "#dcfce7",
    "#3b0000": "#fee2e2",
    "#431407": "#ffedd5",
    "#2e1065": "#ede9fe",
    # borders
    "#141e30": "#e2e8f0",
    "#1a2540": "#e2e8f0",
    "#1e2d44": "#cbd5e1",
    "#263645": "#cbd5e1",
    "#2b3a4a": "#cbd5e1",
    "#334155": "#cbd5e1",
    "#2a3a52": "#94a3b8",
    "#475569": "#94a3b8",
    # text
    "#f1f5f9": "#0f172a",
    "#e2e8f0": "#1e293b",
    "#cfd8ff": "#1e293b",
    "#cfd8e8": "#1e293b",
    "#cbd5e1": "#334155",
    "#b8c5d9": "#334155",
    "#94a3b8": "#475569",
    "#7a8ba8": "#475569",
    "#5a6a82": "#64748b",
    "#4a5a72": "#64748b",
    "#3d4f68": "#94a3b8",
    "#60a5fa": "#2563eb",
    "#a78bfa": "#7c3aed",
}

_WHITE = {"#ffffff", "#fff", "white"}
_WHITE_ON_LIGHT = "#0f172a"
_ICON_ON_LIGHT = "#475569"   # sidebar icons are white images; tint them for light mode

# Backgrounds that keep white text readable in both modes
_ACCENT_BGS = ("#2563eb", "#1d4ed8", "#1e40af", "#3b82f6", "#22c55e", "#16a34a",
               "#15803d", "#ef4444", "#dc2626", "#b91c1c", "#e06a6a", "#b53131")

_RGBA_MAP = {
    "rgba(255,255,255,0.02)": "rgba(15,23,42,0.03)",
    "rgba(255,255,255,0.04)": "rgba(15,23,42,0.05)",
    "rgba(255,255,255,0.08)": "rgba(15,23,42,0.08)",
}

_TOKEN_RE = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|\bwhite\b|rgba\([^)]*\)")

_light = False
_root: QWidget | None = None
_filter = None


def is_light() -> bool:
    return _light


def _translate_block(block: str) -> str:
    lower = block.lower()
    keep_white = any(re.search(r"background(-color)?\s*:\s*" + c, lower) for c in _ACCENT_BGS)

    def repl(m):
        tok = m.group(0)
        key = tok.lower()
        if key.startswith("rgba"):
            return _RGBA_MAP.get(key.replace(" ", ""), tok)
        if key in _WHITE:
            return tok if keep_white else _WHITE_ON_LIGHT
        return _COLOR_MAP.get(key, tok)

    return _TOKEN_RE.sub(repl, block)


def translate(css: str) -> str:
    """Convert a dark stylesheet to its light-mode equivalent."""
    # handle each `selector { ... }` block separately so the white-text rule
    # only looks at the background of the same block
    parts = re.split(r"(?<=\})", css)
    return "".join(_translate_block(p) for p in parts)


def _tinted_icon(path: str, color: str) -> QIcon:
    pix = QPixmap(path)
    if pix.isNull():
        return QIcon(path)
    p = QPainter(pix)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(pix.rect(), QColor(color))
    p.end()
    return QIcon(pix)


def _update_icon(w: QWidget):
    """Buttons that set `_theme_icon_path` get their icon tinted in light mode."""
    path = getattr(w, "_theme_icon_path", None)
    if path and isinstance(w, QAbstractButton):
        w.setIcon(_tinted_icon(path, _ICON_ON_LIGHT) if _light else QIcon(path))


def _in_scope(w: QWidget) -> bool:
    return _root is not None and (w is _root or _root.isAncestorOf(w))


def _apply_to(w: QWidget):
    css = w.styleSheet()
    if not css or css == w.property("_light_css"):
        return
    light = translate(css)
    w.setProperty("_dark_css", css)
    w.setProperty("_light_css", light)
    if light != css:
        w.setStyleSheet(light)


def _restore(w: QWidget):
    dark = w.property("_dark_css")
    if dark is not None and w.styleSheet() == w.property("_light_css"):
        w.setStyleSheet(dark)
    w.setProperty("_dark_css", None)
    w.setProperty("_light_css", None)


class _ThemeFilter(QObject):
    """Restyles widgets that are shown or restyled while light mode is on."""
    def eventFilter(self, obj, event):
        if _light and event.type() in (QEvent.Type.Polish, QEvent.Type.StyleChange) \
                and isinstance(obj, QWidget) and _in_scope(obj):
            _apply_to(obj)
        return False


def apply(root: QWidget, light: bool):
    """Switch `root` (the main window) and everything inside it to light or dark."""
    global _light, _root, _filter
    new_root = root is not _root
    _root = root
    if _filter is None:
        _filter = _ThemeFilter()
        QApplication.instance().installEventFilter(_filter)
    if light == _light and not new_root:
        return
    _light = light
    widgets = [root] + root.findChildren(QWidget)
    for w in widgets:
        if light:
            _apply_to(w)
        else:
            _restore(w)
        _update_icon(w)
    for w in widgets:
        w.update()


def reset(root: QWidget | None = None):
    """Turn light mode off when the main window closes (e.g. on logout).
    Does nothing if another main window has already taken over."""
    global _light, _root
    if root is not None and root is not _root:
        return
    _light = False
    _root = None
