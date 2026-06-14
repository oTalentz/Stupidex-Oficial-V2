from __future__ import annotations

import os
import re
import shlex
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from .config import settings

ALLOWED_EXECUTABLES = {
    item.strip().lower()
    for item in os.getenv(
        "STUPIDEX_SHELL_COMMANDS",
        "python,python3,pytest,git,node,npm,npx,pnpm,yarn,cargo,go,dotnet,make,cmake,ruff,mypy,eslint,prettier",
    ).split(",")
    if item.strip()
}

BLOCKED_TOKENS = ("|", "&&", "||", ";", ">", "<", "`", "$(", "\n", "\r", "\x00")
BLOCKED_EXECUTABLES = {"bash", "sh", "zsh", "fish", "sudo", "su", "env", "printenv", "curl", "wget", "ssh", "scp", "nc", "netcat"}
SENSITIVE_NAMES = {".env", ".keyvault", ".flask_secret", "stupidex.db", "config.json"}
NETWORK_INSTALLERS = {"pip", "pip3", "npm", "npx", "pnpm", "yarn", "cargo", "go"}


def ensure_inside(path: Path, root: Path) -> Path:
    resolved_root = root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise PermissionError("Caminho fora do workspace") from exc
    if resolved.name in SENSITIVE_NAMES:
        raise PermissionError("Arquivo sensível bloqueado")
    return resolved


def safe_path(root: Path, raw: str = ".") -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        raise PermissionError("Caminhos absolutos não são permitidos")
    return ensure_inside(root / candidate, root)


def validate_command(command: str) -> list[str]:
    if not command or len(command) > 4096:
        raise ValueError("Comando vazio ou muito longo")
    if any(token in command for token in BLOCKED_TOKENS):
        raise PermissionError("Operadores de shell não são permitidos")
    argv = shlex.split(command, posix=os.name != "nt")
    if not argv:
        raise ValueError("Comando vazio")
    executable = Path(argv[0]).name.lower()
    if executable in BLOCKED_EXECUTABLES or executable not in ALLOWED_EXECUTABLES:
        raise PermissionError(f"Executável não autorizado: {executable}")
    lowered = [item.lower() for item in argv]
    if any(item.startswith("/") or item.startswith("~") for item in argv[1:]):
        raise PermissionError("Caminhos absolutos não são permitidos")
    if any(name in " ".join(lowered) for name in SENSITIVE_NAMES):
        raise PermissionError("Acesso a arquivo sensível bloqueado")
    if executable in {"python", "python3", "node"} and any(item in {"-c", "-e", "--eval"} for item in lowered[1:]):
        raise PermissionError("Execução de código inline foi bloqueada")
    if executable == "git" and len(argv) > 1 and argv[1].lower() in {"credential", "config"}:
        raise PermissionError("Subcomando Git bloqueado")
    return argv


def requires_approval(argv: list[str]) -> bool:
    executable = Path(argv[0]).name.lower()
    lowered = [x.lower() for x in argv[1:]]
    if executable in NETWORK_INSTALLERS and any(x in {"install", "add", "get"} for x in lowered):
        return True
    if executable == "git" and lowered and lowered[0] in {"push", "commit", "reset", "clean", "checkout", "switch"}:
        return True
    return False


def run_restricted(command: str, workspace: Path, cwd: str = ".", timeout: int | None = None) -> dict[str, Any]:
    if not settings.shell_enabled:
        raise PermissionError("Terminal desativado pelo servidor")
    argv = validate_command(command)
    workdir = safe_path(workspace, cwd)
    if not workdir.is_dir():
        raise ValueError("Diretório de trabalho inválido")
    timeout = min(max(int(timeout or 30), 1), settings.shell_timeout)
    env = {
        "PATH": os.getenv("PATH", os.defpath),
        "HOME": str(workspace / ".home"),
        "TMPDIR": str(workspace / ".tmp"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "NO_COLOR": "1",
        "CI": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }
    Path(env["HOME"]).mkdir(exist_ok=True)
    Path(env["TMPDIR"]).mkdir(exist_ok=True)
    started = time.time()
    process = subprocess.Popen(
        argv,
        cwd=str(workdir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        shell=False,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(process.pid, signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=2)
        except Exception:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except Exception:
                process.kill()
            stdout, stderr = process.communicate()
    limit = settings.shell_output_limit
    stdout = (stdout or b"")[:limit].decode("utf-8", errors="replace")
    stderr = (stderr or b"")[:limit].decode("utf-8", errors="replace")
    return {
        "command": " ".join(shlex.quote(x) for x in argv),
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": process.returncode,
        "duration_ms": int((time.time() - started) * 1000),
        "timed_out": timed_out,
        "truncated": len(stdout.encode()) >= limit or len(stderr.encode()) >= limit,
    }
