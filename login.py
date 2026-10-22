"""
login.py
────────
Multi-page authentication window for SafeTrack.

Pages (managed via QStackedWidget):
  0 – Login
  1 – Sign Up
  2 – Forgot Password  (enter email → generates reset token)
  3 – Reset Password   (enter token + new password)
  4 – Admin Invite     (enter invite code → become admin)

The User class lives here so every module can import it from one place.
Passwords are NEVER stored on the User object — auth goes through
auth_database exclusively.
"""

import smtplib
from email.mime.text import MIMEText

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QStackedWidget,
    QMessageBox, QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import (
    QKeySequence, QColor, QPainter, QLinearGradient, QBrush
)

import auth_database as adb
import i18n
from i18n import tr
from auth_utils import (
    validate_username, validate_password,
    validate_email, validate_fullname,
)

# ─── Optional SMTP settings for real email ──────────────────────────
SMTP_HOST = ""
SMTP_PORT = 587
SMTP_USER = ""
SMTP_PASS = ""
FROM_ADDR = ""


# ════════════════════════════════════════════════════════════════
# USER CLASS  (session object – no password stored)
# ════════════════════════════════════════════════════════════════

class User:
    """Lightweight user object passed around after login.
    Password is NEVER stored here."""

    def __init__(self, username: str, is_admin: int = 0,
                 email: str = "", fullname: str = "",
                 viewable_nodes: list | None = None):
        self.username = username
        self.is_admin = is_admin
        self.email = email
        self.fullname = fullname
        self.viewable_nodes = viewable_nodes if viewable_nodes is not None else []

    def list_info(self):
        return (self.username, self.is_admin, self.email,
                self.fullname, str(self.viewable_nodes))


# Module-level signals used by other parts of the app (e.g. database)
class UserSignals(QObject):
    user_update = pyqtSignal()


user_signals = UserSignals()


def refresh_user_nodes(user: User):
    """Refresh `viewable_nodes` on a User object (if admin).
    This is intended to be called when a new node is added so an admin
    user's available nodes are updated.
    """
    if user is None:
        return
    # only admins should get the full nodes list
    if getattr(user, "is_admin", 0):
        import database
        try:
            user.viewable_nodes = database.get_nodes()
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════
# GRADIENT BACKGROUND WIDGET
# ════════════════════════════════════════════════════════════════

class _GradientBG(QWidget):
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0.0, QColor("#070b14"))
        g.setColorAt(0.5, QColor("#0a1628"))
        g.setColorAt(1.0, QColor("#0e1e36"))
        p.fillRect(self.rect(), QBrush(g))
        p.end()


# ════════════════════════════════════════════════════════════════
# SHARED STYLESHEET
# ════════════════════════════════════════════════════════════════

_STYLES = """
QWidget {
    background: transparent;
    color: #e6edf3;
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 14px;
}
QFrame#card {
    background: transparent;
    border: none;
}
QLabel#logo {
    font-size: 56px; font-weight: 800;
    color: #ffffff;
    font-family: "Segoe UI", "Arial", sans-serif;
    padding: 6px 0;
}
QLabel#heading {
    font-size: 17px; font-weight: 600;
    color: #ffffff; letter-spacing: 3px;
    font-family: "Segoe UI", "Arial", sans-serif;
}
QLabel#errorLabel {
    color: #ff6b6b; font-size: 12px;
    padding: 0; margin: 0;
}
QLabel#successLabel {
    color: #6bffa1; font-size: 12px;
    padding: 0; margin: 0;
}
QLabel#hintLabel {
    color: #ff6b6b; font-size: 11px;
    padding: 0 20px; margin: 0;
}
QLabel#hintOk {
    color: #6bffa1; font-size: 11px;
    padding: 0 20px; margin: 0;
}
QLineEdit {
    background-color: #0d1526;
    border: 1px solid #1e2d44; border-radius: 12px;
    padding: 12px 16px; font-size: 14px;
    color: #cfd8e8;
}
QLineEdit:focus {
    border: 2px solid #2563eb;
}
QLineEdit[validationState="invalid"] {
    border: 2px solid #ff6b6b;
}
QLineEdit[validationState="valid"] {
    border: 2px solid #6bffa1;
}
QPushButton#primary {
    background-color: #2563eb;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 24px; padding: 14px;
    font-size: 15px; font-weight: 600;
    color: white; letter-spacing: 1px;
}
QPushButton#primary:hover { background-color: #1d4ed8; }
QPushButton#primary:pressed { background-color: #153eab; }
QPushButton#link {
    background: transparent; border: none;
    color: #d4cfee; font-size: 13px; padding: 0;
}
QPushButton#link:hover { color: #ffffff; }
QPushButton#linkBold {
    background: transparent; border: none;
    color: #ffffff; font-size: 13px;
    font-weight: 600; text-decoration: underline; padding: 0;
}
QPushButton#linkBold:hover { color: #e0d4ff; }
QLabel#dimLabel { color: #d4cfee; font-size: 13px; }
QMessageBox { background-color: #3b3557; }
QMessageBox QLabel { color: #ffffff; }
QMessageBox QPushButton {
    background-color: #7c6fbf; border: none;
    border-radius: 8px; padding: 8px 20px;
    color: white; font-weight: 600;
}
"""


