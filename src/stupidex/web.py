from __future__ import annotations

import json
import logging
import os
import secrets
import tempfile
import time
import urllib.request
import uuid
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from flask import (
    Flask,
    Response,
    g,
    jsonify,
    make_response,
    request,
    send_from_directory,
    stream_with_context,
)

from . import __version__, db, providers, workspaces
from .config import settings
from .security import requires_approval, run_restricted, validate_command

app = Flask(__name__, static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_bytes
app.secret_key = settings.app_secret or secrets.token_bytes(32)
log_level = os.getenv("STUPIDEX_LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level)


def _token() -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get("stupidex_session", "")


def login_required(fn: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(fn)
    def wrapped(*args: Any, **kwargs: Any):
        user = db.get_user_by_token(_token())
        if not user:
            return jsonify({"error": "Não autenticado"}), 401
        g.user = user
        return fn(*args, **kwargs)

    return wrapped


def _json_error(exc: Exception, status: int = 400):
    return jsonify({"error": str(exc)}), status


@app.before_request
def origin_guard():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    origin = request.headers.get("Origin", "").rstrip("/")
    if not origin:
        return None
    same = origin == f"{request.scheme}://{request.host}".rstrip("/")
    if not same and origin not in settings.cors_origins:
        return jsonify({"error": "Origem não autorizada"}), 403
    return None


@app.after_request
def security_headers(response: Response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com https://cdn.jsdelivr.net; font-src 'self' data: https://fonts.gstatic.com https://unpkg.com https://cdn.jsdelivr.net; img-src 'self' data: https:; connect-src 'self' https:; frame-ancestors 'none'",
    )
    return response


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/health")
def health():
    try:
        with db.connect() as conn:
            conn.execute("SELECT 1").fetchone()
        database = "ok"
    except Exception:
        database = "error"
    status = 200 if database == "ok" else 503
    return jsonify(
        {
            "status": "ok" if status == 200 else "degraded",
            "version": __version__,
            "database": database,
            "shell": settings.shell_enabled,
        }
    ), status


@app.post("/api/auth/register")
def register():
    payload = request.get_json(silent=True) or {}
    try:
        user = db.create_user(
            str(payload.get("username", "")), str(payload.get("password", ""))
        )
        token = db.issue_token(user["id"])
        response = make_response(jsonify({"user": user, "token": token}), 201)
        response.set_cookie(
            "stupidex_session",
            token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="Lax",
            max_age=settings.session_days * 86400,
        )
        return response
    except Exception as exc:
        return _json_error(exc, 409 if "UNIQUE" in str(exc) else 400)


@app.post("/api/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    user = db.authenticate(
        str(payload.get("username", "")), str(payload.get("password", ""))
    )
    if not user:
        return jsonify({"error": "Credenciais inválidas"}), 401
    token = db.issue_token(user["id"])
    response = make_response(jsonify({"user": db.user_public(user), "token": token}))
    response.set_cookie(
        "stupidex_session",
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="Lax",
        max_age=settings.session_days * 86400,
    )
    return response


@app.post("/api/auth/logout")
@login_required
def logout():
    db.revoke_token(_token())
    response = make_response(jsonify({"ok": True}))
    response.delete_cookie("stupidex_session")
    return response


@app.get("/api/auth/me")
@login_required
def me():
    return jsonify(db.user_public(g.user))


@app.get("/api/models")
@login_required
def model_list():
    return jsonify(providers.models())


@app.get("/api/integrations/github")
@login_required
def github_status():
    return jsonify({"connected": bool(g.user.get("github_token_enc"))})


@app.post("/api/integrations/github")
@login_required
def github_connect():
    payload = request.get_json(silent=True) or {}
    token = str(payload.get("token") or "").strip()
    if not token:
        return jsonify({"error": "Token ausente"}), 400
    req = urllib.request.Request(
        "https://api.github.com/user",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "Stupidex",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            profile = json.loads(response.read().decode())
    except Exception:
        return jsonify({"error": "Token GitHub inválido ou sem acesso"}), 400
    db.update_github_token(g.user["id"], token)
    return jsonify({"connected": True, "login": profile.get("login", "")})


@app.delete("/api/integrations/github")
@login_required
def github_disconnect():
    db.clear_github_token(g.user["id"])
    return jsonify({"ok": True})


@app.get("/api/config")
@login_required
def get_config():
    return jsonify(db.user_public(g.user))


@app.post("/api/config")
@login_required
def save_config():
    payload = request.get_json(silent=True) or {}
    db.update_user_config(
        g.user["id"],
        str(payload.get("provider") or settings.default_provider)[:50],
        str(payload.get("model") or settings.default_model)[:200],
        str(payload.get("base_url") or "")[:500],
        payload.get("api_key") if "api_key" in payload else None,
    )
    return jsonify({"ok": True})


@app.get("/api/sessions")
@login_required
def sessions_list():
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT s.*, (SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id) message_count FROM sessions s WHERE user_id=? AND trashed=0 ORDER BY updated_at DESC LIMIT 100",
            (g.user["id"],),
        ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.post("/api/sessions")
@login_required
def session_create():
    payload = request.get_json(silent=True) or {}
    session_id = uuid.uuid4().hex
    now = time.time()
    title = str(payload.get("title") or "Nova conversa")[:120]
    mode = str(payload.get("mode") or "chat")[:20]
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO sessions(id,user_id,title,mode,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (session_id, g.user["id"], title, mode, now, now),
        )
    return jsonify(
        {
            "id": session_id,
            "title": title,
            "mode": mode,
            "created_at": now,
            "updated_at": now,
        }
    ), 201


@app.patch("/api/sessions/<session_id>")
@login_required
def session_patch(session_id: str):
    payload = request.get_json(silent=True) or {}
    allowed: dict[str, Any] = {}
    for key in ("title", "mode", "archived", "trashed"):
        if key in payload:
            allowed[key] = payload[key]
    if not allowed:
        return jsonify({"ok": True})
    fields = ",".join(f"{key}=?" for key in allowed)
    values = list(allowed.values()) + [time.time(), session_id, g.user["id"]]
    with db.connect() as conn:
        cur = conn.execute(
            f"UPDATE sessions SET {fields},updated_at=? WHERE id=? AND user_id=?",
            values,
        )
    return jsonify({"ok": cur.rowcount == 1})


@app.delete("/api/sessions/<session_id>")
@login_required
def session_delete(session_id: str):
    with db.connect() as conn:
        cur = conn.execute(
            "DELETE FROM sessions WHERE id=? AND user_id=?", (session_id, g.user["id"])
        )
    return jsonify({"ok": cur.rowcount == 1})


@app.get("/api/sessions/<session_id>/messages")
@login_required
def message_list(session_id: str):
    with db.connect() as conn:
        owned = conn.execute(
            "SELECT 1 FROM sessions WHERE id=? AND user_id=?",
            (session_id, g.user["id"]),
        ).fetchone()
        if not owned:
            return jsonify({"error": "Sessão não encontrada"}), 404
        rows = conn.execute(
            "SELECT id,role,content,metadata_json,created_at FROM messages WHERE session_id=? ORDER BY id",
            (session_id,),
        ).fetchall()
    return jsonify(
        [
            {**dict(row), "metadata": json.loads(row["metadata_json"] or "{}")}
            for row in rows
        ]
    )


@app.post("/api/sessions/<session_id>/chat")
@login_required
def chat(session_id: str):
    payload = request.get_json(silent=True) or {}
    content = str(payload.get("message") or "").strip()
    if not content:
        return jsonify({"error": "Mensagem vazia"}), 400
    with db.connect() as conn:
        session = conn.execute(
            "SELECT * FROM sessions WHERE id=? AND user_id=?",
            (session_id, g.user["id"]),
        ).fetchone()
        if not session:
            return jsonify({"error": "Sessão não encontrada"}), 404
        conn.execute(
            "INSERT INTO messages(session_id,role,content,created_at) VALUES(?,?,?,?)",
            (session_id, "user", content, time.time()),
        )
        rows = conn.execute(
            "SELECT role,content FROM messages WHERE session_id=? ORDER BY id DESC LIMIT 80",
            (session_id,),
        ).fetchall()
    history = [dict(row) for row in reversed(rows)]
    mode = str(payload.get("mode") or session["mode"] or "chat")
    system = {
        "role": "system",
        "content": f"Você é Stupidex, um assistente de IA objetivo e seguro. Modo atual: {mode}. Nunca alegue executar ferramentas sem ter recebido um resultado real do backend.",
    }
    model = str(payload.get("model") or g.user.get("model") or settings.default_model)

    @stream_with_context
    def generate():
        full = ""
        try:
            yield "event: start\ndata: {}\n\n"
            for token in providers.stream_chat(g.user, [system, *history], model=model):
                full += token
                yield (
                    "event: delta\ndata: "
                    + json.dumps({"text": token}, ensure_ascii=False)
                    + "\n\n"
                )
            with db.connect() as conn:
                conn.execute(
                    "INSERT INTO messages(session_id,role,content,created_at) VALUES(?,?,?,?)",
                    (session_id, "assistant", full, time.time()),
                )
                conn.execute(
                    "UPDATE sessions SET updated_at=? WHERE id=? AND user_id=?",
                    (time.time(), session_id, g.user["id"]),
                )
            yield (
                "event: done\ndata: "
                + json.dumps({"text": full}, ensure_ascii=False)
                + "\n\n"
            )
        except Exception as exc:
            yield (
                "event: error\ndata: "
                + json.dumps({"error": str(exc)}, ensure_ascii=False)
                + "\n\n"
            )

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/workspaces")
@login_required
def workspace_list():
    return jsonify(workspaces.list_all(g.user["id"]))


@app.post("/api/workspaces")
@login_required
def workspace_create():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(
            workspaces.create(g.user["id"], str(payload.get("name") or "Novo projeto"))
        ), 201
    except Exception as exc:
        return _json_error(exc)


@app.delete("/api/workspaces/<workspace_id>")
@login_required
def workspace_delete(workspace_id: str):
    try:
        workspaces.delete(g.user["id"], workspace_id)
        return jsonify({"ok": True})
    except KeyError as exc:
        return _json_error(exc, 404)


@app.get("/api/workspaces/<workspace_id>/tree")
@login_required
def workspace_tree(workspace_id: str):
    try:
        return jsonify(workspaces.tree(g.user["id"], workspace_id))
    except Exception as exc:
        return _json_error(exc)


@app.get("/api/workspaces/<workspace_id>/file")
@login_required
def workspace_read(workspace_id: str):
    try:
        return jsonify(
            {
                "path": request.args.get("path", ""),
                "content": workspaces.read_file(
                    g.user["id"], workspace_id, request.args.get("path", "")
                ),
            }
        )
    except FileNotFoundError as exc:
        return _json_error(exc, 404)
    except Exception as exc:
        return _json_error(exc)


@app.put("/api/workspaces/<workspace_id>/file")
@login_required
def workspace_write(workspace_id: str):
    payload = request.get_json(silent=True) or {}
    try:
        workspaces.write_file(
            g.user["id"],
            workspace_id,
            str(payload.get("path") or ""),
            str(payload.get("content") or ""),
        )
        db.audit(
            g.user["id"], "file.write", workspace_id, {"path": payload.get("path")}
        )
        return jsonify({"ok": True})
    except Exception as exc:
        return _json_error(exc)


@app.post("/api/workspaces/<workspace_id>/upload")
@login_required
def workspace_upload(workspace_id: str):
    try:
        count = workspaces.upload_files(
            g.user["id"], workspace_id, request.files.getlist("files")
        )
        return jsonify({"ok": True, "count": count})
    except Exception as exc:
        return _json_error(exc)


@app.post("/api/workspaces/<workspace_id>/upload-zip")
@login_required
def workspace_zip(workspace_id: str):
    upload = request.files.get("file")
    if not upload:
        return jsonify({"error": "Arquivo ZIP ausente"}), 400
    tmp = Path(tempfile.mkstemp(suffix=".zip")[1])
    try:
        upload.save(tmp)
        count = workspaces.extract_zip(g.user["id"], workspace_id, tmp)
        return jsonify({"ok": True, "count": count})
    except Exception as exc:
        return _json_error(exc)
    finally:
        tmp.unlink(missing_ok=True)


@app.post("/api/workspaces/<workspace_id>/clone")
@login_required
def workspace_clone(workspace_id: str):
    payload = request.get_json(silent=True) or {}
    try:
        output = workspaces.clone_repo(
            g.user["id"],
            workspace_id,
            str(payload.get("url") or ""),
            str(payload.get("branch") or ""),
            db.decrypt(g.user.get("github_token_enc") or ""),
        )
        db.audit(g.user["id"], "git.clone", workspace_id, {"url": payload.get("url")})
        return jsonify({"ok": True, "output": output})
    except Exception as exc:
        return _json_error(exc)


@app.post("/api/workspaces/<workspace_id>/shell")
@login_required
def shell(workspace_id: str):
    payload = request.get_json(silent=True) or {}
    command = str(payload.get("command") or "")
    try:
        argv = validate_command(command)
        if (
            requires_approval(argv)
            and settings.shell_require_approval
            and not payload.get("approved")
        ):
            approval_id = uuid.uuid4().hex
            with db.connect() as conn:
                conn.execute(
                    "INSERT INTO approvals(id,user_id,workspace_id,action,payload_json,created_at) VALUES(?,?,?,?,?,?)",
                    (
                        approval_id,
                        g.user["id"],
                        workspace_id,
                        "shell",
                        json.dumps(payload),
                        time.time(),
                    ),
                )
            return jsonify(
                {
                    "approval_required": True,
                    "approval_id": approval_id,
                    "command": command,
                }
            ), 202
        workspace = workspaces.workspace_path(g.user["id"], workspace_id)
        result = run_restricted(
            command, workspace, str(payload.get("cwd") or "."), payload.get("timeout")
        )
        db.audit(
            g.user["id"],
            "shell.execute",
            workspace_id,
            {
                "command": result["command"],
                "exit_code": result["exit_code"],
                "duration_ms": result["duration_ms"],
            },
        )
        return jsonify(result)
    except PermissionError as exc:
        db.audit(
            g.user["id"],
            "shell.blocked",
            workspace_id,
            {"command": command, "reason": str(exc)},
        )
        return _json_error(exc, 403)
    except Exception as exc:
        return _json_error(exc)


@app.post("/api/approvals/<approval_id>")
@login_required
def resolve_approval(approval_id: str):
    payload = request.get_json(silent=True) or {}
    decision = "approved" if payload.get("approve") else "rejected"
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM approvals WHERE id=? AND user_id=? AND status='pending'",
            (approval_id, g.user["id"]),
        ).fetchone()
        if not row:
            return jsonify({"error": "Aprovação não encontrada"}), 404
        conn.execute(
            "UPDATE approvals SET status=?,resolved_at=? WHERE id=?",
            (decision, time.time(), approval_id),
        )
    if decision == "rejected":
        return jsonify({"ok": True, "status": decision})
    original = json.loads(row["payload_json"])
    original["approved"] = True
    workspace = workspaces.workspace_path(g.user["id"], row["workspace_id"])
    try:
        result = run_restricted(
            original["command"],
            workspace,
            str(original.get("cwd") or "."),
            original.get("timeout"),
        )
        return jsonify({"ok": True, "status": decision, "result": result})
    except Exception as exc:
        return _json_error(exc)


def main() -> None:
    db.init_db()
    app.run(host=settings.host, port=settings.port, debug=False, threaded=True)


db.init_db()

if __name__ == "__main__":
    main()
