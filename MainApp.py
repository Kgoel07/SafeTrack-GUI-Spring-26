import sys
import os

from PyQt6.QtGui import QIcon, QFont, QPainter, QColor, QPen
from PyQt6.QtCore import QSize, Qt, pyqtSignal, QRect, QTimer
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QFrame, QStackedLayout,
    QMessageBox
)

import database
import auth_database as adb
from login import User, LoginWindow

from map import MapDisplay
from notification import NotificationsPage
from backend_worker import BackendWorker
from alert_system import AlertSystem
from serial_monitor import Monitor
from simulating_nodes import Simulate  # for debugging only
from settings import SettingsPage
from history_log import HistoryLogPage
from nodes import NodesPage
import i18n
import preferences
import theme
from i18n import tr


# ═══════════════════════════════════════════════════════
# CUSTOM WIDGETS
# ═══════════════════════════════════════════════════════

class AvatarWidget(QWidget):
    """Circular avatar showing user initials."""
    def __init__(self, initials: str, size: int = 36, parent=None):
        super().__init__(parent)
        self.initials = initials.upper()[:2]
        self.setFixedSize(size, size)
        self._size = size

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#2563eb"))
        p.setPen(QPen(QColor("#3b82f6"), 1.5))
        p.drawEllipse(2, 2, self._size - 4, self._size - 4)
        p.setPen(QColor("#ffffff"))
        font = QFont("SF Pro Display", int(self._size * 0.32))
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        p.drawText(QRect(0, 0, self._size, self._size),
                   Qt.AlignmentFlag.AlignCenter, self.initials)
        p.end()