# ════════════════════════════════════════════════════════════════
# REUSABLE UI HELPERS
# ════════════════════════════════════════════════════════════════

def _logo() -> QLabel:
    lbl = QLabel("safetrack")
    lbl.setObjectName("logo")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(20)
    shadow.setColor(QColor(255, 255, 255, 120))
    shadow.setOffset(0, 0)
    lbl.setGraphicsEffect(shadow)
    return lbl


def _heading(text: str) -> QLabel:
    lbl = QLabel(tr(text))
    lbl.setObjectName("heading")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl


def _error_label() -> QLabel:
    lbl = QLabel("")
    lbl.setObjectName("errorLabel")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setWordWrap(True)
    return lbl


def _success_label() -> QLabel:
    lbl = QLabel("")
    lbl.setObjectName("successLabel")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setWordWrap(True)
    return lbl


def _hint_label() -> QLabel:
    """Small red hint label placed directly below an input field."""
    lbl = QLabel("")
    lbl.setObjectName("hintLabel")
    lbl.setWordWrap(True)
    lbl.setMaximumHeight(0)  # hidden by default
    return lbl


def _set_hint(label: QLabel, text: str, ok: bool = False):
    """Update a hint label — show red text if invalid, green if valid, hide if empty."""
    if not text:
        label.setText("")
        label.setMaximumHeight(0)
    else:
        label.setText(tr(text))
        label.setObjectName("hintOk" if ok else "hintLabel")
        # Force stylesheet re-evaluation after objectName change
        label.setStyleSheet(label.styleSheet())
        label.style().unpolish(label)
        label.style().polish(label)
        label.setMaximumHeight(60)


def _set_field_state(field: QLineEdit, state: str):
    """Set the validation state property on a QLineEdit for CSS styling.
    state: 'valid', 'invalid', or '' (neutral)."""
    field.setProperty("validationState", state)
    field.style().unpolish(field)
    field.style().polish(field)


def _input(placeholder: str, password: bool = False) -> QLineEdit:
    le = QLineEdit()
    le.setPlaceholderText(tr(placeholder))
    le.setFixedHeight(48)
    if password:
        le.setEchoMode(QLineEdit.EchoMode.Password)
    return le


def _primary_btn(text: str) -> QPushButton:
    btn = QPushButton(tr(text))
    btn.setObjectName("primary")
    btn.setFixedHeight(50)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def _link_btn(text: str, bold: bool = False) -> QPushButton:
    btn = QPushButton(tr(text))
    btn.setObjectName("linkBold" if bold else "link")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def _card(max_w: int = 480) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("card")
    card.setFixedWidth(max_w)
    lay = QVBoxLayout(card)
    lay.setSpacing(10)
    lay.setContentsMargins(50, 30, 50, 30)
    return card, lay


