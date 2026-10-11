"""Example: switch the running Minecraft client to another account.

Run the Minecraft client (your admin tool injects reauth-x64.dll /
reauth-x86.dll into its javaw.exe), then call this to re-authenticate the
live client -- no restart.

    python examples/switch_account.py mcskill admin_login

The password is taken from the MC_REAUTH_PASSWORD environment variable, or
prompted for interactively.

This is the programmatic equivalent of:

    python -m mc_reauth switch --provider mcskill --username admin_login
"""

import os
import sys

# Make the sibling package importable when run straight from the repo.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from mc_reauth import ControlError, apply_session, authenticate  # noqa: E402
from mc_reauth.session import AuthError  # noqa: E402


def main(argv):
    if len(argv) < 3:
        print(
            "usage: switch_account.py <mcskill|gribland> <username> "
            "[client_name]",
            file=sys.stderr,
        )
        return 1

    provider = argv[1]
    username = argv[2]
    client_name = argv[3] if len(argv) > 3 else None
    password = os.environ.get("MC_REAUTH_PASSWORD")
    if not password:
        import getpass

        password = getpass.getpass("Password: ")

    try:
        session = authenticate(
            username=username,
            password=password,
            provider=provider,
            client_name=client_name,
        )
    except AuthError as exc:
        print(f"auth failed: {exc}", file=sys.stderr)
        return 2

    try:
        reply = apply_session(session, port=5151)
    except ControlError as exc:
        print(f"could not reach / update the client: {exc}", file=sys.stderr)
        return 3

    print(
        f"ok: client is now {session.username} "
        f"({session.provider}), strategy={reply.get('strategy')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