class BadgeWidget(QWidget):
    """Small circular badge that draws a filled circle and centered text.
    This ensures a pixel-perfect circle on all DPI settings.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._count_text = ""
        self._bg = QColor("#e06a6a")
        self._fg = QColor("#ffffff")
        self._font = QFont()
        self._font.setPointSize(9)
        self._font.setWeight(QFont.Weight.DemiBold)
        self.setVisible(False)

    def set_count(self, count: int):
        if count and count > 0:
            if count < 10:
                w = h = 18
                text = str(count)
            elif count < 100:
                w, h = 24, 18
                text = str(count)
            else:
                w, h = 30, 18
                text = '99+'
            self._count_text = text
            self.setFixedSize(w, h)
            self.setVisible(True)
        else:
            self._count_text = ""
            self.setVisible(False)
        self.update()

    def paintEvent(self, event):
        if not self.isVisible():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        # draw circle/rounded background
        p.setBrush(self._bg)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(r)
        # draw text
        p.setPen(self._fg)
        p.setFont(self._font)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self._count_text)
        p.end()


class SidebarButton(QPushButton):
    """Nav button with left accent bar when active."""
    def __init__(self, text: str, icon_path: str = "", parent=None):
        super().__init__(text, parent)
        self._active = False
        if icon_path and os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
            self.setIconSize(QSize(20, 20))
            self._theme_icon_path = icon_path   # lets theme.py tint it in light mode
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(42)
        self._update_style()
        # badge widget for counts (hidden by default)
        self._badge = BadgeWidget(self)
        self._badge.setVisible(False)

    def set_active(self, active: bool):
        self._active = active
        self._update_style()

    def _update_style(self):
        if self._active:
            self.setStyleSheet("""
                QPushButton {
                    background-color: rgba(37, 99, 235, 0.15);
                    border: none;
                    border-left: 3px solid #2563eb;
                    border-radius: 0px;
                    padding: 8px 14px;
                    text-align: left;
                    color: #ffffff;
                    font-size: 13px;
                    font-weight: 600;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    border-left: 3px solid transparent;
                    border-radius: 0px;
                    padding: 8px 14px;
                    text-align: left;
                    color: #7a8ba8;
                    font-size: 13px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.04);
                    color: #b8c5d9;
                }
            """)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # position badge near top-right inside the button
        try:
            x = self.width() - (self._badge.width() + 12)
            y = (self.height() - self._badge.height()) // 2
            self._badge.move(x, y)
        except Exception:
            pass

    def set_badge(self, count: int):
        try:
            # delegate sizing/drawing to BadgeWidget
            self._badge.set_count(count if isinstance(count, int) else 0)
            # reposition after resize
            try:
                x = self.width() - (self._badge.width() + 12)
                y = (self.height() - self._badge.height()) // 2
                self._badge.move(x, y)
            except Exception:
                pass
        except Exception:
            pass



# ═══════════════════════════════════════════════════════
# FILTERED NOTIFICATIONS PAGE
# Wraps NotificationsPage and adds category filter tabs on top
# ═══════════════════════════════════════════════════════

class FilteredPage(QWidget):
    """Adds All / SOS / Alert / Info / System filter tabs above the
    existing NotificationsPage widget from notification.py."""

    TABS = ["All", "SOS", "Alert", "Info", "System"]

    # colour per category: (active-bg hex, active-text hex, border hex)
    _TAB_COLORS = {
        "All":    ("#2563eb", "#ffffff", "#2563eb"),
        "SOS":    ("#3b0000", "#ef4444", "#ef4444"),
        "Alert":  ("#431407", "#f97316", "#f97316"),
        "Info":   ("#172554", "#60a5fa", "#60a5fa"),
        "System": ("#2e1065", "#a78bfa", "#a78bfa"),
    }

    def __init__(self, page, parent=None):
        super().__init__(parent)
        self.page = page
        self._active_tab = "All"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Tab bar ──
        tab_bar = QFrame()
        tab_bar.setFixedHeight(48)
        tab_bar.setStyleSheet("background: transparent; border: none;")
        tab_lay = QHBoxLayout(tab_bar)
        tab_lay.setContentsMargins(12, 8, 12, 4)
        tab_lay.setSpacing(8)

        self._tab_btns: dict[str, QPushButton] = {}
        for t in self.TABS:
            btn = QPushButton(tr(t))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(28)
            self._tab_btns[t] = btn
            btn.clicked.connect(lambda _, tab=t: self._set_tab(tab))
            tab_lay.addWidget(btn)
        tab_lay.addStretch()

        outer.addWidget(tab_bar)
        outer.addWidget(self.page)

        self._refresh_tab_styles()

    def _set_tab(self, tab: str):
        self._active_tab = tab
        self._refresh_tab_styles()
        # Drive the wrapped NotificationsPage via its `set_filter` API
        try:
            self.page.set_filter(tab)
        except Exception:
            # gracefully ignore if method missing
            pass

    def _refresh_tab_styles(self):
        for t, btn in self._tab_btns.items():
            active = (t == self._active_tab)
            bg, fg, border = self._TAB_COLORS.get(t, ("#1e2d44", "#64748b", "#334155"))
            if active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {bg};
                        color: {fg};
                        border: 1px solid {border};
                        border-radius: 14px;
                        padding: 3px 14px;
                        font-size: 12px;
                        font-weight: 700;
                    }}
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: #64748b;
                        border: 1px solid #334155;
                        border-radius: 14px;
                        padding: 3px 14px;
                        font-size: 12px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: rgba(255,255,255,0.04);
                        color: #94a3b8;
                    }
                """)

    def load(self):
        """Delegates to the inner page and reapplies the current filter."""
        if isinstance(self.page, NotificationsPage):
            self.page.load_notifications()
        elif isinstance(self.page, HistoryLogPage):
            self.page.load_history_logs()
        self._set_tab(self._active_tab)