def _send_reset_email(to_addr: str, token: str) -> bool:
    if not SMTP_HOST or not SMTP_USER:
        return False
    try:
        body = (
            f"Your SafeTrack password-reset code:\n\n"
            f"    {token}\n\n"
            f"This code expires in 1 hour.\n"
            f"If you did not request this, ignore this email."
        )
        msg = MIMEText(body)
        msg["Subject"] = "SafeTrack – Password Reset"
        msg["From"] = FROM_ADDR or SMTP_USER
        msg["To"] = to_addr
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as srv:
            srv.starttls()
            srv.login(SMTP_USER, SMTP_PASS)
            srv.send_message(msg)
        return True
    except Exception as exc:
        print(f"[email] send failed: {exc}")
        return False


# ════════════════════════════════════════════════════════════════
# PAGE 0 – LOGIN
# ════════════════════════════════════════════════════════════════

class _LoginPage(QWidget):
    login_success = pyqtSignal(User)
    go_signup = pyqtSignal()
    go_forgot = pyqtSignal()
    go_invite = pyqtSignal()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card, lay = _card()

        lay.addWidget(_logo())
        lay.addSpacing(4)
        lay.addWidget(_heading("LOG IN"))
        lay.addSpacing(10)

        self.err = _error_label()
        lay.addWidget(self.err)

        self.f_user = _input("username")
        lay.addWidget(self.f_user)

        # ── inline hint for username ──
        self.h_user = _hint_label()
        lay.addWidget(self.h_user)

        lay.addSpacing(4)

        self.f_pass = _input("password", password=True)
        lay.addWidget(self.f_pass)

        # ── inline hint for password ──
        self.h_pass = _hint_label()
        lay.addWidget(self.h_pass)

        # forgot password
        row_forgot = QHBoxLayout()
        row_forgot.addStretch()
        forgot = _link_btn("forgot password?")
        forgot.clicked.connect(self.go_forgot.emit)
        row_forgot.addWidget(forgot)
        lay.addLayout(row_forgot)

        lay.addSpacing(8)

        login_btn = _primary_btn("Log In")
        login_btn.setShortcut(QKeySequence("Return"))
        login_btn.clicked.connect(self._handle)
        lay.addWidget(login_btn)

        lay.addSpacing(6)

        # signup row
        row_su = QHBoxLayout()
        row_su.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(tr("Don't have an account?"))
        lbl.setObjectName("dimLabel")
        su_btn = _link_btn("Sign up!", bold=True)
        su_btn.clicked.connect(self.go_signup.emit)
        row_su.addWidget(lbl)
        row_su.addWidget(su_btn)
        lay.addLayout(row_su)

        # admin invite link
        row_inv = QHBoxLayout()
        row_inv.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inv_btn = _link_btn("Have an admin invite code?")
        inv_btn.clicked.connect(self.go_invite.emit)
        row_inv.addWidget(inv_btn)
        lay.addLayout(row_inv)

        outer.addWidget(card)

    def _handle(self):
        self.err.setText("")
        _set_hint(self.h_user, "")
        _set_hint(self.h_pass, "")
        _set_field_state(self.f_user, "")
        _set_field_state(self.f_pass, "")

        username = self.f_user.text().strip()
        password = self.f_pass.text()

        has_error = False

        if not username:
            _set_hint(self.h_user, "Please enter a username.")
            _set_field_state(self.f_user, "invalid")
            has_error = True
        if not password:
            _set_hint(self.h_pass, "Please enter your password.")
            _set_field_state(self.f_pass, "invalid")
            has_error = True

        if has_error:
            return

        result = adb.authenticate_user(username, password)
        if result is None:
            _set_hint(self.h_user, "Invalid username or password.")
            _set_hint(self.h_pass, "Invalid username or password.")
            _set_field_state(self.f_user, "invalid")
            _set_field_state(self.f_pass, "invalid")
            return

        import database
        viewable = database.get_nodes() if result["is_admin"] else []

        user = User(
            username=result["username"],
            is_admin=result["is_admin"],
            email=result["email"],
            fullname=result["fullname"],
            viewable_nodes=viewable,
        )
        self.login_success.emit(user)


# ════════════════════════════════════════════════════════════════
# PAGE 1 – SIGN UP  (with real-time inline validation)
# ════════════════════════════════════════════════════════════════

