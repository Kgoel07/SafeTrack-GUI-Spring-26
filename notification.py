# ----------------- Notifications Backend -----------------

# Notif = (time, node_id, status, title, message, is_read)

import database
from datetime import datetime

def _parse_time(val: str) -> datetime:
    try:
        return datetime.fromisoformat(val)
    except Exception:
        try:
            return datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return datetime.min


def create_notification(data: list[tuple], old_data: list[tuple]) -> list[tuple]:
    """Compare `data` and `old_data` per-node and return only new
    notifications for added/removed nodes and meaningful updates.
    - status changes (inactive/active/SOS) produce status notifications
    - location changes (lat/lon) produce location notifications
    - time-only changes produce no notification
    """
    new_notifs: list[tuple] = []

    # build latest-row lookup by node_id for both datasets
    def to_dict(rows: list[tuple]) -> dict:
        # expected row format: (time, node_id, latitude, longitude, status)
        d = {}
        for r in rows:
            node = r[1]  
            d[node] = r
        return d

    new_dict = to_dict(data)
    old_dict = to_dict(old_data)

    new_nodes = set(new_dict.keys())
    old_nodes = set(old_dict.keys())

    # Added nodes
    for node in new_nodes - old_nodes:
        n = new_row_notifications(new_dict[node])
        new_notifs.append(n)

    # Removed nodes
    for node in old_nodes - new_nodes:
        n = removed_row_notifications(old_dict[node])
        new_notifs.append(n)

    # Updated nodes (present in both) -> decide if status/location changed
    for node in new_nodes & old_nodes:
        old_row = old_dict[node]
        new_row = new_dict[node]
        n = updated_row_notifications(old_row, new_row)
        if n:
            new_notifs.append(n)

    return new_notifs

def new_row_notifications(data: tuple) -> tuple:
    # Title should describe the event; status/type goes in the third field.
    if data[4] == "SOS":
        title = f"New Node {data[1]} SOS Alert"
        # data[2] = latitude, data[3] = longitude
        message = f"Current location: {data[2]:.6f}, {data[3]:.6f}"
        n = (data[0], data[1], "SOS", title, message, 0)
    else:
        title = f"Node {data[1]} has been added"
        message = f"Current location: {data[2]:.6f}, {data[3]:.6f}"
        n = (data[0], data[1], "System", title, message, 0)
    database.add_notif(n)
    return n

def removed_row_notifications(data: tuple) -> tuple:
    title = f"Node {data[1]} has been removed"
    message = f"Last recorded location: {data[2]:.6f}, {data[3]:.6f}"
    n = (data[0], data[1], "System", title, message, 0)
    database.add_notif(n)
    return n

def updated_row_notifications(old_row: tuple, new_row: tuple) -> tuple:
    """Compare an old_row and new_row for a node and return a notification
    tuple if a meaningful change occurred; otherwise return None.
    """
    # expected row format: (time, node_id, latitude, longitude, status)
    try:
        old_status = str(old_row[4])
        new_status = str(new_row[4])
        # stored as (latitude, longitude)
        old_lat, old_lon = float(old_row[2]), float(old_row[3])
        new_lat, new_lon = float(new_row[2]), float(new_row[3])
    except Exception:
        return None

    node = new_row[1]
    # Status change has priority
    if old_status != new_status:
        if new_status == "SOS":
            title = f"Node {node} SOS Alert"
            # new_lat, new_lon computed from new_row (lat, long)
            message = f"Location: {new_lat:.6f}, {new_lon:.6f}"
            n = (new_row[0], node, "SOS", title, message, 0)
        elif new_status == "inactive":
            title = f"Node {node} Disconnected"
            message = f"Last known location: {new_lat:.6f}, {new_lon:.6f}"
            n = (new_row[0], node, "Alert", title, message, 0)
        elif new_status == "active":
            title = f"Node {node} Reconnected"
            message = f"Present location: {new_lat:.6f}, {new_lon:.6f}"
            n = (new_row[0], node, "Alert", title, message, 0)
        else:
            title = f"Node {node} Status: {new_status}"
            message = f"Location: {new_lat:.6f}, {new_lon:.6f}"
            n = (new_row[0], node, "Info", title, message, 0)
        database.add_notif(n)
        return n

    # No status change -> check location change (consider small epsilon)
    eps = 1e-6
    if abs(old_lat - new_lat) > eps or abs(old_lon - new_lon) > eps:
        title = f"Node {node} Location Update"
        message = f"Location: {new_lat:.6f}, {new_lon:.6f}"
        n = (new_row[0], node, "Info", title, message, 0)
        database.add_notif(n)
        return n

    # Only time changed or identical -> no notification
    return None


# ----------------- PyQt6 Notifications Page (UI) -----------------

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea,
    QFrame, QLabel, QComboBox, QSizePolicy, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer
from i18n import tr, notif_text
from login import User