# ═══════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    logout_requested = pyqtSignal()
    language_changed = pyqtSignal()   # the window must be rebuilt in the new language

    def __init__(self, user: User):
        super().__init__()
        self.setWindowTitle("SafeTrack")
        self.setMinimumSize(1200, 700)
        self.user = user
        self.prefs = preferences.load(user.username)
        # Set the language before any widget is created so every tr() call uses it
        i18n.set_language(self.prefs["language"])
        preferences.save_last_language(self.prefs["language"])

        self.port = "COM7"
        self.hrs = self.prefs["retention_hours"]
        self.monitor = Simulate(self.port, self.hrs)
        self.monitor.start()

        self.setStyleSheet("QMainWindow { background-color: #060a13; }")

        # ═════ CENTRAL WIDGET ═════
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ═══════════════════════════════════════════
        # SIDEBAR
        # ═══════════════════════════════════════════
        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #0b1120;
                border-right: 1px solid #141e30;
            }
        """)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # ── Logo ──
        logo_frame = QFrame()
        logo_frame.setFixedHeight(64)
        logo_frame.setStyleSheet("background: transparent; border: none; border-bottom: 1px solid #141e30;")
        logo_lay = QHBoxLayout(logo_frame)
        logo_lay.setContentsMargins(20, 0, 20, 0)

        logo_text = QLabel("SafeTrack")
        logo_text.setStyleSheet("""
            color: #ffffff; font-size: 17px; font-weight: 700;
            letter-spacing: 0.5px; border: none;
        """)
        logo_lay.addWidget(logo_text)
        logo_lay.addStretch()
        sidebar_layout.addWidget(logo_frame)

        # ── Section label ──
        nav_label = QLabel(tr("NAVIGATION"))
        nav_label.setStyleSheet("""
            color: #3d4f68; font-size: 10px; font-weight: 700;
            letter-spacing: 1.5px; padding: 18px 20px 8px 20px; border: none;
        """)
        sidebar_layout.addWidget(nav_label)

        # ── Nav buttons ──
        img = lambda name: os.path.join("images", name)

        self.sidebar_buttons_info = [
            ("btnMap",           "Map",           img("map_icon.png")),
            ("btnNodes",         "Nodes",         img("nodes_icon.svg")),
            ("btnNotifications", "Notifications", img("notifications_icon.png")),
            ("btnHistory",       "History && Logs",img("history_icon.png")),
            ("btnSettings",      "Settings",      img("settings_icon.png")),
        ]
        if user.is_admin:
            self.sidebar_buttons_info.append(("btnInvite", "Invite", img("invite_icon.png")))

        self.sidebar_buttons = {}
        for obj_name, label, icon_path in self.sidebar_buttons_info:
            btn = SidebarButton(f"  {tr(label)}", icon_path)
            sidebar_layout.addWidget(btn)
            self.sidebar_buttons[obj_name] = btn
            btn.clicked.connect(lambda checked, n=obj_name: self.on_sidebar_button(n))

        self.sidebar_buttons["btnMap"].set_active(True)
        self._active_btn = "btnMap"

        sidebar_layout.addStretch()

        # ── Divider ──
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background-color: #141e30; border: none;")
        sidebar_layout.addWidget(div)

        # ── Logout (separate, bottom) ──
        logout_btn = SidebarButton(f"  {tr('Logout')}", img("logout_icon.png"))
        logout_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                border-left: 3px solid transparent;
                padding: 8px 14px; text-align: left;
                color: #5a6a82; font-size: 13px; font-weight: 500;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.08);
                color: #ef4444;
            }
        """)
        logout_btn.clicked.connect(lambda: self.on_sidebar_button("btnLogout"))
        self.sidebar_buttons["btnLogout"] = logout_btn
        sidebar_layout.addWidget(logout_btn)

        # ── User profile (clickable → Settings > Account) ──
        user_frame = QFrame()
        user_frame.setFixedHeight(66)
        user_frame.setCursor(Qt.CursorShape.PointingHandCursor)
        user_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255,255,255,0.02);
                border: none; border-top: 1px solid #141e30;
            }
            QFrame:hover {
                background-color: rgba(37,99,235,0.08);
            }
        """)
        user_lay = QHBoxLayout(user_frame)
        user_lay.setContentsMargins(16, 0, 16, 0)
        user_lay.setSpacing(10)

        display_name = user.fullname if user.fullname else user.username
        parts = display_name.split()
        initials = (parts[0][0] + (parts[1][0] if len(parts) > 1 else "")) if parts else "?"
        self.avatar = AvatarWidget(initials, 36)
        user_lay.addWidget(self.avatar)

        user_text = QVBoxLayout()
        user_text.setSpacing(1)
        user_text.setContentsMargins(0, 0, 0, 0)

        self.name_lbl = QLabel(display_name)
        self.name_lbl.setStyleSheet("color: #cfd8e8; font-size: 13px; font-weight: 600; border: none;")
        role_lbl = QLabel(tr("Admin") if user.is_admin else tr("User"))
        role_lbl.setStyleSheet("color: #4a5a72; font-size: 11px; font-weight: 500; border: none;")

        user_text.addStretch()
        user_text.addWidget(self.name_lbl)
        user_text.addWidget(role_lbl)
        user_text.addStretch()
        user_lay.addLayout(user_text)
        user_lay.addStretch()
        sidebar_layout.addWidget(user_frame)

        # Make the profile strip open Settings > Account when clicked
        user_frame.mousePressEvent = lambda e: self.on_sidebar_button("btnSettings")

        root_layout.addWidget(sidebar)

        # ═══════════════════════════════════════════
        # MAIN CONTENT AREA
        # ═══════════════════════════════════════════
        main_area = QWidget()
        main_area.setStyleSheet("""
            QWidget {
                background-color: #060a13;
                color: #cfd8e8;
            }
        """)
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(0)
        root_layout.addWidget(main_area)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(0)
        main_layout.addLayout(content_layout)

        self.stacked_layout = QStackedLayout()
        content_frame = QFrame()
        content_frame.setStyleSheet("background: transparent; border: none;")
        content_frame.setLayout(self.stacked_layout)
        content_layout.addWidget(content_frame)

        self.blank_pages = {}

        # Backend worker
        self.backend = BackendWorker(user)
        self.backend.notification_signal.connect(self.handle_backend_notification)
        self.backend.start()

        # start a timer to refresh unread notification badge periodically
        self._notif_timer = QTimer(self)
        self._notif_timer.timeout.connect(self.update_notif_badge)
        self._notif_timer.start(2000)

        # ── MAP PAGE ──
        self.alert_system = AlertSystem(self, user)
        self.alert_system.viewNodeRequested.connect(self.open_node_on_map)

        self.center = (33.42057834806449, -111.9322007773111)
        self.map_widget = MapDisplay(center_coord=self.center, user=user)
        self.stacked_layout.addWidget(self.map_widget) # index 0

        # ── NOTIFICATIONS PAGE (wrapped with category filter tabs) ──
        _inner_notif = NotificationsPage(user=user)
        self.notifications_page = FilteredPage(_inner_notif)
        self.notifications_page.load()
        self.stacked_layout.addWidget(self.notifications_page)  # index 1

        # ── HISTORY PAGE (placeholder until history.py is integrated) ──
        _inner_histroy = HistoryLogPage(user=user)
        self.history_page = FilteredPage(_inner_histroy)
        self.history_page.load()
        self.stacked_layout.addWidget(self.history_page)  # index 2

        # ── SETTINGS PAGE ──
        self.settings_page = SettingsPage(user=user)
        self.settings_page.back_requested.connect(
            lambda: self.on_sidebar_button("btnMap")
        )
        self.settings_page.preferences_changed.connect(self.apply_preferences)
        self.settings_page.profile_changed.connect(self._refresh_profile)
        self.settings_page.account_deleted.connect(self._on_account_deleted)
        self.settings_page.light_mode_changed.connect(lambda on: theme.apply(self, on))
        self.settings_page.language_changed.connect(lambda _: self.language_changed.emit())
        self.stacked_layout.addWidget(self.settings_page)       # index 3
        self.blank_pages["btnSettings"] = self.settings_page

        # ── NODES PAGE (all node IDs + latest status from the DB) ──
        self.nodes_page = NodesPage(user=user)
        self.nodes_page.viewNodeRequested.connect(self.open_node_on_map)
        self.nodes_page.load_nodes()
        self.stacked_layout.addWidget(self.nodes_page)          # index 4
        self.blank_pages["btnNodes"] = self.nodes_page

        # ── BLANK PAGES (Invite, etc.) ──
        # btnMap=0, btnNotifications=1, btnHistory=2, btnSettings=3, btnNodes=4 already set
        _skip = {"btnMap", "btnNodes", "btnNotifications", "btnHistory", "btnSettings"}
        for obj_name, label, _ in self.sidebar_buttons_info:
            if obj_name in _skip:
                continue
            page = QFrame()
            page.setStyleSheet("background: transparent;")
            p_layout = QVBoxLayout(page)
            p_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            icon_lbl = QLabel("⚙")
            icon_lbl.setStyleSheet("font-size: 48px; color: #1e2d44;")
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            p_layout.addWidget(icon_lbl)

            title_lbl = QLabel(tr(label))
            title_lbl.setStyleSheet("font-size: 22px; font-weight: 600; color: #2a3a52;")
            title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            p_layout.addWidget(title_lbl)

            sub_lbl = QLabel(tr("Coming soon"))
            sub_lbl.setStyleSheet("font-size: 13px; color: #1e2d44;")
            sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            p_layout.addWidget(sub_lbl)

            self.stacked_layout.addWidget(page)
            self.blank_pages[obj_name] = page

        self.stacked_layout.setCurrentIndex(0)

        self.apply_preferences(self.prefs)
        startup = {"Nodes": "btnNodes", "History": "btnHistory"}.get(self.prefs["startup_page"])
        if startup:
            self.on_sidebar_button(startup)

    def apply_preferences(self, prefs: dict):
        """Apply App Preferences to the running window."""
        zoom_changed = (prefs["map_zoom"] != self.map_widget.zoom or
                        prefs["show_sos_radius"] != self.map_widget.show_sos_radius)
        self.prefs = prefs
        theme.apply(self, prefs["light_mode"])
        self.map_widget.zoom = prefs["map_zoom"]
        self.map_widget.show_sos_radius = prefs["show_sos_radius"]
        self.nodes_page.set_time_format(prefs["time_format_24h"])
        if zoom_changed:
            self.map_widget.update_map()

    def _refresh_profile(self):
        """Update the sidebar name/avatar after the profile is edited."""
        display_name = self.user.fullname if self.user.fullname else self.user.username
        parts = display_name.split()
        self.avatar.initials = ((parts[0][0] + (parts[1][0] if len(parts) > 1 else "")) if parts else "?").upper()
        self.avatar.update()
        self.name_lbl.setText(display_name)

    def _on_account_deleted(self):
        self.logout_requested.emit()
        self.close()

    # ─────────────────────────────────────
    # SIDEBAR NAVIGATION
    # ─────────────────────────────────────

    def _set_active(self, name: str):
        for key, btn in self.sidebar_buttons.items():
            if key == "btnLogout":
                continue
            if isinstance(btn, SidebarButton):
                btn.set_active(key == name)
        self._active_btn = name

    def on_sidebar_button(self, name):
        match name:
            case "btnMap":
                self._set_active(name)
                self.stacked_layout.setCurrentIndex(0)
                self.map_widget.update_map()
            case "btnNotifications":
                self._set_active(name)
                self.stacked_layout.setCurrentIndex(1)
                self.notifications_page.load()
                # immediately refresh badge after opening notifications (badge will clear after page marks read)
                try:
                    QTimer.singleShot(400, self.update_notif_badge)
                except Exception:
                    pass
            case "btnNodes":
                self._set_active(name)
                self.stacked_layout.setCurrentWidget(self.nodes_page)
                self.nodes_page.load_nodes()
            case "btnHistory":
                self._set_active(name)
                self.stacked_layout.setCurrentIndex(2)
                self.history_page.load()
            case "btnSettings":
                self._set_active(name)
                self.settings_page.show_section("Account")
                idx = self.stacked_layout.indexOf(self.settings_page)
                if idx != -1:
                    self.stacked_layout.setCurrentIndex(idx)
            case "btnInvite":
                self._generate_invite()
            case "btnLogout":
                if self.prefs["confirm_logout"]:
                    if not i18n.confirm(self, tr("Log out"), tr("Are you sure you want to log out?")):
                        return
                self.logout_requested.emit()
                self.close()
            case _:
                self._set_active(name)
                page_widget = self.blank_pages.get(name)
                if page_widget is not None:
                    idx = self.stacked_layout.indexOf(page_widget)
                    if idx != -1:
                        self.stacked_layout.setCurrentIndex(idx)

    def _generate_invite(self):
        if not self.user.is_admin:
            i18n.warn(self, tr("Permission Denied"), tr("Only admins can create invite codes."))
            return
        code = adb.create_invite_code(self.user.username)
        i18n.info(
            self, tr("Invite Code Generated"),
            tr("Share this code with the person you want to invite:\n\n"
               "    {code}\n\n"
               "It expires in 48 hours and can only be used once.", code=code)
        )

    # ─────────────────────────────────────
    # BACKEND / MAP HANDLERS
    # ─────────────────────────────────────

    def node_added_callback(self, node_id):
        self.map_widget.update_map()

    def handle_backend_notification(self, notif):
        if notif[2] == "SOS":
            self.alert_system.show_alert_node(notif)
        if self.stacked_layout.currentWidget() == self.map_widget:
            self.map_widget.update_map()
        # update badge immediately when backend reports a new notification
        try:
            self.update_notif_badge()
        except Exception:
            pass

    def closeEvent(self, event):
        theme.reset(self)
        if hasattr(self, "monitor"):
            self.monitor.requestInterruption()
        if hasattr(self, "backend"):
            try:
                self.backend.requestInterruption()
                self.backend.wait(2000)
            except Exception:
                pass
        super().closeEvent(event)

    def open_node_on_map(self, node_id):
        self.stacked_layout.setCurrentIndex(0)
        self._set_active("btnMap")
        self.map_widget.center_on_node(node_id)

    def update_notif_badge(self):
        try:
            rows = database.get_unread_notifs()
            count = len(rows) if rows else 0
            btn = self.sidebar_buttons.get("btnNotifications")
            if btn:
                try:
                    btn.set_badge(count)
                except Exception:
                    pass
        except Exception:
            pass


# ═══════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    database.init_db()
    database.init_notif_db()
    adb.init_auth_db()

    app = QApplication(sys.argv)
    # The login screen uses the last language picked in Settings on this computer
    i18n.set_language(preferences.load_last_language())
    login_window = LoginWindow()
    main_window = None
    _user_update_connected = False

    def start_main(user, geometry=None):
        global main_window, _user_update_connected
        main_window = MainWindow(user)
        main_window.logout_requested.connect(show_login)
        main_window.language_changed.connect(restart_main)
        if geometry is not None:
            main_window.setGeometry(geometry)
        login_window.hide()
        main_window.show()
        print(f"Logged in: {user.list_info()}")

        if _user_update_connected:
            return
        _user_update_connected = True

        # Connect the global user_update signal so the running main window
        # refreshes the current user's viewable nodes when a new node is added.
        try:
            import login as login_module

            def _on_user_update():
                try:
                    # refresh the user object (updates viewable_nodes for admins)
                    login_module.refresh_user_nodes(main_window.user)
                    # propagate the updated user to widgets that cache it
                    try:
                        main_window.map_widget.user = main_window.user
                        
                        main_window.map_widget.update_map()
                    except Exception:
                        pass
                    try:
                        main_window.alert_system.user = main_window.user
                    except Exception:
                        pass
                except Exception as exc:
                    print(f"[user_update] handler error: {exc}")

            login_module.user_signals.user_update.connect(_on_user_update)
        except Exception:
            pass

    def restart_main():
        """Rebuild the main window after the language is changed in Settings."""
        old = main_window
        start_main(old.user, old.geometry())
        old.close()
        main_window.on_sidebar_button("btnSettings")
        main_window.settings_page.show_section("App Preferences")
        QTimer.singleShot(0, lambda: i18n.info(main_window, tr("Saved"), tr("Your settings have been saved.")))

    def show_login():
        login_window.show()

    login_window.login_successful.connect(start_main)
    login_window.show()
    sys.exit(app.exec())