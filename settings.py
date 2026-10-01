# ═══════════════════════════════════════════════════════
# settings.py  –  SafeTrack Settings Page
# ═══════════════════════════════════════════════════════

import os
import re
from datetime import datetime, timezone

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QLineEdit, QScrollArea, QStackedWidget,
    QMessageBox, QComboBox, QCheckBox, QInputDialog, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor

import auth_database as adb
import auth_utils
import database
import preferences as prefs
import theme
from login import User


# ───────────────────────────────────────────────────────
# SECTION BUTTON  (left-hand tab list)
# ───────────────────────────────────────────────────────
class _SectionBtn(QPushButton):
    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self._icon  = icon
        self._label = label
        self._active = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(42)
        self._refresh()

    def set_active(self, active: bool):
        self._active = active
        self._refresh()

    def _refresh(self):
        if self._active:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    border: none; border-radius: 8px;
                    padding: 8px 14px; text-align: left;
                    color: #ffffff;
                    font-size: 13px; font-weight: 700;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none; border-radius: 8px;
                    padding: 8px 14px; text-align: left;
                    color: #64748b;
                    font-size: 13px; font-weight: 500;
                }
                QPushButton:hover {
                    background-color: rgba(255,255,255,0.04);
                    color: #94a3b8;
                }
            """)
        # "&&" so Qt shows a literal "&" instead of a mnemonic underline
        self.setText(f"  {self._icon}  {self._label.replace('&', '&&')}")


# ───────────────────────────────────────────────────────
# SHARED WIDGET HELPERS
# ───────────────────────────────────────────────────────
def _make_input(placeholder: str = "", password: bool = False) -> QLineEdit:
    w = QLineEdit()
    w.setPlaceholderText(placeholder)
    if password:
        w.setEchoMode(QLineEdit.EchoMode.Password)
    w.setFixedHeight(44)
    w.setStyleSheet("""
        QLineEdit {
            background-color: #0d1526;
            border: 1px solid #1e2d44;
            border-radius: 8px;
            padding: 0 12px;
            color: #cbd5e1;
            font-size: 13px;
        }
        QLineEdit:focus {
            border-color: #2563eb;
            background-color: #0f1a30;
        }
        QLineEdit:hover {
            border-color: #2a3a52;
        }
        QLineEdit:read-only {
            color: #64748b;
            background-color: #0b1220;
        }
    """)
    return w


def _field_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: 600;")
    return lbl


def _hint(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color: #64748b; font-size: 12px;")
    return lbl


def _button(text: str, kind: str = "primary") -> QPushButton:
    """kind: primary (blue), secondary (outline), danger (red)."""
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedHeight(38)
    styles = {
        "primary": """
            QPushButton {
                background-color: #2563eb; color: #ffffff; border: none;
                border-radius: 8px; font-size: 13px; font-weight: 700; padding: 0 18px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
            QPushButton:pressed { background-color: #1e40af; }
        """,
        "secondary": """
            QPushButton {
                background: transparent; color: #94a3b8;
                border: 1px solid #334155; border-radius: 8px;
                font-size: 13px; font-weight: 600; padding: 0 16px;
            }
            QPushButton:hover { color: #cbd5e1; border-color: #475569; }
        """,
        "danger": """
            QPushButton {
                background-color: #ef4444; color: #ffffff; border: none;
                border-radius: 8px; font-size: 13px; font-weight: 700; padding: 0 18px;
            }
            QPushButton:hover { background-color: #dc2626; }
            QPushButton:pressed { background-color: #b91c1c; }
        """,
    }
    btn.setStyleSheet(styles[kind])
    return btn


def _make_combo(options: list[tuple[str, object]], width: int = 170) -> QComboBox:
    """options = [(display text, stored value), ...]"""
    w = QComboBox()
    for text, value in options:
        w.addItem(text, value)
    w.setFixedSize(width, 36)
    w.setCursor(Qt.CursorShape.PointingHandCursor)
    w.setStyleSheet("""
        QComboBox {
            background-color: #0d1526; border: 1px solid #1e2d44;
            border-radius: 8px; padding: 0 12px; color: #cbd5e1; font-size: 13px;
        }
        QComboBox:hover { border-color: #2a3a52; }
        QComboBox:focus { border-color: #2563eb; }
        QComboBox::drop-down { border: none; width: 24px; }
        QComboBox QAbstractItemView {
            background-color: #0d1526; color: #cbd5e1;
            selection-background-color: #2563eb; border: 1px solid #1e2d44;
        }
    """)
    return w


def _set_combo_value(combo: QComboBox, value):
    idx = combo.findData(value)
    combo.setCurrentIndex(idx if idx != -1 else 0)


class _Toggle(QCheckBox):
    """Checkbox drawn as an on/off switch."""
    _W, _H = 40, 22

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self._W, self._H)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#2563eb" if on else ("#cbd5e1" if theme.is_light() else "#1e2d44")))
        p.drawRoundedRect(0, 0, self._W, self._H, self._H / 2, self._H / 2)
        knob = self._H - 6
        x = self._W - knob - 3 if on else 3
        p.setBrush(QColor("#ffffff" if on else "#64748b"))
        p.drawEllipse(x, 3, knob, knob)
        p.end()


def _divider() -> QFrame:
    div = QFrame()
    div.setFixedHeight(1)
    div.setStyleSheet("background-color: #1a2540; border: none;")
    return div


def _card() -> tuple[QFrame, QVBoxLayout]:
    """Rounded group container used by every settings panel."""
    card = QFrame()
    card.setObjectName("settingsCard")
    card.setStyleSheet("""
        QFrame#settingsCard { background-color: #0b1220; border: 1px solid #1a2540; border-radius: 10px; }
        QLabel { border: none; background: transparent; }
    """)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(16, 4, 16, 4)
    lay.setSpacing(0)
    return card, lay


def _setting_row(name: str, desc: str, control: QWidget | None = None) -> QHBoxLayout:
    """Title + description on the left, a control on the right."""
    row = QHBoxLayout()
    row.setContentsMargins(0, 12, 0, 12)
    text = QVBoxLayout()
    text.setSpacing(2)
    n = QLabel(name)
    n.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: 600;")
    text.addWidget(n)
    if desc:
        text.addWidget(_hint(desc))
    row.addLayout(text, stretch=1)
    if control is not None:
        row.addSpacing(16)
        row.addWidget(control, alignment=Qt.AlignmentFlag.AlignVCenter)
    return row


def _value_label(text: str, color: str = "#cbd5e1") -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 600;")
    lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lbl


# ───────────────────────────────────────────────────────
# PANEL BASE  (scrollable column with a title + groups)
# ───────────────────────────────────────────────────────
class _Panel(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
            QScrollBar::handle:vertical { background: #1e2d44; border-radius: 4px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: #2a3a52; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        self.form = QVBoxLayout(inner)
        self.form.setContentsMargins(0, 0, 16, 16)
        self.form.setSpacing(10)

        t = QLabel(title)
        t.setStyleSheet("color: #f1f5f9; font-size: 17px; font-weight: 700;")
        self.form.addWidget(t)
        if subtitle:
            self.form.addWidget(_hint(subtitle))
        self.form.addSpacing(6)

        scroll.setWidget(inner)
        layout.addWidget(scroll)

    def add_heading(self, text: str):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #3d4f68; font-size: 10px; font-weight: 700; "
                          "letter-spacing: 1.5px; padding-top: 8px;")
        self.form.addWidget(lbl)

    def add_group(self, heading: str, rows) -> QVBoxLayout:
        """rows = [(name, description, control), ...]; returns the card layout."""
        self.add_heading(heading)
        card, lay = _card()
        for i, (name, desc, control) in enumerate(rows):
            if i:
                lay.addWidget(_divider())
            lay.addLayout(_setting_row(name, desc, control))
        self.form.addWidget(card)
        return lay


# ───────────────────────────────────────────────────────
# ACCOUNT
# ───────────────────────────────────────────────────────
_PHONE_RE = re.compile(r"^\+?[0-9\s\-().]{7,20}$")


class _AccountPanel(_Panel):
    def __init__(self, user: User, parent=None):
        super().__init__("Account Settings", "Your profile details. Click Save Changes to update them.", parent)
        self.user = user

        self.full_name = _make_input("Enter your full name")
        self.username  = _make_input()
        self.email     = _make_input("Enter email address")
        self.phone     = _make_input("Enter phone number (optional)")

        # Pre-fill from the database (falls back to the logged-in user object)
        info = adb.get_user_by_username(user.username) or {}
        self.full_name.setText(info.get("fullname") or user.fullname or "")
        self.username.setText(user.username)
        self.username.setReadOnly(True)
        self.email.setText(info.get("email") or user.email or "")
        self.phone.setText(adb.get_phone(user.username))

        for label_text, widget, hint in [
            ("Full Name",    self.full_name, ""),
            ("Username",     self.username,  "Usernames can't be changed."),
            ("Email",        self.email,     "Used to recover your account if you forget your password."),
            ("Phone Number", self.phone,     ""),
        ]:
            self.form.addWidget(_field_label(label_text))
            self.form.addWidget(widget)
            if hint:
                self.form.addWidget(_hint(hint))
            self.form.addSpacing(4)
        self.form.addStretch()

    def save(self) -> tuple[bool, str]:
        fullname = self.full_name.text().strip()
        email = self.email.text().strip()
        phone = self.phone.text().strip()

        ok, msg = auth_utils.validate_fullname(fullname)
        if not ok:
            return False, msg
        ok, msg = auth_utils.validate_email(email)
        if not ok:
            return False, msg
        owner = adb.find_username_by_email(email)
        if owner and owner.lower() != self.user.username.lower():
            return False, "That email is already used by another account."
        if phone and not _PHONE_RE.match(phone):
            return False, "Enter a valid phone number (digits, spaces, +, - and brackets only)."

        if not adb.update_profile(self.user.username, fullname, email, phone):
            return False, "Could not update your profile."
        self.user.fullname = fullname
        self.user.email = email
        return True, ""


# ───────────────────────────────────────────────────────
# PRIVACY & SECURITY
# ───────────────────────────────────────────────────────
class _PrivacyPanel(_Panel):
    account_deleted = pyqtSignal()

    def __init__(self, user: User, parent=None):
        super().__init__("Privacy & Security", "Manage your password and who can see node locations.", parent)
        self.user = user

        # ── Access level ──
        self.role_lbl = _value_label("Admin" if user.is_admin else "User",
                                     "#60a5fa" if user.is_admin else "#cbd5e1")
        self.nodes_lbl = _value_label("")
        self.add_group("YOUR ACCESS", [
            ("Role", "Admins can see every node's location and invite other admins.", self.role_lbl),
            ("Node locations you can view", "Locations of other nodes are hidden from you.", self.nodes_lbl),
        ])
        self.refresh_access()

        # ── Change password ──
        self.add_heading("PASSWORD")
        card, lay = _card()
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(8)
        self.current_pw = _make_input("Current password", password=True)
        self.new_pw     = _make_input("New password", password=True)
        self.confirm_pw = _make_input("Confirm new password", password=True)
        for w in (self.current_pw, self.new_pw, self.confirm_pw):
            lay.addWidget(w)
        lay.addWidget(_hint("8–12 characters. Must not contain your username or the app name, "
                            "and can't be a common password."))
        self.pw_status = QLabel("")
        self.pw_status.setWordWrap(True)
        self.pw_status.hide()
        lay.addWidget(self.pw_status)
        pw_row = QHBoxLayout()
        pw_btn = _button("Update Password")
        pw_btn.clicked.connect(self._change_password)
        pw_row.addWidget(pw_btn)
        pw_row.addStretch()
        lay.addSpacing(4)
        lay.addLayout(pw_row)
        self.form.addWidget(card)

        # ── Admin invite codes ──
        if user.is_admin:
            self.add_heading("ADMIN INVITE CODES")
            card, self.invite_lay = _card()
            gen_btn = _button("Generate Code", "secondary")
            gen_btn.clicked.connect(self._generate_invite)
            self.invite_lay.addLayout(_setting_row(
                "Invite another admin",
                "Codes can be used once and expire after 48 hours.", gen_btn))
            self.invite_list = QVBoxLayout()
            self.invite_list.setSpacing(0)
            self.invite_lay.addLayout(self.invite_list)
            self.form.addWidget(card)
            self._load_invites()

        # ── Delete account ──
        del_btn = _button("Delete Account", "danger")
        del_btn.clicked.connect(self._delete_account)
        self.add_group("DANGER ZONE", [
            ("Delete account", "Permanently removes your account and emergency contacts. "
                               "This can't be undone.", del_btn),
        ])
        self.form.addStretch()

    def refresh_access(self):
        if self.user.is_admin:
            self.nodes_lbl.setText("All nodes")
        else:
            n = len(self.user.viewable_nodes)
            self.nodes_lbl.setText(f"{n} node{'s' if n != 1 else ''}")

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_access()
        if self.user.is_admin:
            self._load_invites()   # codes may also be created from the sidebar

    def _show_pw_status(self, ok: bool, text: str):
        self.pw_status.setText(text)
        self.pw_status.setStyleSheet(f"color: {'#22c55e' if ok else '#ef4444'}; font-size: 12px;")
        self.pw_status.show()

    def _change_password(self):
        current, new, confirm = self.current_pw.text(), self.new_pw.text(), self.confirm_pw.text()
        if not current or not new:
            self._show_pw_status(False, "Fill in your current and new password.")
            return
        if adb.authenticate_user(self.user.username, current) is None:
            self._show_pw_status(False, "Your current password is incorrect.")
            return
        if new != confirm:
            self._show_pw_status(False, "New passwords do not match.")
            return
        if new == current:
            self._show_pw_status(False, "New password must be different from your current one.")
            return
        ok, msg = auth_utils.validate_password(new, self.user.username)
        if not ok:
            self._show_pw_status(False, msg)
            return
        if not adb.update_password(self.user.username, new):
            self._show_pw_status(False, "Could not update your password.")
            return
        for w in (self.current_pw, self.new_pw, self.confirm_pw):
            w.clear()
        self._show_pw_status(True, "Password updated.")

    def _generate_invite(self):
        code = adb.create_invite_code(self.user.username)
        QApplication.clipboard().setText(code)
        self._load_invites()
        QMessageBox.information(self, "Invite Code Generated",
                                f"Invite code: {code}\n\nIt has been copied to your clipboard.")

    def _load_invites(self):
        while self.invite_list.count():
            item = self.invite_list.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        now = datetime.now(timezone.utc)
        for inv in adb.list_invite_codes(self.user.username)[:8]:
            if inv["used"]:
                status, color = f"Used by {inv['used_by']}", "#64748b"
            elif datetime.fromisoformat(inv["expires_at"]) < now:
                status, color = "Expired", "#64748b"
            else:
                expires = datetime.fromisoformat(inv["expires_at"]).astimezone()
                status, color = f"Active · expires {expires:%b %d, %H:%M}", "#22c55e"
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 8, 0, 8)
            code = _value_label(inv["code"])
            code.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: 700; "
                               "font-family: Menlo, Consolas, monospace;")
            st = QLabel(status)
            st.setStyleSheet(f"color: {color}; font-size: 12px;")
            rl.addWidget(code)
            rl.addStretch()
            rl.addWidget(st)
            self.invite_list.addWidget(_divider())
            self.invite_list.addWidget(row)

    def _delete_account(self):
        resp = QMessageBox.warning(
            self, "Delete Account",
            "Are you sure you want to delete your account?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        pw, ok = QInputDialog.getText(self, "Confirm Password",
                                      "Enter your password to delete your account:",
                                      QLineEdit.EchoMode.Password)
        if not ok:
            return
        if adb.authenticate_user(self.user.username, pw) is None:
            QMessageBox.warning(self, "Incorrect Password", "That password is incorrect.")
            return
        if adb.remove_user(self.user.username):
            prefs.clear(self.user.username)
            QMessageBox.information(self, "Account Deleted", "Your account has been deleted.")
            self.account_deleted.emit()
        else:
            QMessageBox.warning(self, "Error", "Could not delete your account.")


# ───────────────────────────────────────────────────────
# APP PREFERENCES
# ───────────────────────────────────────────────────────
class _PreferencesPanel(_Panel):
    """App Preferences: appearance, general, map and data options."""

    light_mode_changed = pyqtSignal(bool)

    def __init__(self, user: User, parent=None):
        super().__init__("App Preferences", "Click Save Changes to apply.", parent)
        self.user = user

        self.light_mode = _Toggle()
        self.add_group("APPEARANCE", [
            ("Light mode", "Use a light colour scheme. Applies instantly.", self.light_mode),
        ])

        self.startup_page = _make_combo([("Map", "Map"), ("Nodes", "Nodes"),
                                         ("History & Logs", "History")])
        self.time_format = _make_combo([("24-hour (14:30)", True), ("12-hour (2:30 PM)", False)])
        self.confirm_logout = _Toggle()

        self.map_zoom = _make_combo([("City (12)", 12), ("District (13)", 13),
                                     ("Neighborhood (14)", 14), ("Street (15)", 15),
                                     ("Building (16)", 16)])
        self.show_sos_radius = _Toggle()

        self.retention = _make_combo([("24 hours", 24), ("48 hours", 48),
                                      ("72 hours", 72), ("7 days", 168)])

        self.add_group("GENERAL", [
            ("Start-up page", "Page shown after you log in.", self.startup_page),
            ("Time format", "How timestamps appear on the Nodes page.", self.time_format),
            ("Confirm before logout", "Ask for confirmation when logging out.", self.confirm_logout),
        ])
        self.add_group("MAP", [
            ("Default zoom level", "Zoom used when the map loads or refreshes.", self.map_zoom),
            ("Highlight SOS area", "Draw a red radius around nodes in SOS.", self.show_sos_radius),
        ])
        self.add_group("DATA", [
            ("Keep node history for", "Older location and alert data is removed. "
                                      "Applies the next time you log in.", self.retention),
        ])

        reset_btn = _button("Restore Defaults", "secondary")
        reset_btn.clicked.connect(self._restore_defaults)
        reset_row = QHBoxLayout()
        reset_row.addWidget(reset_btn)
        reset_row.addStretch()
        self.form.addSpacing(6)
        self.form.addLayout(reset_row)
        self.form.addStretch()

        self.set_values(prefs.load(user.username))
        self.light_mode.toggled.connect(self._on_light_mode)

    def _on_light_mode(self, on: bool):
        # Theme changes are saved and applied immediately (no Save Changes needed)
        prefs.save(self.user.username, {"light_mode": on})
        self.light_mode_changed.emit(on)

    def set_values(self, p: dict):
        self.light_mode.setChecked(p["light_mode"])
        _set_combo_value(self.startup_page, p["startup_page"])
        _set_combo_value(self.time_format, p["time_format_24h"])
        self.confirm_logout.setChecked(p["confirm_logout"])
        _set_combo_value(self.map_zoom, p["map_zoom"])
        self.show_sos_radius.setChecked(p["show_sos_radius"])
        _set_combo_value(self.retention, p["retention_hours"])

    def values(self) -> dict:
        return {
            "light_mode":      self.light_mode.isChecked(),
            "startup_page":    self.startup_page.currentData(),
            "time_format_24h": self.time_format.currentData(),
            "confirm_logout":  self.confirm_logout.isChecked(),
            "map_zoom":        self.map_zoom.currentData(),
            "show_sos_radius": self.show_sos_radius.isChecked(),
            "retention_hours": self.retention.currentData(),
        }

    def _restore_defaults(self):
        self.set_values({k: default for k, (default, _) in prefs.DEFAULTS.items()})


# ───────────────────────────────────────────────────────
# EMERGENCY CONTACTS
# ───────────────────────────────────────────────────────
class _ContactsPanel(_Panel):
    MAX_CONTACTS = 5
    _RELATIONSHIPS = ["Parent", "Spouse / Partner", "Sibling", "Friend", "Roommate", "Other"]

    def __init__(self, user: User, parent=None):
        super().__init__("Emergency Contacts",
                         "People to reach if you're in an emergency. Saved (encrypted) "
                         "as soon as you add them.", parent)
        self.user = user

        # ── Saved contacts ──
        self.add_heading("YOUR CONTACTS")
        card, self.list_lay = _card()
        self.form.addWidget(card)

        # ── Add a contact ──
        self.add_heading("ADD A CONTACT")
        card, lay = _card()
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(8)
        self.name_in = _make_input("Full name")
        self.phone_in = _make_input("Phone number")
        self.rel_in = _make_combo([(r, r) for r in self._RELATIONSHIPS], width=200)
        self.rel_in.setFixedHeight(44)
        for label, w in (("Name", self.name_in), ("Phone", self.phone_in), ("Relationship", self.rel_in)):
            lay.addWidget(_field_label(label))
            lay.addWidget(w)
        self.add_status = QLabel("")
        self.add_status.setStyleSheet("color: #ef4444; font-size: 12px;")
        self.add_status.hide()
        lay.addWidget(self.add_status)
        self.add_btn = _button("Add Contact")
        self.add_btn.clicked.connect(self._add_contact)
        row = QHBoxLayout()
        row.addWidget(self.add_btn)
        row.addStretch()
        lay.addSpacing(4)
        lay.addLayout(row)
        self.form.addWidget(card)
        self.form.addStretch()

        self._load()

    def _load(self):
        while self.list_lay.count():
            item = self.list_lay.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        contacts = adb.list_emergency_contacts(self.user.username)
        if not contacts:
            empty = QLabel("No emergency contacts yet.")
            empty.setStyleSheet("color: #64748b; font-size: 13px; padding: 14px 0;")
            self.list_lay.addWidget(empty)
        for i, c in enumerate(contacts):
            if i:
                self.list_lay.addWidget(_divider())
            remove_btn = _button("Remove", "secondary")
            remove_btn.setFixedHeight(32)
            remove_btn.clicked.connect(lambda _, cid=c["id"], n=c["name"]: self._remove(cid, n))
            detail = " · ".join(x for x in (c["relationship"], c["phone"]) if x)
            self.list_lay.addLayout(_setting_row(c["name"], detail, remove_btn))

        full = len(contacts) >= self.MAX_CONTACTS
        self.add_btn.setEnabled(not full)
        self.add_btn.setText(f"Limit of {self.MAX_CONTACTS} reached" if full else "Add Contact")

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
            elif item.layout():
                _ContactsPanel._clear_layout(item.layout())

    def _add_contact(self):
        name = self.name_in.text().strip()
        phone = self.phone_in.text().strip()
        ok, msg = auth_utils.validate_fullname(name)
        if not ok:
            msg = msg.replace("Full name", "Name")
        elif not _PHONE_RE.match(phone):
            ok, msg = False, "Enter a valid phone number."
        if not ok:
            self.add_status.setText(msg)
            self.add_status.show()
            return
        self.add_status.hide()
        if adb.add_emergency_contact(self.user.username, name, phone, self.rel_in.currentData()):
            self.name_in.clear()
            self.phone_in.clear()
            self.rel_in.setCurrentIndex(0)
            self._load()

    def _remove(self, contact_id: int, name: str):
        resp = QMessageBox.question(self, "Remove Contact", f"Remove {name} from your emergency contacts?")
        if resp == QMessageBox.StandardButton.Yes:
            adb.remove_emergency_contact(self.user.username, contact_id)
            self._load()


# ───────────────────────────────────────────────────────
# ABOUT & HELP
# ───────────────────────────────────────────────────────
class _AboutPanel(_Panel):
    VERSION = "Spring 2026"

    def __init__(self, user: User, parent=None):
        super().__init__("About & Help", "", parent)
        self.user = user

        self.add_group("ABOUT", [
            ("SafeTrack", "Tracks the location and status of SafeTrack nodes and alerts you "
                          "the moment a node sends an SOS.", _value_label(self.VERSION, "#64748b")),
            ("Signed in as", "", _value_label(
                f"{user.username} ({'Admin' if user.is_admin else 'User'})")),
        ])

        # ── Status legend ──
        self.add_heading("NODE STATUS")
        card, lay = _card()
        for i, (name, color, meaning) in enumerate([
            ("SOS",      "#ef4444", "The node has sent an emergency alert. Shown in red on the map."),
            ("Active",   "#22c55e", "The node is on and reporting its location normally."),
            ("Inactive", "#94a3b8", "The node has stopped reporting."),
        ]):
            if i:
                lay.addWidget(_divider())
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 16px;")
            row = _setting_row(name, meaning)
            row.insertWidget(0, dot, alignment=Qt.AlignmentFlag.AlignTop)
            row.insertSpacing(1, 10)
            lay.addLayout(row)
        self.form.addWidget(card)

        # ── Quick guide ──
        self.add_group("QUICK GUIDE", [
            ("Map", "Live positions of the nodes you can view. Click Refresh to redraw.", None),
            ("Nodes", "Every node in the database with its latest status. Use View on Map to jump to one.", None),
            ("Notifications", "New alerts since you last looked. The sidebar badge shows how many are unread.", None),
            ("History & Logs", "Every alert that has been recorded, filterable by type.", None),
        ])

        # ── Troubleshooting ──
        self.add_group("TROUBLESHOOTING", [
            ("Locations say “Unauthorized”", "Only admins can see every node. Ask an admin for an "
                                             "invite code, then use “Have an admin invite code?” on the login screen.", None),
            ("No nodes are showing up", "Check that the SafeTrack receiver is plugged into this computer.", None),
            ("The map is blank", "Offline map tiles are loaded from the tiles folder next to the app. "
                                 "Run download_map.py to download them again.", None),
            ("Forgot your password", "Log out and use “forgot password?” on the login screen.", None),
        ])

        # ── System info ──
        self.db_lbl = _value_label("", "#64748b")
        self.nodes_lbl = _value_label("")
        self.alerts_lbl = _value_label("")
        self.add_group("SYSTEM", [
            ("Database", "", self.db_lbl),
            ("Nodes stored", "", self.nodes_lbl),
            ("Alerts stored", "", self.alerts_lbl),
        ])
        self.form.addStretch()

    def showEvent(self, event):
        super().showEvent(event)
        self.db_lbl.setText(os.path.abspath("nodes.db"))
        try:
            self.nodes_lbl.setText(str(len(database.get_nodes())))
            self.alerts_lbl.setText(str(len(database.get_notifs())))
        except Exception:
            self.nodes_lbl.setText("—")
            self.alerts_lbl.setText("—")


# ───────────────────────────────────────────────────────
# MAIN SETTINGS PAGE
# ───────────────────────────────────────────────────────
class SettingsPage(QWidget):
    """Full settings page with left tab list and right content panel."""

    back_requested = pyqtSignal()            # emitted when user clicks ← Back
    preferences_changed = pyqtSignal(dict)   # emitted after App Preferences are saved
    profile_changed = pyqtSignal()           # emitted after the account profile is saved
    account_deleted = pyqtSignal()           # emitted after the user deletes their account
    light_mode_changed = pyqtSignal(bool)    # emitted when the Light mode switch is flipped

    _SECTIONS = [
        ("👤", "Account"),
        ("🔒", "Privacy & Security"),
        ("⚙️", "App Preferences"),
        ("📞", "Emergency Contacts"),
        ("ℹ️", "About & Help"),
    ]

    def __init__(self, user: User, parent=None):
        super().__init__(parent)
        self.user = user
        self.setStyleSheet("background: #060a13;")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(20)

        # ── Top bar ──
        top = QHBoxLayout()
        top.setSpacing(16)

        back_btn = QPushButton("← Back")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setFixedHeight(34)
        back_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 7px;
                font-size: 13px; font-weight: 600;
                padding: 0 14px;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.04);
                color: #cbd5e1;
            }
        """)
        back_btn.clicked.connect(self.back_requested.emit)

        page_title = QLabel("Settings")
        page_title.setStyleSheet(
            "color: #f1f5f9; font-size: 24px; font-weight: 800; letter-spacing: -0.5px;"
        )

        self.save_btn = QPushButton("💾  Save Changes")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setFixedHeight(36)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #22c55e;
                color: #ffffff; border: none;
                border-radius: 8px;
                font-size: 13px; font-weight: 700;
                padding: 0 18px;
            }
            QPushButton:hover { background-color: #16a34a; }
            QPushButton:pressed { background-color: #15803d; }
        """)
        self.save_btn.clicked.connect(self._save_changes)

        top.addWidget(back_btn)
        top.addWidget(page_title)
        top.addStretch()
        top.addWidget(self.save_btn)
        root.addLayout(top)

        # ── Body (left nav + right content) ──
        body = QHBoxLayout()
        body.setSpacing(16)

        # Left nav panel
        nav_frame = QFrame()
        nav_frame.setFixedWidth(220)
        nav_frame.setStyleSheet("""
            QFrame {
                background-color: #0f172b;
                border: 1px solid #1a2540;
                border-radius: 12px;
            }
        """)
        nav_lay = QVBoxLayout(nav_frame)
        nav_lay.setContentsMargins(8, 10, 8, 10)
        nav_lay.setSpacing(2)

        self._section_btns: dict[str, _SectionBtn] = {}
        for icon, label in self._SECTIONS:
            btn = _SectionBtn(icon, label)
            btn.clicked.connect(lambda _, lbl=label: self.show_section(lbl))
            nav_lay.addWidget(btn)
            self._section_btns[label] = btn
        nav_lay.addStretch()

        # Right content panel
        content_frame = QFrame()
        content_frame.setStyleSheet("""
            QFrame {
                background-color: #0f172b;
                border: 1px solid #1a2540;
                border-radius: 12px;
            }
        """)
        content_lay = QVBoxLayout(content_frame)
        content_lay.setContentsMargins(24, 20, 24, 20)
        content_lay.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent; border: none;")

        panel_types = {
            "Account":            _AccountPanel,
            "Privacy & Security": _PrivacyPanel,
            "App Preferences":    _PreferencesPanel,
            "Emergency Contacts": _ContactsPanel,
            "About & Help":       _AboutPanel,
        }
        self._panels: dict[str, QWidget] = {}
        for icon, label in self._SECTIONS:
            panel = panel_types[label](user)
            self._stack.addWidget(panel)
            self._panels[label] = panel
        self._panels["Privacy & Security"].account_deleted.connect(self.account_deleted.emit)
        self._panels["App Preferences"].light_mode_changed.connect(self.light_mode_changed.emit)

        content_lay.addWidget(self._stack)

        body.addWidget(nav_frame)
        body.addWidget(content_frame, stretch=1)
        root.addLayout(body, stretch=1)

        # Default to Account tab
        self.show_section("Account")

    def show_section(self, label: str):
        """Switch to a named section tab."""
        for lbl, btn in self._section_btns.items():
            btn.set_active(lbl == label)
        panel = self._panels.get(label)
        if panel:
            self._stack.setCurrentWidget(panel)
        # Only Account and App Preferences use the Save button
        self.save_btn.setVisible(label in ("Account", "App Preferences"))

    def _save_changes(self):
        ok, msg = self._panels["Account"].save()
        if not ok:
            self.show_section("Account")
            QMessageBox.warning(self, "Couldn't Save", msg)
            return
        self.profile_changed.emit()

        values = self._panels["App Preferences"].values()
        prefs.save(self.user.username, values)
        self.preferences_changed.emit(values)
        QMessageBox.information(self, "Saved", "Your settings have been saved.")
