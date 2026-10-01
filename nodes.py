from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QScrollArea,
    QFrame, QLabel, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
import database
import preferences
from login import User


# status (lowercase) -> (label, text colour, badge background)
_STATUS_STYLE = {
    "sos":      ("SOS",      "#ef4444", "#3b0000"),
    "active":   ("Active",   "#22c55e", "#052e16"),
    "inactive": ("Inactive", "#94a3b8", "#1e293b"),
}

_TILE_MIN_WIDTH = 250


def _status_style(status: str):
    return _STATUS_STYLE.get(str(status).lower(), (str(status).capitalize() or "Unknown", "#60a5fa", "#172554"))


def _time_ago(timestamp: str) -> str:
    try:
        secs = int((datetime.now() - datetime.fromisoformat(str(timestamp))).total_seconds())
    except ValueError:
        return ""
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{secs // 60} min ago"
    if secs < 86400:
        return f"{secs // 3600} hr ago"
    return f"{secs // 86400} day{'s' if secs >= 172800 else ''} ago"


class _StatFilter(QFrame):
    """Summary tile (count + label) that also acts as a status filter."""
    clicked = pyqtSignal()

    def __init__(self, label: str, color: str, parent=None):
        super().__init__(parent)
        self.setObjectName("statFilter")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._active = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(0)
        self.count_lbl = QLabel("0")
        self.count_lbl.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: 800;")
        cap = QLabel(label.upper())
        cap.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;")
        lay.addWidget(self.count_lbl)
        lay.addWidget(cap)
        self._refresh()

    def set_count(self, n: int):
        self.count_lbl.setText(str(n))

    def set_active(self, active: bool):
        self._active = active
        self._refresh()

    def mousePressEvent(self, event):
        self.clicked.emit()

    def _refresh(self):
        border = "#2563eb" if self._active else "#1a2540"
        self.setStyleSheet(f"""
            QFrame#statFilter {{ background-color: #0f172b; border: 1px solid {border}; border-radius: 10px; }}
            QFrame#statFilter:hover {{ border-color: {'#2563eb' if self._active else '#2a3a52'}; }}
            QLabel {{ background: transparent; border: none; }}
        """)


class _NodeTile(QFrame):
    """Card for a single node in the grid."""
    def __init__(self, row, authorized: bool, use_24h: bool, on_view, parent=None):
        super().__init__(parent)
        time, node_id, lat, lon, status = row
        label, fg, bg = _status_style(status)
        is_sos = str(status).lower() == "sos"

        self.setObjectName("nodeTile")
        self.setMinimumWidth(_TILE_MIN_WIDTH - 20)
        self.setStyleSheet(f"""
            QFrame#nodeTile {{
                background-color: #0f172b; border-radius: 10px;
                border: 1px solid {'#ef4444' if is_sos else '#1a2540'};
            }}
            QLabel {{ background: transparent; border: none; }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        # Top row: node number + status badge
        top = QHBoxLayout()
        id_box = QVBoxLayout()
        id_box.setSpacing(0)
        cap = QLabel("NODE")
        cap.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;")
        num = QLabel(str(node_id))
        num.setStyleSheet("color: #f1f5f9; font-size: 26px; font-weight: 800;")
        id_box.addWidget(cap)
        id_box.addWidget(num)
        top.addLayout(id_box)
        top.addStretch()
        badge = QLabel(f"●  {label}")
        badge.setFixedHeight(22)
        badge.setStyleSheet(f"color: {fg}; background-color: {bg}; border-radius: 11px; "
                            f"padding: 0 10px; font-size: 11px; font-weight: 700;")
        top.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)

        # Details
        for caption, value, sub in (
            ("LAST SEEN", _time_ago(time), preferences.format_time(time, use_24h)),
            ("LOCATION", f"{lat:.5f}, {lon:.5f}" if authorized else "Hidden",
             "Latitude, longitude" if authorized else "You don't have access to this node"),
        ):
            box = QVBoxLayout()
            box.setSpacing(1)
            c = QLabel(caption)
            c.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;")
            v = QLabel(value)
            v.setStyleSheet(f"color: {'#cbd5e1' if authorized or caption != 'LOCATION' else '#64748b'}; "
                            f"font-size: 13px; font-weight: 600;")
            box.addWidget(c)
            box.addWidget(v)
            if sub:
                s = QLabel(sub)
                s.setStyleSheet("color: #64748b; font-size: 11px;")
                box.addWidget(s)
            lay.addLayout(box)

        lay.addSpacing(4)
        btn = QPushButton("View on Map")
        btn.setFixedHeight(32)
        btn.setEnabled(authorized)
        btn.setCursor(Qt.CursorShape.PointingHandCursor if authorized else Qt.CursorShape.ArrowCursor)
        btn.setStyleSheet("""
            QPushButton { padding:6px 10px; border:1px solid #2b3a4a; border-radius:6px; background: transparent; color: #cfd8ff; }
            QPushButton:hover { background-color: #162040; }
            QPushButton:disabled { color: #3d4f68; border-color: #1a2540; }
        """)
        btn.clicked.connect(lambda _, n=node_id: on_view(int(n)))
        lay.addWidget(btn)


class NodesPage(QWidget):
    """Grid of every node in the database with its latest status."""

    viewNodeRequested = pyqtSignal(int)

    _FILTERS = [("All", "#f1f5f9"), ("SOS", "#ef4444"), ("Active", "#22c55e"), ("Inactive", "#94a3b8")]

    def __init__(self, parent=None, user: User = None):
        super().__init__(parent)

        self.nodes = []  # cached latest row per node: (time, node_id, lat, lon, status)
        self.user = user if user else User("Guest")
        self.use_24h = True
        self.current_filter = "All"
        self._tiles: list[_NodeTile] = []
        self._cols = 0

        self.setMinimumSize(600, 400)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        self.setLayout(layout)

        # Header / controls (same controls as the Notifications and History pages)
        header_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setStyleSheet("QPushButton { padding:6px 10px; border:1px solid #2b3a4a; border-radius:6px; }"
                                       "QPushButton:hover {background-color: #162040;}"
        )
        self.my_nodes_checkbox = QCheckBox("My Nodes")
        self.my_nodes_checkbox.setStyleSheet(
            "QCheckBox { color: #cfd8ff; spacing:6px; font-weight:600; }"
            "QCheckBox::indicator { width:18px; height:18px; }"
        )
        title_lbl = QLabel("Nodes")
        title_lbl.setStyleSheet("font-size:16px; font-weight:700; color: #cfd8ff;")
        self.updated_lbl = QLabel("")
        self.updated_lbl.setStyleSheet("font-size: 11px; color: gray;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        header_layout.addWidget(self.updated_lbl)
        header_layout.addSpacing(8)
        header_layout.addWidget(self.my_nodes_checkbox)
        header_layout.addWidget(self.refresh_btn)
        layout.addLayout(header_layout)

        # Summary tiles that double as status filters
        stats = QHBoxLayout()
        stats.setSpacing(12)
        self._stat_btns: dict[str, _StatFilter] = {}
        for name, color in self._FILTERS:
            btn = _StatFilter(name, color)
            btn.clicked.connect(lambda n=name: self.set_filter(n))
            stats.addWidget(btn)
            self._stat_btns[name] = btn
        layout.addLayout(stats)

        # Scrollable grid of node tiles
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_content = QFrame()
        self.grid = QGridLayout(self.scroll_content)
        self.grid.setContentsMargins(0, 4, 0, 4)
        self.grid.setSpacing(12)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll, stretch=1)

        self.empty_lbl = QLabel("")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_lbl.setStyleSheet("font-size:14px; color: gray; padding:20px;")

        # Connections
        self.refresh_btn.clicked.connect(lambda checked=False: self.load_nodes())
        self.my_nodes_checkbox.stateChanged.connect(lambda _: self._apply_filters())

        # Auto-refresh while the page is visible
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._auto_refresh)
        self._timer.start(5000)

        self.set_filter("All")

    def load_nodes(self):
        """Fetch the latest row for every node from the DB and rebuild the grid."""
        try:
            self.nodes = database.get_latest_node_rows()
        except Exception as e:
            print(f"load_nodes(): get_latest_node_rows failed: {e}")
            self.nodes = []
        self.updated_lbl.setText("Updated " + datetime.now().strftime(
            "%H:%M:%S" if self.use_24h else "%I:%M:%S %p"))
        self._apply_filters()

    def _auto_refresh(self):
        if self.isVisible():
            self.load_nodes()

    def set_filter(self, name: str):
        self.current_filter = name
        for n, btn in self._stat_btns.items():
            btn.set_active(n == name)
        self._apply_filters()

    def set_time_format(self, use_24h: bool):
        self.use_24h = use_24h
        self._apply_filters()

    def _apply_filters(self):
        rows = self.nodes
        if self.my_nodes_checkbox.isChecked():
            rows = [r for r in rows if r[1] in self.user.viewable_nodes]

        statuses = [str(r[4]).lower() for r in rows]
        self._stat_btns["All"].set_count(len(rows))
        for name in ("SOS", "Active", "Inactive"):
            self._stat_btns[name].set_count(statuses.count(name.lower()))

        if self.current_filter != "All":
            rows = [r for r in rows if str(r[4]).lower() == self.current_filter.lower()]
        # SOS nodes first, then by node id
        rows = sorted(rows, key=lambda r: (str(r[4]).lower() != "sos", r[1]))

        for tile in self._tiles:
            tile.hide()
            tile.deleteLater()
        self._tiles = [
            _NodeTile(r, r[1] in self.user.viewable_nodes, self.use_24h, self.viewNodeRequested.emit)
            for r in rows
        ]
        if not rows:
            self.empty_lbl.setText("No nodes in the database yet" if not self.nodes
                                   else "No nodes match this filter")
        self._cols = 0
        self._layout_grid()

    def _layout_grid(self):
        cols = max(1, self.scroll.viewport().width() // _TILE_MIN_WIDTH)
        if cols == self._cols and self.grid.count() == max(len(self._tiles), 1):
            return
        self._cols = cols
        while self.grid.count():
            self.grid.takeAt(0)
        if not self._tiles:
            self.empty_lbl.show()
            self.grid.addWidget(self.empty_lbl, 0, 0)
            return
        self.empty_lbl.hide()
        for i, tile in enumerate(self._tiles):
            self.grid.addWidget(tile, i // cols, i % cols, Qt.AlignmentFlag.AlignTop)
        for c in range(max(cols, self.grid.columnCount())):
            self.grid.setColumnStretch(c, 1 if c < cols else 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_grid()
