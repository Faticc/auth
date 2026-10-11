"""Client for the Java agent's loopback control port.

The agent (see ``../agent``) listens on 127.0.0.1:<port> and speaks a tiny
newline-delimited JSON protocol:

    -> {"uuid": "...", "accessToken": "...", "username": "..."}\\n
    <- {"ok": true, "username": "...", "strategy": "..."}\\n
       {"ok": false, "error": "..."}\\n

Only the loopback interface is used, so the control channel never leaves the
machine the game runs on.
"""

import json
import socket
from typing import Optional

from .session import GameSession

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5151


class ControlError(Exception):
    pass


def apply_session(
    session: GameSession,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = 5.0,
) -> dict:
    """Push ``session`` to a running agent and return its JSON reply.

    Raises :class:`ControlError` if the agent is unreachable, times out, or
    reports that it could not apply the session.
    """
    payload = (json.dumps(session.to_wire()) + "\n").encode("utf-8")

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(payload)
            sock.shutdown(socket.SHUT_WR)
            raw = _read_line(sock, timeout)
    except OSError as exc:
        raise ControlError(
            f"cannot reach the Minecraft agent at {host}:{port} "
            f"(is the game running with the agent attached?): {exc}"
        ) from exc

    try:
        reply = json.loads(raw.decode("utf-8", errors="replace"))
    except ValueError as exc:
        raise ControlError(f"malformed reply from agent: {raw!r}") from exc

    if not isinstance(reply, dict) or not reply.get("ok"):
        message = ""
        if isinstance(reply, dict):
            message = str(reply.get("error", ""))
        raise ControlError(message or "agent could not apply the session")

    return reply


def _read_line(sock: socket.socket, timeout: float) -> bytes:
    sock.settimeout(timeout)
    chunks = []
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    data = b"".join(chunks)
    line, _, _ = data.partition(b"\n")
    return line


def ping(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = 2.0,
) -> bool:
    """Return True if an agent is listening on the control port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