class _SignUpPage(QWidget):
    go_login = pyqtSignal()
    signup_success = pyqtSignal()
    update_user = pyqtSignal()  # emitted after successful signup to refresh user list in admin panel

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card, lay = _card()

        lay.addWidget(_logo())
        lay.addSpacing(4)
        lay.addWidget(_heading("CREATE ACCOUNT"))
        lay.addSpacing(8)

        self.err = _error_label()
        self.ok = _success_label()
        lay.addWidget(self.err)
        lay.addWidget(self.ok)

        # ── Full Name ──
        self.f_name = _input("full name")
        lay.addWidget(self.f_name)
        self.h_name = _hint_label()
        lay.addWidget(self.h_name)

        # ── Username ──
        self.f_user = _input("username")
        lay.addWidget(self.f_user)
        self.h_user = _hint_label()
        lay.addWidget(self.h_user)

        # ── Password ──
        self.f_pass = _input("password (8–12 chars)", password=True)
        lay.addWidget(self.f_pass)
        self.h_pass = _hint_label()
        lay.addWidget(self.h_pass)

        # ── Confirm Password ──
        self.f_pass2 = _input("confirm password", password=True)
        lay.addWidget(self.f_pass2)
        self.h_pass2 = _hint_label()
        lay.addWidget(self.h_pass2)

        lay.addSpacing(6)
        btn = _primary_btn("Sign Up")
        btn.clicked.connect(self._handle)
        lay.addWidget(btn)

        lay.addSpacing(6)
        row = QHBoxLayout()
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(tr("Already have an account?"))
        lbl.setObjectName("dimLabel")
        back = _link_btn("Log in!", bold=True)
        back.clicked.connect(self.go_login.emit)
        row.addWidget(lbl)
        row.addWidget(back)
        lay.addLayout(row)

        outer.addWidget(card)

        # ── Connect real-time validation on every keystroke ──
        self.f_name.textChanged.connect(self._validate_name_live)
        self.f_user.textChanged.connect(self._validate_username_live)
        self.f_pass.textChanged.connect(self._validate_password_live)
        self.f_pass2.textChanged.connect(self._validate_confirm_live)

    # ── Live validators (called on every keystroke) ──

    def _validate_name_live(self, text: str):
        text = text.strip()
        if not text:
            _set_hint(self.h_name, "")
            _set_field_state(self.f_name, "")
            return
        ok, msg = validate_fullname(text)
        if ok:
            _set_hint(self.h_name, "✓", ok=True)
            _set_field_state(self.f_name, "valid")
        else:
            _set_hint(self.h_name, msg)
            _set_field_state(self.f_name, "invalid")

    def _validate_username_live(self, text: str):
        text = text.strip()
        if not text:
            _set_hint(self.h_user, "")
            _set_field_state(self.f_user, "")
            return
        ok, msg = validate_username(text)
        if not ok:
            _set_hint(self.h_user, msg)
            _set_field_state(self.f_user, "invalid")
            return
        # Check uniqueness (case-insensitive)
        if adb.user_exists(text):
            _set_hint(self.h_user, "That username is already taken.")
            _set_field_state(self.f_user, "invalid")
            return
        _set_hint(self.h_user, "✓ Username available", ok=True)
        _set_field_state(self.f_user, "valid")

    def _validate_password_live(self, text: str):
        if not text:
            _set_hint(self.h_pass, "")
            _set_field_state(self.f_pass, "")
            return
        username = self.f_user.text().strip()
        ok, msg = validate_password(text, username)
        if ok:
            _set_hint(self.h_pass, "✓ Strong password", ok=True)
            _set_field_state(self.f_pass, "valid")
        else:
            _set_hint(self.h_pass, msg)
            _set_field_state(self.f_pass, "invalid")
        # Also recheck confirm if it has content
        if self.f_pass2.text():
            self._validate_confirm_live(self.f_pass2.text())

    def _validate_confirm_live(self, text: str):
        if not text:
            _set_hint(self.h_pass2, "")
            _set_field_state(self.f_pass2, "")
            return
        if text == self.f_pass.text():
            _set_hint(self.h_pass2, "✓ Passwords match", ok=True)
            _set_field_state(self.f_pass2, "valid")
        else:
            _set_hint(self.h_pass2, "Passwords do not match.")
            _set_field_state(self.f_pass2, "invalid")

    # ── Submit handler (runs all validations once more) ──

    def _handle(self):
        self.err.setText("")
        self.ok.setText("")

        fullname = self.f_name.text().strip()
        username = self.f_user.text().strip()
        pw = self.f_pass.text()
        pw2 = self.f_pass2.text()

        # Run all validations and show inline hints
        all_ok = True

        ok, msg = validate_fullname(fullname)
        if not ok:
            _set_hint(self.h_name, msg)
            _set_field_state(self.f_name, "invalid")
            all_ok = False

        ok, msg = validate_username(username)
        if not ok:
            _set_hint(self.h_user, msg)
            _set_field_state(self.f_user, "invalid")
            all_ok = False
        elif adb.user_exists(username):
            _set_hint(self.h_user, "That username is already taken.")
            _set_field_state(self.f_user, "invalid")
            all_ok = False

        ok, msg = validate_password(pw, username)
        if not ok:
            _set_hint(self.h_pass, msg)
            _set_field_state(self.f_pass, "invalid")
            all_ok = False

        if pw != pw2:
            _set_hint(self.h_pass2, "Passwords do not match.")
            _set_field_state(self.f_pass2, "invalid")
            all_ok = False

        if not all_ok:
            return

        success = adb.create_user(username, "", fullname, pw, is_admin=0)
        if not success:
            self.err.setText(tr("Could not create account. Try again."))
            return

        self.ok.setText(tr("Account created! You can now log in."))
        for w in (self.f_name, self.f_user, self.f_pass, self.f_pass2):
            w.clear()
        for h in (self.h_name, self.h_user, self.h_pass, self.h_pass2):
            _set_hint(h, "")


