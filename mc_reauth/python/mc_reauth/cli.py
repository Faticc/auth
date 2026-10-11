"""Command-line front end: authenticate and hot-swap the live account.

Typical use from an administration tool (no game restart needed):

    python -m mc_reauth switch --provider mcskill --username admin
    # password is read from MC_REAUTH_PASSWORD or prompted for

    python -m mc_reauth switch --provider gribland \\
        --username admin --client-name SKYDRIVE-HITECH-TEST

    python -m mc_reauth attach --pid 12345      # attach agent at runtime
    python -m mc_reauth ping                     # is an agent listening?
"""

import argparse
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from . import control
from .providers import PRIORITY, authenticate
from .session import AuthError

ENV_PASSWORD = "MC_REAUTH_PASSWORD"


def _resolve_password(args: argparse.Namespace) -> str:
    if args.password:
        return args.password
    env = os.environ.get(ENV_PASSWORD)
    if env:
        return env
    return getpass.getpass("Password: ")


def _cmd_switch(args: argparse.Namespace) -> int:
    try:
        session = authenticate(
            username=args.username,
            password=_resolve_password(args),
            provider=args.provider,
            code=args.code,
            client_name=args.client_name,
            fallback=args.fallback,
        )
    except AuthError as exc:
        print(f"auth failed: {exc}", file=sys.stderr)
        return 2

    if args.print_only:
        print(json.dumps({"provider": session.provider, **session.to_wire()}))
        return 0

    try:
        reply = control.apply_session(
            session,
            host=args.host,
            port=args.port,
        )
    except control.ControlError as exc:
        print(f"switch failed: {exc}", file=sys.stderr)
        return 3

    print(
        f"switched to {session.username} "
        f"({session.provider}) via {reply.get('strategy', 'unknown')}"
    )
    return 0


def _default_agent_jar() -> Optional[str]:
    # The build drops the jar next to the agent sources.
    candidate = (
        Path(__file__).resolve().parents[2] / "agent" / "session-agent.jar"
    )
    return str(candidate) if candidate.exists() else None


def _cmd_attach(args: argparse.Namespace) -> int:
    jar = args.jar or _default_agent_jar()
    if not jar:
        print(
            "agent jar not found; build it first (agent/build.sh) "
            "or pass --jar",
            file=sys.stderr,
        )
        return 2

    cmd = [
        args.java,
        "-jar",
        jar,
        str(args.pid),
        str(args.port),
    ]
    try:
        completed = subprocess.run(cmd, check=False)
    except FileNotFoundError:
        print(f"java executable not found: {args.java}", file=sys.stderr)
        return 2
    return completed.returncode


def _cmd_ping(args: argparse.Namespace) -> int:
    alive = control.ping(host=args.host, port=args.port)
    print("agent is listening" if alive else "no agent on control port")
    return 0 if alive else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mc_reauth",
        description="Re-authenticate / switch Minecraft account at runtime.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    switch = sub.add_parser("switch", help="authenticate and apply live")
    switch.add_argument("--username", "-u", required=True)
    switch.add_argument(
        "--password",
        "-p",
        help=f"password (else ${ENV_PASSWORD} or an interactive prompt)",
    )
    switch.add_argument(
        "--provider",
        choices=PRIORITY,
        default=None,
        help="force a provider; default is the priority provider (mcskill)",
    )
    switch.add_argument(
        "--fallback",
        action="store_true",
        help="if the priority provider fails, try the others in order",
    )
    switch.add_argument("--code", help="MFA / OTP code, if required")
    switch.add_argument(
        "--client-name",
        help="GribLand client name (required for the gribland provider)",
    )
    switch.add_argument("--host", default=control.DEFAULT_HOST)
    switch.add_argument("--port", type=int, default=control.DEFAULT_PORT)
    switch.add_argument(
        "--print-only",
        action="store_true",
        help="print the resolved session as JSON instead of applying it",
    )
    switch.set_defaults(func=_cmd_switch)

    attach = sub.add_parser(
        "attach",
        help="attach the agent to an already-running Minecraft process",
    )
    attach.add_argument("--pid", type=int, required=True)
    attach.add_argument("--port", type=int, default=control.DEFAULT_PORT)
    attach.add_argument("--jar", help="path to session-agent.jar")
    attach.add_argument("--java", default="java")
    attach.set_defaults(func=_cmd_attach)

    ping = sub.add_parser("ping", help="check whether an agent is listening")
    ping.add_argument("--host", default=control.DEFAULT_HOST)
    ping.add_argument("--port", type=int, default=control.DEFAULT_PORT)
    ping.set_defaults(func=_cmd_ping)

    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
