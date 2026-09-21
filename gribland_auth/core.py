import json
import urllib.error
import urllib.request
from typing import Any, Optional, Tuple

from .models import (
    Profile,
    SessionId,
    AuthResult,
    SessionCheckResult,
    GameSession,
    GameSessionResult
)

# The launcher tries these hosts in order and uses the first one that answers.
DOMAINS = ("launcher.gribland.net", "launcher-cf.gribland.net")
USER_AGENT = "GribLand"
TIMEOUT = 10

OTP_MARKER = ".otp_"
OTP_INCORRECT = "messages.login.otp_incorrect"

_STATUS_CODES = {
    400: "INVALID_ARGUMENT",
    401: "UNAUTHENTICATED",
    403: "PERMISSION_DENIED",
    404: "NOT_FOUND",
    422: "INVALID_ARGUMENT",
    429: "RESOURCE_EXHAUSTED",
}


class _Unreachable(Exception):
    pass


def _pick(data: Any, *names: str) -> Any:
    if not isinstance(data, dict):
        return None
    for name in names:
        if data.get(name) is not None:
            return data[name]
    return None


def _request(
    method: str,
    path: str,
    body: Optional[dict] = None,
    token: Optional[str] = None
) -> Tuple[int, Any]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json"
    }
    payload = None

    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"

    if token:
        headers["Authorization"] = f"Bearer {token}"

    last_error: Optional[BaseException] = None

    for domain in DOMAINS:
        request = urllib.request.Request(
            f"https://{domain}{path}",
            data=payload,
            headers=headers,
            method=method
        )

        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return response.status, _parse(response.read())
        except urllib.error.HTTPError as e:
            return e.code, _parse(e.read())
        except (urllib.error.URLError, OSError) as e:
            last_error = e

    raise _Unreachable(str(last_error))


def _parse(raw: bytes) -> Any:
    text = raw.decode("utf-8", errors="replace")

    try:
        return json.loads(text)
    except ValueError:
        return {"message": text.strip()[:200]}


def _error_text(data: Any, status: int) -> str:
    if isinstance(data, dict):
        message = _pick(data, "message", "error")
        if isinstance(message, str) and message:
            return message
    return f"HTTP {status}"


def _error_code(status: int) -> str:
    if status in _STATUS_CODES:
        return _STATUS_CODES[status]
    if status >= 500:
        return "UNAVAILABLE"
    return f"HTTP_{status}"


def _profile(data: Any) -> Optional[Profile]:
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        data = data["data"]

    uuid = _pick(data, "uuid")
    username = _pick(data, "name", "username")

    if uuid is None or username is None:
        return None

    group = _pick(data, "group")
    if isinstance(group, dict):
        group = _pick(group, "name")

    return Profile(
        uuid=str(uuid),
        username=str(username),
        group=group if isinstance(group, str) else None
    )


def _fetch_profile(access_token: str) -> Tuple[int, Any]:
    return _request("GET", "/user/fetch", token=access_token)


def send_request(
    username: str,
    password: str,
    code: Optional[str] = None,
    client_name: Optional[str] = None
) -> AuthResult:
    """Log in and, when `client_name` is given, also perform step 2 (the
    JWT -> per-client game session exchange) so the returned result already
    carries a ready-to-use `game_session` (see `create_game_session`).

    `client_name` must match one of the launcher's client names, e.g.
    "SKYDRIVE-HITECH-TEST" or "OneBlockProd". Omit it to get the JWT only.
    """
    try:
        status, data = _request(
            "POST",
            "/authentication/login",
            body={"ident": username, "password": password, "code": code}
        )
    except _Unreachable as e:
        return AuthResult(ok=False, error=str(e), code="UNAVAILABLE")

    if status != 200:
        message = _error_text(data, status)

        if OTP_MARKER in message:
            if message == OTP_INCORRECT:
                return AuthResult(ok=False, error=message, code="MFA_INVALID")
            return AuthResult(ok=False, error="MFA required", code="MFA")

        return AuthResult(ok=False, error=message, code=_error_code(status))

    access_token = _pick(data, "accessToken", "access_token")
    if not isinstance(access_token, str) or not access_token:
        return AuthResult(ok=False, error="Unknown response", code="UNKNOWN")

    expires_in = _pick(data, "expiresIn", "expires_in")
    result = AuthResult(
        ok=True,
        sessionId=SessionId(access_token),
        refresh_token=_pick(data, "refreshToken", "refresh_token"),
        expires_in=expires_in if isinstance(expires_in, int) else None
    )

    try:
        status, data = _fetch_profile(access_token)
    except _Unreachable:
        pass
    else:
        if status == 200:
            result.profile = _profile(data)

    if client_name:
        game = create_game_session(access_token, client_name)

        if game.ok:
            result.game_session = game.session
        else:
            # Login worked but the game-session exchange did not: report
            # failure, but keep sessionId/profile so the caller can retry
            # create_game_session() directly instead of logging in again.
            result.ok = False
            result.error = game.error
            result.code = game.code

    return result


def check_session(session_id: str) -> SessionCheckResult:
    try:
        status, data = _fetch_profile(session_id)
    except _Unreachable as e:
        return SessionCheckResult(valid=False, error=str(e), code="UNAVAILABLE")

    if status != 200:
        return SessionCheckResult(
            valid=False,
            error=_error_text(data, status),
            code=_error_code(status)
        )

    profile = _profile(data)
    if profile is None:
        return SessionCheckResult(valid=False, error="Unknown response", code="UNKNOWN")

    return SessionCheckResult(valid=True, profile=profile)


def create_game_session(access_token: str, client_name: str) -> GameSessionResult:
    """Exchange a login JWT for a per-client game session (the 64-hex token
    the launcher hands to the Minecraft process for joinServer/hasJoined).
    """
    try:
        status, data = _request(
            "GET",
            f"/minecraft/createSession/{client_name}",
            token=access_token
        )
    except _Unreachable as e:
        return GameSessionResult(ok=False, error=str(e), code="UNAVAILABLE")

    if status != 200:
        return GameSessionResult(
            ok=False,
            error=_error_text(data, status),
            code=_error_code(status)
        )

    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        data = data["data"]

    uuid = _pick(data, "uuid")
    session_token = _pick(data, "accessToken", "access_token")
    username = _pick(data, "username", "name")

    if uuid is None or session_token is None or username is None:
        return GameSessionResult(ok=False, error="Unknown response", code="UNKNOWN")

    return GameSessionResult(
        ok=True,
        session=GameSession(
            uuid=str(uuid),
            access_token=str(session_token),
            username=str(username)
        )
    )