# ════════════════════════════════════════════════════════════════
# PAGE 2 – FORGOT PASSWORD  (enter email)
# ════════════════════════════════════════════════════════════════

class _ForgotPage(QWidget):
    go_login = pyqtSignal()
    go_reset = pyqtSignal()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card, lay = _card()

        lay.addWidget(_logo())
        lay.addSpacing(4)
        lay.addWidget(_heading("FORGOT PASSWORD"))
        lay.addSpacing(8)

        info = QLabel(tr("Enter the email linked to your account.\nWe'll send a reset code."))
        info.setObjectName("dimLabel")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        lay.addWidget(info)
        lay.addSpacing(4)

        self.err = _error_label()
        self.ok = _success_label()
        lay.addWidget(self.err)
        lay.addWidget(self.ok)

        self.f_email = _input("email")
        lay.addWidget(self.f_email)
        lay.addSpacing(8)

        btn = _primary_btn("Send Reset Code")
        btn.clicked.connect(self._handle)
        lay.addWidget(btn)

        lay.addSpacing(6)

        row = QHBoxLayout()
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(tr("Already have a code?"))
        lbl.setObjectName("dimLabel")
        rlink = _link_btn("Enter code", bold=True)
        rlink.clicked.connect(self.go_reset.emit)
        row.addWidget(lbl)
        row.addWidget(rlink)
        lay.addLayout(row)

        back = _link_btn("← Back to login")
        back.clicked.connect(self.go_login.emit)
        lay.addWidget(back, alignment=Qt.AlignmentFlag.AlignCenter)

        outer.addWidget(card)

    def _handle(self):
        self.err.setText("")
        self.ok.setText("")
        email = self.f_email.text().strip()

        ok, msg = validate_email(email)
        if not ok:
            self.err.setText(tr(msg))
            return

        username = adb.find_username_by_email(email)
        if username is None:
            self.ok.setText(tr("If that email is registered, a reset code has been sent."))
            return

        token = adb.create_reset_token(username)
        sent = _send_reset_email(email, token)

        if sent:
            self.ok.setText(tr("Reset code sent! Check your inbox."))
        else:
            self.ok.setText(tr(
                "Reset code (SMTP not configured):\n{token}\n\n"
                "Copy this code and click 'Enter code' below.", token=token
            ))


# ════════════════════════════════════════════════════════════════
# PAGE 3 – RESET PASSWORD  (enter token + new password)
# ════════════════════════════════════════════════════════════════

