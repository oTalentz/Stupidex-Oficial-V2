from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from cryptography.fernet import Fernet, InvalidToken
from werkzeug.security import check_password_hash, generate_password_hash

from .config import settings


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at REAL NOT NULL,
  provider TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL DEFAULT '',
  base_url TEXT NOT NULL DEFAULT '',
  api_key_enc TEXT NOT NULL DEFAULT '',
  github_token_enc TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS auth_tokens (
  token_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at REAL NOT NULL,
  expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  mode TEXT NOT NULL DEFAULT 'chat',
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL,
  archived INTEGER NOT NULL DEFAULT 0,
  trashed INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_sessions_user_updated ON sessions(user_id, updated_at DESC);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  content TEXT NOT NULL DEFAULT '',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id, id);
CREATE TABLE IF NOT EXISTS workspaces (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'empty',
  git_url TEXT NOT NULL DEFAULT '',
  git_branch TEXT NOT NULL DEFAULT '',
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_workspaces_user ON workspaces(user_id, updated_at DESC);
CREATE TABLE IF NOT EXISTS approvals (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  workspace_id TEXT NOT NULL,
  action TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at REAL NOT NULL,
  resolved_at REAL
);
CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  action TEXT NOT NULL,
  resource TEXT NOT NULL DEFAULT '',
  detail_json TEXT NOT NULL DEFAULT '{}',
  created_at REAL NOT NULL
);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(settings.db_path), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def _key_file() -> Path:
    return settings.data_dir / ".keyvault"


def _fernet() -> Fernet:
    path = _key_file()
    if not path.exists():
        path.write_bytes(Fernet.generate_key())
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return Fernet(path.read_bytes().strip())


def encrypt(value: str) -> str:
    return "" if not value else _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        return ""


def create_user(username: str, password: str) -> dict[str, Any]:
    username = username.strip().lower()
    if not (3 <= len(username) <= 50):
        raise ValueError("O usuário deve ter entre 3 e 50 caracteres")
    if len(password) < 8:
        raise ValueError("A senha deve ter pelo menos 8 caracteres")
    user_id = uuid.uuid4().hex
    now = time.time()
    with connect() as conn:
        conn.execute(
            "INSERT INTO users(id,username,password_hash,created_at) VALUES(?,?,?,?)",
            (user_id, username, generate_password_hash(password), now),
        )
    return {"id": user_id, "username": username, "created_at": now}


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username.strip().lower(),)).fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        return None
    return dict(row)


def issue_token(user_id: str) -> str:
    raw = secrets.token_urlsafe(40)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    now = time.time()
    with connect() as conn:
        conn.execute(
            "INSERT INTO auth_tokens(token_hash,user_id,created_at,expires_at) VALUES(?,?,?,?)",
            (digest, user_id, now, now + settings.session_days * 86400),
        )
    return raw


def get_user_by_token(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    digest = hashlib.sha256(raw.encode()).hexdigest()
    now = time.time()
    with connect() as conn:
        row = conn.execute(
            "SELECT users.* FROM auth_tokens JOIN users ON users.id=auth_tokens.user_id WHERE token_hash=? AND expires_at>?",
            (digest, now),
        ).fetchone()
    return dict(row) if row else None


def revoke_token(raw: str) -> None:
    digest = hashlib.sha256(raw.encode()).hexdigest()
    with connect() as conn:
        conn.execute("DELETE FROM auth_tokens WHERE token_hash=?", (digest,))


def update_user_config(user_id: str, provider: str, model: str, base_url: str, api_key: str | None) -> None:
    with connect() as conn:
        if api_key is None:
            conn.execute("UPDATE users SET provider=?,model=?,base_url=? WHERE id=?", (provider, model, base_url, user_id))
        else:
            conn.execute(
                "UPDATE users SET provider=?,model=?,base_url=?,api_key_enc=? WHERE id=?",
                (provider, model, base_url, encrypt(api_key), user_id),
            )



def update_github_token(user_id: str, token: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE users SET github_token_enc=? WHERE id=?", (encrypt(token), user_id))


def clear_github_token(user_id: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE users SET github_token_enc='' WHERE id=?", (user_id,))


def user_public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "username": row["username"],
        "created_at": row["created_at"],
        "provider": row.get("provider") or settings.default_provider,
        "model": row.get("model") or settings.default_model,
        "base_url": row.get("base_url") or settings.default_base_url,
        "has_api_key": bool(row.get("api_key_enc")),
        "github_connected": bool(row.get("github_token_enc")),
    }


def audit(user_id: str, action: str, resource: str = "", detail: dict[str, Any] | None = None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO audit_logs(user_id,action,resource,detail_json,created_at) VALUES(?,?,?,?,?)",
            (user_id, action, resource, json.dumps(detail or {}, ensure_ascii=False), time.time()),
        )
