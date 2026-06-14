from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any

from .config import settings
from .db import connect
from .security import ensure_inside, safe_path

ID_RX = re.compile(r"^[0-9a-f]{12}$")
SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", "dist", "build", ".next"}


def workspace_path(user_id: str, workspace_id: str) -> Path:
    if not ID_RX.fullmatch(workspace_id):
        raise ValueError("Workspace inválido")
    root = settings.workspace_root / user_id
    path = root / workspace_id
    ensure_inside(path, root)
    return path


def create(user_id: str, name: str = "Novo projeto") -> dict[str, Any]:
    workspace_id = uuid.uuid4().hex[:12]
    path = workspace_path(user_id, workspace_id)
    path.mkdir(parents=True, exist_ok=False)
    now = time.time()
    with connect() as conn:
        conn.execute(
            "INSERT INTO workspaces(id,user_id,name,created_at,updated_at) VALUES(?,?,?,?,?)",
            (workspace_id, user_id, (name or "Novo projeto")[:80], now, now),
        )
    return get(user_id, workspace_id)


def get(user_id: str, workspace_id: str) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM workspaces WHERE id=? AND user_id=?", (workspace_id, user_id)).fetchone()
    if not row:
        raise KeyError("Workspace não encontrado")
    result = dict(row)
    path = workspace_path(user_id, workspace_id)
    size = sum(p.stat().st_size for p in path.rglob("*") if p.is_file() and ".git" not in p.parts)
    result["size_bytes"] = size
    return result


def list_all(user_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM workspaces WHERE user_id=? ORDER BY updated_at DESC", (user_id,)).fetchall()
    return [dict(row) for row in rows]


def delete(user_id: str, workspace_id: str) -> None:
    path = workspace_path(user_id, workspace_id)
    with connect() as conn:
        cur = conn.execute("DELETE FROM workspaces WHERE id=? AND user_id=?", (workspace_id, user_id))
        if cur.rowcount != 1:
            raise KeyError("Workspace não encontrado")
    shutil.rmtree(path, ignore_errors=True)


def tree(user_id: str, workspace_id: str, limit: int = 2000) -> list[dict[str, Any]]:
    root = workspace_path(user_id, workspace_id)
    items: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda p: (len(p.parts), p.as_posix().lower())):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.is_symlink():
            continue
        items.append({"path": rel.as_posix(), "name": path.name, "type": "directory" if path.is_dir() else "file", "size": 0 if path.is_dir() else path.stat().st_size})
        if len(items) >= limit:
            break
    return items


def read_file(user_id: str, workspace_id: str, raw_path: str) -> str:
    root = workspace_path(user_id, workspace_id)
    path = safe_path(root, raw_path)
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError("Arquivo não encontrado")
    if path.stat().st_size > 1_000_000:
        raise ValueError("Arquivo muito grande para visualização")
    return path.read_text("utf-8")


def write_file(user_id: str, workspace_id: str, raw_path: str, content: str) -> None:
    root = workspace_path(user_id, workspace_id)
    path = safe_path(root, raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    with connect() as conn:
        conn.execute("UPDATE workspaces SET updated_at=? WHERE id=? AND user_id=?", (time.time(), workspace_id, user_id))


def upload_files(user_id: str, workspace_id: str, files: list[Any]) -> int:
    root = workspace_path(user_id, workspace_id)
    count = 0
    for upload in files:
        filename = Path(upload.filename or "").name
        if not filename:
            continue
        target = safe_path(root, filename)
        upload.save(target)
        count += 1
    return count


def extract_zip(user_id: str, workspace_id: str, archive_path: Path) -> int:
    root = workspace_path(user_id, workspace_id)
    count = 0
    with zipfile.ZipFile(archive_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            if info.file_size > 20_000_000:
                raise ValueError("Arquivo interno muito grande")
            target = safe_path(root, info.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
    return count


def clone_repo(user_id: str, workspace_id: str, url: str, branch: str = "", github_token: str = "") -> str:
    if not re.fullmatch(r"https://(github\.com|gitlab\.com)/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?", url):
        raise ValueError("Apenas URLs HTTPS do GitHub ou GitLab são permitidas")
    root = workspace_path(user_id, workspace_id)
    if any(root.iterdir()):
        raise ValueError("O workspace precisa estar vazio para clonagem")
    args = ["git", "clone", "--depth", "1"]
    if branch:
        args += ["--branch", branch]
    args += [url, str(root)]
    env = {"PATH": os.getenv("PATH", os.defpath), "HOME": str(root), "GIT_TERMINAL_PROMPT": "0", "LANG": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    if github_token and "github.com" in url:
        import base64
        credentials = base64.b64encode(f"x-access-token:{github_token}".encode()).decode()
        env.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader", "GIT_CONFIG_VALUE_0": f"Authorization: Basic {credentials}"})
    result = subprocess.run(args, capture_output=True, text=True, timeout=120, env=env)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2000:] or "Falha ao clonar")
    with connect() as conn:
        conn.execute(
            "UPDATE workspaces SET source='git',git_url=?,git_branch=?,updated_at=? WHERE id=? AND user_id=?",
            (url, branch or "main", time.time(), workspace_id, user_id),
        )
    return result.stdout[-2000:]