class _ResetPage(QWidget):
    go_login = pyqtSignal()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card, lay = _card()

        lay.addWidget(_logo())
        lay.addSpacing(4)
        lay.addWidget(_heading("RESET PASSWORD"))
        lay.addSpacing(8)

        self.err = _error_label()
        self.ok = _success_label()
        lay.addWidget(self.err)
        lay.addWidget(self.ok)

        self.f_token = _input("paste your reset code")
        lay.addWidget(self.f_token)

        self.f_pass = _input("new password (8–12 chars)", password=True)
        lay.addWidget(self.f_pass)
        self.h_pass = _hint_label()
        lay.addWidget(self.h_pass)

        self.f_pass2 = _input("confirm new password", password=True)
        lay.addWidget(self.f_pass2)
        self.h_pass2 = _hint_label()
        lay.addWidget(self.h_pass2)

        # Live validation on reset page too
        self.f_pass.textChanged.connect(self._validate_pw_live)
        self.f_pass2.textChanged.connect(self._validate_confirm_live)

        lay.addSpacing(6)
        btn = _primary_btn("Reset Password")
        btn.clicked.connect(self._handle)
        lay.addWidget(btn)

        lay.addSpacing(6)
        back = _link_btn("← Back to login")
        back.clicked.connect(self.go_login.emit)
        lay.addWidget(back, alignment=Qt.AlignmentFlag.AlignCenter)

        outer.addWidget(card)

    def _validate_pw_live(self, text):
        if not text:
            _set_hint(self.h_pass, "")
            _set_field_state(self.f_pass, "")
            return
        ok, msg = validate_password(text)
        if ok:
            _set_hint(self.h_pass, "✓ Strong password", ok=True)
            _set_field_state(self.f_pass, "valid")
        else:
            _set_hint(self.h_pass, msg)
            _set_field_state(self.f_pass, "invalid")
        if self.f_pass2.text():
            self._validate_confirm_live(self.f_pass2.text())

    def _validate_confirm_live(self, text):
        if not text:
            _set_hint(self.h_pass2, "")
            _set_field_state(self.f_pass2, "")
            return
        if text == self.f_pass.text():
            _set_hint(self.h_pass2, "✓ Passwords match", ok=True)
            _set_field_state(self.f_pass2, "valid")
        else:
            _set_hint(self.h_pass2, "Passwords do not match.")
            _set_field_state(self.f_pass2, "invalid")

    def _handle(self):
        self.err.setText("")
        self.ok.setText("")

        token = self.f_token.text().strip()
        pw = self.f_pass.text()
        pw2 = self.f_pass2.text()

        if not token:
            self.err.setText(tr("Paste the reset code you received."))
            return

        username = adb.validate_reset_token(token)
        if username is None:
            self.err.setText(tr("Invalid or expired reset code."))
            return

        ok, msg = validate_password(pw, username)
        if not ok:
            _set_hint(self.h_pass, msg)
            _set_field_state(self.f_pass, "invalid")
            return
        if pw != pw2:
            _set_hint(self.h_pass2, "Passwords do not match.")
            _set_field_state(self.f_pass2, "invalid")
            return

        adb.update_password(username, pw)
        adb.consume_reset_token(token)

        self.ok.setText(tr("Password updated! You can now log in."))
        for w in (self.f_token, self.f_pass, self.f_pass2):
            w.clear()
        _set_hint(self.h_pass, "")
        _set_hint(self.h_pass2, "")


# ════════════════════════════════════════════════════════════════
# PAGE 4 – ADMIN INVITE  (enter invite code)
# ════════════════════════════════════════════════════════════════