class NotificationsPage(QWidget):
    def __init__(self, parent=None, user:User=None):
        super().__init__(parent)

        self.notifs = []  # cached notifications (only updated on refresh)
        self._raw_notifs = []  # original rows fetched from DB before view filtering
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
        title_lbl = QLabel(tr("Notifications"))
        title_lbl.setStyleSheet("font-size:16px; font-weight:700; color: #cfd8ff;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        # header_layout.addWidget(self.filter_combo)  # dropdown removed (use pills)
        header_layout.addWidget(self.my_nodes_checkbox)
        header_layout.addWidget(self.refresh_btn)
        layout.addLayout(header_layout)

        # Scrollable list container for notification 'cards'
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
        self.refresh_btn.clicked.connect(self.load_notifications)
        # The wrapper (FilteredNotificationsPage) will call `set_filter()` on this
        # page to apply filters via the pill buttons. Keep the slot for
        # compatibility but do not connect a dropdown signal here.
        self.my_nodes_checkbox.stateChanged.connect(self.on_my_nodes_toggled)

        # Filter state: None or lowercase string
        self.current_filter = None
        # default: show all nodes (unchecked). Keep state synced with checkbox
        self.my_nodes = False
        self.my_nodes_checkbox.setChecked(self.my_nodes)

    def load_notifications(self):
        """Fetch unread notifications from the DB and populate the list of cards.
        Marks all fetched notifications as read so they won't appear on next visit.
        Called on explicit Refresh and when the page is shown."""
        # ensure UI cleared immediately so message appears even on early calls
        self._clear_list()
        print("load_notifications(): called")
        # get only unread notifications (includes is_read column now)
        try:
            rows = database.get_unread_notifs()
        except Exception as e:
            print(f"load_notifications(): get_unread_notifs failed: {e}")
            rows = []

        # normalize: some DBs may return rows with 6 columns (including is_read)
        # while older schemas may return only 5; prefer the explicit unread query.
        self._raw_notifs = rows if rows else []
        print(f"load_notifications(): fetched {len(self.notifs)} unread rows")
        if self.notifs:
            try:
                print(f"load_notifications(): first row sample: {self.notifs[0]}")
            except Exception:
                pass
        # fallback: scan all notifications and pick those with is_read==0 when present
        if not self._raw_notifs:
            try:
                alln = database.get_notifs()
                fallback = []
                for r in alln:
                    if len(r) > 5:
                        try:
                            if int(r[5]) == 0:
                                fallback.append(r)
                        except Exception:
                            continue
                self._raw_notifs = fallback
                if fallback:
                    print(f"load_notifications(): fallback found {len(fallback)} unread rows")
            except Exception as e:
                print(f"load_notifications(): fallback get_notifs failed: {e}")
        # apply view filtering to the raw rows without mutating the original list
        visible = []
        for idx, r in enumerate(self._raw_notifs):
            try:
                nid = r[1]
            except Exception:
                continue
            print(f"filtering raw idx={idx} node_id={nid} type={type(nid)} viewable={self.user.viewable_nodes}")
            if nid not in self.user.viewable_nodes:
                # if SOS and the UI is not limited to 'My Nodes', show unauthorized placeholder
                if len(r) > 2 and r[2] == "SOS" and not self.my_nodes:
                    visible.append((r[0], r[1], r[2], r[3], "(UNAUTHORIZED TO VIEW LOCATION)"))
                else:
                    # skip rows the user cannot view
                    continue
            else:
                visible.append(r)

        self.notifs = visible
        # keep whatever current_filter is set by wrapper; default show all
        if self.current_filter is None:
            rows_to_show = self.notifs
        else:
            wanted = self.current_filter.lower()
            rows_to_show = [r for r in self.notifs if len(r) > 2 and str(r[2]).lower() == wanted]

        # If there are no unread notifications to show, display a message
        if not rows_to_show:
            lbl = QLabel(tr("No new notifications"))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-size:14px; color: gray; padding:20px;")
            self.scroll_layout.addWidget(lbl)
            self.scroll_layout.addStretch()
        else:
            self._populate_list(rows_to_show)

        # mark all unread notifications as read after a short delay so
        # duplicate/early calls to `load_notifications()` don't hide items
        # before the UI has a chance to render them.
        try:
            QTimer.singleShot(200, self._mark_read_delayed)
        except Exception:
            try:
                database.mark_all_notifs_read()
            except Exception:
                pass

    def _mark_read_delayed(self):
        try:
            database.mark_all_notifs_read()
        except Exception:
            pass

    def set_filter(self, tab: str | None):
        """Apply a filter by tab name (e.g. 'All','SOS','Alert',...).
        Called by an external wrapper when pill buttons are used.
        Pass `None` or 'All' to clear the filter.
        """
        if tab is None or tab == "All":
            self.current_filter = None
            rows = self.notifs
        else:
            wanted = tab.lower()
            self.current_filter = wanted
            rows = [r for r in self.notifs if len(r) > 2 and str(r[2]).lower() == wanted]

        if not rows:
            self._clear_list()
            lbl = QLabel(tr("No new notifications"))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-size:14px; color: gray; padding:20px;")
            self.scroll_layout.addWidget(lbl)
            self.scroll_layout.addStretch()
            return

        self._populate_list(rows)

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
        """Apply the dropdown filter to the cached notifications.
        Does not query the DB; only filters in-memory list.
        Options: All, Alert, System"""
        # kept for compatibility if dropdown is ever re-added; no-op otherwise
        return

    def on_my_nodes_toggled(self):
        # Toggle the local filter state and reapply filtering to the already-fetched
        # notification rows so we do NOT requery the DB (which would mark them read).
        self.my_nodes = self.my_nodes_checkbox.isChecked()
        # Recompute visible notifications from the original raw rows
        visible = []
        for idx, r in enumerate(self._raw_notifs):
            try:
                nid = r[1]
            except Exception:
                continue
            if nid not in self.user.viewable_nodes:
                if len(r) > 2 and r[2] == "SOS" and not self.my_nodes:
                    visible.append((r[0], r[1], r[2], r[3], "(UNAUTHORIZED TO VIEW LOCATION)"))
                else:
                    continue
            else:
                visible.append(r)

        self.notifs = visible
        # reapply the current category filter and update UI without touching the DB
        if self.current_filter is None:
            self._populate_list(self.notifs)
        else:
            self.set_filter(self.current_filter)

    def showEvent(self, event):
        # When the page becomes visible, load unread notifications
        try:
            self.load_notifications()
        except Exception as e:
            print(f"showEvent: load_notifications raised: {e}")
        super().showEvent(event)