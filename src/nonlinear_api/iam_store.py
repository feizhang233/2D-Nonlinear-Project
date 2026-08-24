"""Server-side identity, revocable sessions, and private model history."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

PASSWORD_SCHEME = "scrypt"
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SESSION_TTL_DAYS = 30
MODEL_HISTORY_LIMIT = 24


class DuplicateEmailError(ValueError):
    """Raised when an email is already registered."""


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=32,
    )
    encoded_salt = base64.urlsafe_b64encode(salt).decode("ascii")
    encoded_digest = base64.urlsafe_b64encode(digest).decode("ascii")
    return (
        f"{PASSWORD_SCHEME}${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}"
        f"${encoded_salt}${encoded_digest}"
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, raw_n, raw_r, raw_p, raw_salt, raw_digest = encoded.split("$", 5)
        if scheme != PASSWORD_SCHEME:
            return False
        salt = base64.urlsafe_b64decode(raw_salt.encode("ascii"))
        expected = base64.urlsafe_b64decode(raw_digest.encode("ascii"))
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(raw_n),
            r=int(raw_r),
            p=int(raw_p),
            dklen=len(expected),
        )
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(actual, expected)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def default_database_path() -> Path:
    configured = os.environ.get("NONLINEAR_DATA_DIR", "").strip()
    data_dir = Path(configured).expanduser() if configured else Path("frontend/.nonlinear-data")
    return data_dir / "nonlinear-studio.sqlite3"


class IdentityStore:
    """Persist account data and user-owned model snapshots in SQLite."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = Path(database_path) if database_path else default_database_path()

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_used_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions(expires_at);
            CREATE TABLE IF NOT EXISTS saved_models (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                model_family TEXT NOT NULL,
                saved_at TEXT NOT NULL,
                model_json TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS saved_models_user_time_idx
                ON saved_models(user_id, saved_at DESC);
            """
        )
        return connection

    @staticmethod
    def _public_user(row: sqlite3.Row) -> dict[str, str]:
        return {
            "id": str(row["id"]),
            "email": str(row["email"]),
            "display_name": str(row["display_name"]),
            "created_at": str(row["created_at"]),
        }

    def register(self, email: str, display_name: str, password: str) -> dict[str, str]:
        user_id = uuid4().hex
        created_at = _iso_utc(_utc_now())
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO users (id, email, display_name, password_hash, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        normalize_email(email),
                        display_name.strip(),
                        hash_password(password),
                        created_at,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise DuplicateEmailError("An account with this email already exists") from error
        return {
            "id": user_id,
            "email": normalize_email(email),
            "display_name": display_name.strip(),
            "created_at": created_at,
        }

    def authenticate(self, email: str, password: str) -> dict[str, str] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, email, display_name, password_hash, created_at
                FROM users WHERE email = ? COLLATE NOCASE
                """,
                (normalize_email(email),),
            ).fetchone()
        if row is None or not verify_password(password, str(row["password_hash"])):
            return None
        return self._public_user(row)

    def create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        now = _utc_now()
        expires_at = now + timedelta(days=SESSION_TTL_DAYS)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (token_hash, user_id, expires_at, created_at, last_used_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (_token_hash(token), user_id, _iso_utc(expires_at), _iso_utc(now), _iso_utc(now)),
            )
            connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (_iso_utc(now),))
        return token

    def user_for_session(self, token: str) -> dict[str, str] | None:
        now = _iso_utc(_utc_now())
        token_hash = _token_hash(token)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT users.id, users.email, users.display_name, users.created_at
                FROM sessions
                INNER JOIN users ON users.id = sessions.user_id
                WHERE sessions.token_hash = ? AND sessions.expires_at > ?
                """,
                (token_hash, now),
            ).fetchone()
            if row is not None:
                connection.execute(
                    "UPDATE sessions SET last_used_at = ? WHERE token_hash = ?",
                    (now, token_hash),
                )
        return self._public_user(row) if row is not None else None

    def delete_session(self, token: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))

    def list_models(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, model_family, saved_at, model_json
                FROM saved_models
                WHERE user_id = ?
                ORDER BY saved_at DESC
                LIMIT ?
                """,
                (user_id, MODEL_HISTORY_LIMIT),
            ).fetchall()
        return [
            {
                "id": str(row["id"]),
                "name": str(row["name"]),
                "model_family": str(row["model_family"]),
                "saved_at": str(row["saved_at"]),
                "model": json.loads(str(row["model_json"])),
            }
            for row in rows
        ]

    def save_model(self, user_id: str, name: str, model: dict[str, Any]) -> dict[str, Any]:
        entry = {
            "id": uuid4().hex,
            "name": name.strip(),
            "model_family": str(model["model_family"]),
            "saved_at": _iso_utc(_utc_now()),
            "model": model,
        }
        model_json = json.dumps(model, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO saved_models (id, user_id, name, model_family, saved_at, model_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry["id"],
                    user_id,
                    entry["name"],
                    entry["model_family"],
                    entry["saved_at"],
                    model_json,
                ),
            )
            connection.execute(
                """
                DELETE FROM saved_models
                WHERE user_id = ? AND id NOT IN (
                    SELECT id FROM saved_models
                    WHERE user_id = ?
                    ORDER BY saved_at DESC
                    LIMIT ?
                )
                """,
                (user_id, user_id, MODEL_HISTORY_LIMIT),
            )
        return entry

    def delete_model(self, user_id: str, entry_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM saved_models WHERE user_id = ? AND id = ?",
                (user_id, entry_id),
            )
            return cursor.rowcount > 0


__all__ = [
    "DuplicateEmailError",
    "IdentityStore",
    "MODEL_HISTORY_LIMIT",
    "SESSION_TTL_DAYS",
    "hash_password",
    "normalize_email",
    "verify_password",
]