class _InvitePage(QWidget):
    go_login = pyqtSignal()
    go_signup = pyqtSignal()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card, lay = _card()

        lay.addWidget(_logo())
        lay.addSpacing(4)
        lay.addWidget(_heading("ADMIN INVITE"))
        lay.addSpacing(8)

        info = QLabel(tr(
            "An existing admin has sent you an invite code.\n"
            "Enter it below along with your account credentials."
        ))
        info.setObjectName("dimLabel")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        lay.addWidget(info)
        lay.addSpacing(4)

        self.err = _error_label()
        self.ok = _success_label()
        lay.addWidget(self.err)
        lay.addWidget(self.ok)

        self.f_code = _input("invite code")
        self.f_user = _input("your username")
        self.f_pass = _input("your password", password=True)

        for w in (self.f_code, self.f_user, self.f_pass):
            lay.addWidget(w)
            lay.addSpacing(2)

        lay.addSpacing(6)
        btn = _primary_btn("Activate Admin Access")
        btn.clicked.connect(self._handle)
        lay.addWidget(btn)

        lay.addSpacing(6)

        row = QHBoxLayout()
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(tr("No account yet?"))
        lbl.setObjectName("dimLabel")
        su = _link_btn("Sign up first", bold=True)
        su.clicked.connect(self.go_signup.emit)
        row.addWidget(lbl)
        row.addWidget(su)
        lay.addLayout(row)

        back = _link_btn("← Back to login")
        back.clicked.connect(self.go_login.emit)
        lay.addWidget(back, alignment=Qt.AlignmentFlag.AlignCenter)

        outer.addWidget(card)

    def _handle(self):
        self.err.setText("")
        self.ok.setText("")

        code = self.f_code.text().strip()
        username = self.f_user.text().strip()
        password = self.f_pass.text()

        if not code or not username or not password:
            self.err.setText(tr("All fields are required."))
            return

        if not adb.validate_invite_code(code):
            self.err.setText(tr("Invalid or expired invite code."))
            return

        result = adb.authenticate_user(username, password)
        if result is None:
            self.err.setText(tr("Invalid username or password."))
            return

        adb.promote_to_admin(username)
        adb.consume_invite_code(code, username)

        self.ok.setText(tr(
            "Success! '{username}' now has admin access.\n"
            "Go back to login to continue.", username=username
        ))
        for w in (self.f_code, self.f_user, self.f_pass):
            w.clear()


# ════════════════════════════════════════════════════════════════
# TOP-LEVEL LOGIN WINDOW  (stacks all pages)
# ════════════════════════════════════════════════════════════════

class LoginWindow(_GradientBG):
    login_successful = pyqtSignal(User)

    def __init__(self):
        super().__init__()

        # Ensure auth tables exist before any page tries to query them
        adb.init_auth_db()

        self.setMinimumSize(900, 650)
        self.setStyleSheet(_STYLES)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        self._build_pages()

    def _build_pages(self):
        """Create (or re-create) every page in the current language."""
        self._lang = i18n.get_language()
        self.setWindowTitle(tr("SafeTrack – Login"))
        while self.stack.count():
            old = self.stack.widget(0)
            self.stack.removeWidget(old)
            old.deleteLater()

        self.pg_login = _LoginPage()
        self.pg_signup = _SignUpPage()
        self.pg_forgot = _ForgotPage()
        self.pg_reset = _ResetPage()
        self.pg_invite = _InvitePage()

        for pg in (self.pg_login, self.pg_signup, self.pg_forgot,
                   self.pg_reset, self.pg_invite):
            self.stack.addWidget(pg)

        # wire navigation
        self.pg_login.go_signup.connect(lambda: self.stack.setCurrentIndex(1))
        self.pg_login.go_forgot.connect(lambda: self.stack.setCurrentIndex(2))
        self.pg_login.go_invite.connect(lambda: self.stack.setCurrentIndex(4))
        self.pg_login.login_success.connect(self._on_login)

        self.pg_signup.go_login.connect(lambda: self.stack.setCurrentIndex(0))
        self.pg_signup.signup_success.connect(lambda: self.stack.setCurrentIndex(0))

        self.pg_forgot.go_login.connect(lambda: self.stack.setCurrentIndex(0))
        self.pg_forgot.go_reset.connect(lambda: self.stack.setCurrentIndex(3))

        self.pg_reset.go_login.connect(lambda: self.stack.setCurrentIndex(0))

        self.pg_invite.go_login.connect(lambda: self.stack.setCurrentIndex(0))
        self.pg_invite.go_signup.connect(lambda: self.stack.setCurrentIndex(1))

    def _on_login(self, user: User):
        self.login_successful.emit(user)
        self.close()

    def show(self):
        if self._lang != i18n.get_language():
            self._build_pages()   # language was changed in Settings
        self.stack.setCurrentIndex(0)
        super().show()