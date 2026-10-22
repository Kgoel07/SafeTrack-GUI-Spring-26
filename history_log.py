from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea,
    QFrame, QLabel, QComboBox, QSizePolicy, QCheckBox
)
from PyQt6.QtCore import Qt
import database
from i18n import tr, notif_text
from login import User


class HistoryLogPage(QWidget):
    def __init__(self, parent=None, user:User=None):
        super().__init__(parent)

        self.logs = []  # cached history log entries (only updated on refresh)
        self.user = user if user else User("Guest")

        self.setMinimumSize(600, 400)

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Header / controls
        header_layout = QHBoxLayout()
        self.refresh_btn = QPushButton(tr("Refresh"))
        self.refresh_btn.setStyleSheet("QPushButton { padding:6px 10px; border:1px solid #2b3a4a; border-radius:6px; }"
                                       "QPushButton:hover {background-color: #162040;}"
        )
        # NOTE: filter UI is provided by the outer wrapper (tab buttons).
        # Keep internal filter state but do not expose a dropdown here.
        # shorter label and styling to match the app theme
        self.my_nodes_checkbox = QCheckBox(tr("My Nodes"))
        self.my_nodes_checkbox.setStyleSheet(
            "QCheckBox { color: #cfd8ff; spacing:6px; font-weight:600; }"
            "QCheckBox::indicator { width:18px; height:18px; }"
        )
        title_lbl = QLabel(tr("History & Log"))
        title_lbl.setStyleSheet("font-size:16px; font-weight:700; color: #cfd8ff;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        # header_layout.addWidget(self.filter_combo)  # dropdown removed (use pills)
        header_layout.addWidget(self.my_nodes_checkbox)
        header_layout.addWidget(self.refresh_btn)
        layout.addLayout(header_layout)

        # Scrollable list container for history log 'cards'
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QFrame()
        self.scroll_layout = QVBoxLayout()
        self.scroll_layout.setContentsMargins(8, 8, 8, 8)
        self.scroll_layout.setSpacing(8)
        self.scroll_content.setLayout(self.scroll_layout)
        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll)

        # Connections
        self.refresh_btn.clicked.connect(self.load_history_logs)
        # The wrapper (FilteredlogsPage) will call `set_filter()` on this
        # page to apply filters via the pill buttons. Keep the slot for
        # compatibility but do not connect a dropdown signal here.
        self.my_nodes_checkbox.stateChanged.connect(self.on_my_nodes_toggled)

        # Filter state: None or lowercase string
        self.current_filter = None
        # default: show all nodes (unchecked). Keep state synced with checkbox
        self.my_nodes = False
        self.my_nodes_checkbox.setChecked(self.my_nodes)

    def load_history_logs(self):
        """Fetch history log entries from the DB and populate the list of cards.
        Intentionally only called when the Refresh button is pressed."""
        self.logs = database.get_logs()
        i = 0
        while i < len(self.logs):
            if self.logs[i][1] not in self.user.viewable_nodes:
                if self.logs[i][2] == "SOS" and not self.my_nodes:
                    self.logs[i] = (self.logs[i][0], self.logs[i][1], self.logs[i][2], self.logs[i][3], "(UNAUTHORIZED TO VIEW LOCATION)")
                else:
                    self.logs.pop(i)
                    i -= 1
            i += 1
        # keep whatever current_filter is set by wrapper; default show all
        if self.current_filter is None:
            self._populate_list(self.logs)
        else:
            wanted = self.current_filter.lower()
            filtered = [r for r in self.logs if len(r) > 2 and str(r[2]).lower() == wanted]
            self._populate_list(filtered)

    def set_filter(self, tab: str | None):
        """Apply a filter by tab name (e.g. 'All','SOS','Alert',...).
        Called by an external wrapper when pill buttons are used.
        Pass `None` or 'All' to clear the filter.
        """
        if tab is None or tab == "All":
            self.current_filter = None
            self._populate_list(self.logs)
            return
        wanted = tab.lower()
        self.current_filter = wanted
        filtered = [r for r in self.logs if len(r) > 2 and str(r[2]).lower() == wanted]
        self._populate_list(filtered)

    def _clear_list(self):
        while self.scroll_layout.count():
            child = self.scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _populate_list(self, rows):
        self._clear_list()
        for r in rows:
            # expected row format: (time, node_id, status, Title, Message)
            time = str(r[0]) if len(r) > 0 else ""
            node_id = str(r[1]) if len(r) > 1 else ""
            status = str(r[2]) if len(r) > 2 else ""
            title = str(r[3]) if len(r) > 3 else ""
            message = str(r[4]) if len(r) > 4 else ""

            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel)
            # keep a subtle background and rounded corners but remove inner borders
            card.setStyleSheet("background-color: #0f1724; border-radius:8px;")
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            card_layout = QHBoxLayout()
            card_layout.setContentsMargins(8, 8, 8, 8)

            # Left: title and message (vertical)
            left = QVBoxLayout()
            title_lbl = QLabel(notif_text(title))
            title_lbl.setStyleSheet("font-weight: 600; font-size: 14px;")
            msg_lbl = QLabel(notif_text(message))
            msg_lbl.setWordWrap(True)
            left.addWidget(title_lbl)
            left.addWidget(msg_lbl)

            # Right: status and time
            right = QVBoxLayout()
            status_lbl = QLabel(tr(status))
            status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            status_lbl.setStyleSheet("font-weight: 700; color: #c0392b;")
            time_lbl = QLabel(time)
            time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            time_lbl.setStyleSheet("font-size: 10px; color: gray;")
            right.addWidget(status_lbl)
            right.addWidget(time_lbl)

            card_layout.addLayout(left)
            card_layout.addLayout(right)
            card.setLayout(card_layout)

            self.scroll_layout.addWidget(card)

        # add stretch at bottom
        self.scroll_layout.addStretch()

    def on_filter_changed(self, index: int):
        """Apply the dropdown filter to the cached history log entries.
        Does not query the DB; only filters in-memory list.
        Options: All, Alert, System"""
        # kept for compatibility if dropdown is ever re-added; no-op otherwise
        return

    def on_my_nodes_toggled(self):
        self.my_nodes = self.my_nodes_checkbox.isChecked()
        self.load_history_logs()