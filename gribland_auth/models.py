from dataclasses import dataclass
from typing import Optional


@dataclass
class Profile:
    uuid: str
    username: str
    skin_url: str = ""
    group: Optional[str] = None


@dataclass
class SessionId:
    value: str

    def is_valid(self):
        from .core import check_session
        return check_session(self.value)


@dataclass
class AuthResult:
    ok: bool
    sessionId: Optional[SessionId] = None
    profile: Optional[Profile] = None
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    error: Optional[str] = None
    code: Optional[str] = None


@dataclass
class SessionCheckResult:
    valid: bool
    profile: Optional[Profile] = None
    error: Optional[str] = None
    code: Optional[str] = None
