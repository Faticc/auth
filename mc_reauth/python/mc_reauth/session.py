"""The provider-neutral game session that gets injected into Minecraft.

Every supported auth backend is reduced to the three values the Minecraft
client actually needs to authenticate a server join (the Yggdrasil
`joinServer` / `hasJoined` handshake): the account UUID, the session access
token and the in-game username.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GameSession:
    uuid: str
    access_token: str
    username: str
    provider: str = ""

    def to_wire(self) -> dict:
        """The exact JSON object the Java agent expects on its control port."""
        return {
            "uuid": self.uuid,
            "accessToken": self.access_token,
            "username": self.username,
        }


class AuthError(Exception):
    """A login attempt against one provider failed.

    `code` mirrors the `code` field the underlying auth libraries return
    (e.g. ``MFA``, ``UNAUTHENTICATED``, ``UNAVAILABLE``) so the caller can
    react to it programmatically.
    """

    def __init__(
        self,
        message: str,
        provider: str,
        code: Optional[str] = None,
    ) -> None:
        super().__init__(f"[{provider}] {code or 'ERROR'}: {message}")
        self.message = message
        self.provider = provider
        self.code = code
