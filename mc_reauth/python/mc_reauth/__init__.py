"""mc_reauth -- hot-swap the Minecraft account of a running client.

Authenticate against MCSkill (priority) or GribLand using the auth packages
already in this repository, then inject the resulting game session into a
live Minecraft process through a small Java agent -- no game restart, no
re-opening the administration tool.
"""

from .control import ControlError, apply_session, ping
from .providers import GRIBLAND, MCSKILL, PRIORITY, authenticate
from .session import AuthError, GameSession

__all__ = [
    "authenticate",
    "apply_session",
    "ping",
    "GameSession",
    "AuthError",
    "ControlError",
    "MCSKILL",
    "GRIBLAND",
    "PRIORITY",
]
