"""
auth_database.py
────────────────
SQLite-backed authentication store.  Lives inside nodes.db alongside
the existing nodes / notifications / users tables.

Tables (all created in nodes.db)
------
  auth_users     – username (unique, case-insensitive), email (encrypted),
                   full_name (encrypted), password_hash (bcrypt), is_admin,
                   created_at
  reset_tokens   – token, username, expires_at, used
  invite_codes   – code, created_by (admin), used_by, expires_at, used
  emergency_contacts – owner username, name (encrypted), phone (encrypted),
                   relationship, created_at

Sensitive fields (email, full_name) are Fernet-encrypted at rest.
Passwords are bcrypt-hashed (never stored in plain text).
"""

import sqlite3
import os
from datetime import datetime, timedelta, timezone

from auth_utils import (
    hash_password, verify_password,
    encrypt_field, decrypt_field,
    generate_reset_token, generate_invite_code,
)

DB_PATH = "nodes.db"


def _conn():
    return sqlite3.connect(DB_PATH)
 

# ──────────────────────────────────────
# SCHEMA
# ──────────────────────────────────────

def init_auth_db():
    """Create tables if they don't exist."""
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS auth_users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            email_enc       TEXT    NOT NULL,
            fullname_enc    TEXT    NOT NULL,
            password_hash   TEXT    NOT NULL,
            is_admin        INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reset_tokens (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            token       TEXT    NOT NULL UNIQUE,
            username    TEXT    NOT NULL,
            expires_at  TEXT    NOT NULL,
            used        INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS invite_codes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT    NOT NULL UNIQUE,
            created_by  TEXT    NOT NULL,
            used_by     TEXT,
            expires_at  TEXT    NOT NULL,
            used        INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS emergency_contacts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            owner           TEXT    NOT NULL COLLATE NOCASE,
            name_enc        TEXT    NOT NULL,
            phone_enc       TEXT    NOT NULL,
            relationship    TEXT    NOT NULL DEFAULT '',
            created_at      TEXT    NOT NULL
        );
        """)
        # Older databases: add the phone column to auth_users if it is missing
        cols = [r[1] for r in con.execute("PRAGMA table_info(auth_users)")]
        if "phone_enc" not in cols:
            con.execute("ALTER TABLE auth_users ADD COLUMN phone_enc TEXT NOT NULL DEFAULT ''")


# ──────────────────────────────────────
# USER CRUD
# ──────────────────────────────────────

def user_exists(username: str) -> bool:
    """Case-insensitive check."""
    try:
        with _conn() as con:
            row = con.execute(
                "SELECT 1 FROM auth_users WHERE username = ? COLLATE NOCASE", (username,)
            ).fetchone()
            return row is not None
    except Exception as exc:
        print(f"[auth_database] user_exists error: {exc}")
        return False


def email_exists(email: str) -> bool:
    """Scan encrypted emails (necessary because Fernet is non-deterministic)."""
    try:
        with _conn() as con:
            rows = con.execute("SELECT email_enc FROM auth_users").fetchall()
        low = email.lower()
        for (enc,) in rows:
            try:
                if decrypt_field(enc).lower() == low:
                    return True
            except Exception:
                continue
        return False
    except Exception as exc:
        print(f"[auth_database] email_exists error: {exc}")
        return False


def create_user(
    username: str,
    email: str,
    fullname: str,
    password: str,
    is_admin: int = 0,
) -> bool:
    """Insert a new user. Returns True on success."""
    try:
        with _conn() as con:
            con.execute(
                """INSERT INTO auth_users
                   (username, email_enc, fullname_enc, password_hash, is_admin, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    username,
                    encrypt_field(email),
                    encrypt_field(fullname),
                    hash_password(password),
                    is_admin,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as exc:
        print(f"[auth_database] create_user error: {exc}")
        return False


def authenticate_user(username: str, password: str) -> dict | None:
    """
    Return user dict on success, None on failure.
    Dict keys: id, username, is_admin, email, fullname
    """
    try:
        with _conn() as con:
            row = con.execute(
                """SELECT id, username, password_hash, is_admin,
                          email_enc, fullname_enc
                   FROM auth_users WHERE username = ? COLLATE NOCASE""",
                (username,),
            ).fetchone()
        if row is None:
            return None
        uid, uname, pw_hash, is_admin, email_enc, fn_enc = row
        if not verify_password(password, pw_hash):
            return None
        return {
            "id": uid,
            "username": uname,
            "is_admin": is_admin,
            "email": decrypt_field(email_enc),
            "fullname": decrypt_field(fn_enc),
        }
    except Exception as exc:
        print(f"[auth_database] authenticate_user error: {exc}")
        return None


def get_user_by_username(username: str) -> dict | None:
    """Look up user info (no password check)."""
    with _conn() as con:
        row = con.execute(
            """SELECT id, username, is_admin, email_enc, fullname_enc
               FROM auth_users WHERE username = ? COLLATE NOCASE""",
            (username,),
        ).fetchone()
    if row is None:
        return None
    uid, uname, is_admin, email_enc, fn_enc = row
    return {
        "id": uid,
        "username": uname,
        "is_admin": is_admin,
        "email": decrypt_field(email_enc),
        "fullname": decrypt_field(fn_enc),
    }


def find_username_by_email(email: str) -> str | None:
    """Return the username associated with an email, or None."""
    with _conn() as con:
        rows = con.execute("SELECT username, email_enc FROM auth_users").fetchall()
    low = email.lower()
    for uname, enc in rows:
        try:
            if decrypt_field(enc).lower() == low:
                return uname
        except Exception:
            continue
    return None


def update_password(username: str, new_password: str) -> bool:
    with _conn() as con:
        cur = con.execute(
            "UPDATE auth_users SET password_hash = ? WHERE username = ? COLLATE NOCASE",
            (hash_password(new_password), username),
        )
        return cur.rowcount > 0


def get_phone(username: str) -> str:
    with _conn() as con:
        row = con.execute(
            "SELECT phone_enc FROM auth_users WHERE username = ? COLLATE NOCASE", (username,)
        ).fetchone()
    if not row or not row[0]:
        return ""
    try:
        return decrypt_field(row[0])
    except Exception:
        return ""


def update_profile(username: str, fullname: str, email: str, phone: str) -> bool:
    """Update the editable profile fields for a user."""
    with _conn() as con:
        cur = con.execute(
            """UPDATE auth_users SET fullname_enc = ?, email_enc = ?, phone_enc = ?
               WHERE username = ? COLLATE NOCASE""",
            (encrypt_field(fullname), encrypt_field(email),
             encrypt_field(phone) if phone else "", username),
        )
        return cur.rowcount > 0


def promote_to_admin(username: str) -> bool:
    with _conn() as con:
        cur = con.execute(
            "UPDATE auth_users SET is_admin = 1 WHERE username = ? COLLATE NOCASE",
            (username,),
        )
        return cur.rowcount > 0
    
def remove_user(username: str) -> bool:
    with _conn() as con:
        con.execute("DELETE FROM emergency_contacts WHERE owner = ? COLLATE NOCASE", (username,))
        cur = con.execute(
            "DELETE FROM auth_users WHERE username = ? COLLATE NOCASE",
            (username,),
        )
        return cur.rowcount > 0


# ──────────────────────────────────────
# PASSWORD-RESET TOKENS
# ──────────────────────────────────────

def create_reset_token(username: str, hours: int = 1) -> str:
    """Generate and store a time-limited reset token. Returns the token string."""
    token = generate_reset_token()
    expires = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
    with _conn() as con:
        con.execute(
            "INSERT INTO reset_tokens (token, username, expires_at) VALUES (?, ?, ?)",
            (token, username, expires),
        )
    return token


def validate_reset_token(token: str) -> str | None:
    """
    If the token is valid and not expired, return the associated username.
    Otherwise return None.
    """
    with _conn() as con:
        row = con.execute(
            "SELECT username, expires_at, used FROM reset_tokens WHERE token = ?",
            (token,),
        ).fetchone()
    if row is None:
        return None
    username, expires_str, used = row
    if used:
        return None
    expires = datetime.fromisoformat(expires_str)
    if datetime.now(timezone.utc) > expires:
        return None
    return username


def consume_reset_token(token: str) -> bool:
    """Mark the token as used. Returns True if successful."""
    with _conn() as con:
        cur = con.execute(
            "UPDATE reset_tokens SET used = 1 WHERE token = ? AND used = 0",
            (token,),
        )
        return cur.rowcount > 0


# ──────────────────────────────────────
# ADMIN INVITE CODES
# ──────────────────────────────────────

def create_invite_code(admin_username: str, hours: int = 48) -> str:
    """Admin creates an invite code. Returns the code string."""
    code = generate_invite_code()
    expires = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
    with _conn() as con:
        con.execute(
            "INSERT INTO invite_codes (code, created_by, expires_at) VALUES (?, ?, ?)",
            (code, admin_username, expires),
        )
    return code


def validate_invite_code(code: str) -> bool:
    """Check if code exists, not used, not expired."""
    with _conn() as con:
        row = con.execute(
            "SELECT expires_at, used FROM invite_codes WHERE code = ? COLLATE NOCASE",
            (code,),
        ).fetchone()
    if row is None:
        return False
    expires_str, used = row
    if used:
        return False
    expires = datetime.fromisoformat(expires_str)
    return datetime.now(timezone.utc) <= expires


def consume_invite_code(code: str, used_by: str) -> bool:
    """Mark the invite code as used by *used_by*. Returns True on success."""
    with _conn() as con:
        cur = con.execute(
            "UPDATE invite_codes SET used = 1, used_by = ? WHERE code = ? COLLATE NOCASE AND used = 0",
            (used_by, code),
        )
        return cur.rowcount > 0


def list_invite_codes(admin_username: str) -> list[dict]:
    """List all invite codes created by this admin."""
    with _conn() as con:
        rows = con.execute(
            """SELECT code, used_by, expires_at, used
               FROM invite_codes WHERE created_by = ? ORDER BY id DESC""",
            (admin_username,),
        ).fetchall()
    result = []
    for code, used_by, exp, used in rows:
        result.append({
            "code": code,
            "used_by": used_by or "",
            "expires_at": exp,
            "used": bool(used),
        })
    return result


# ──────────────────────────────────────
# EMERGENCY CONTACTS
# ──────────────────────────────────────

def add_emergency_contact(owner: str, name: str, phone: str, relationship: str = "") -> bool:
    try:
        with _conn() as con:
            con.execute(
                """INSERT INTO emergency_contacts
                   (owner, name_enc, phone_enc, relationship, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (owner, encrypt_field(name), encrypt_field(phone), relationship,
                 datetime.now(timezone.utc).isoformat()),
            )
        return True
    except Exception as exc:
        print(f"[auth_database] add_emergency_contact error: {exc}")
        return False


def list_emergency_contacts(owner: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """SELECT id, name_enc, phone_enc, relationship
               FROM emergency_contacts WHERE owner = ? COLLATE NOCASE ORDER BY id""",
            (owner,),
        ).fetchall()
    result = []
    for cid, name_enc, phone_enc, rel in rows:
        try:
            result.append({
                "id": cid,
                "name": decrypt_field(name_enc),
                "phone": decrypt_field(phone_enc),
                "relationship": rel,
            })
        except Exception:
            continue
    return result


def remove_emergency_contact(owner: str, contact_id: int) -> bool:
    with _conn() as con:
        cur = con.execute(
            "DELETE FROM emergency_contacts WHERE id = ? AND owner = ? COLLATE NOCASE",
            (contact_id, owner),
        )
        return cur.rowcount > 0


if __name__ == "__main__":
    init_auth_db()
    remove_user("admin")
    create_user("admin", "", "", "admin@123", is_admin=1)