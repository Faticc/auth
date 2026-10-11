"""Turn account credentials into a :class:`GameSession`.

This is a thin adapter over the two auth packages that already live in this
repository:

* ``auth``          -> MCSkill  (gRPC)       -- the priority provider
* ``gribland_auth`` -> GribLand (launcher HTTP API)

MCSkill is tried first by design. GribLand is only contacted when it is
explicitly selected, or when ``fallback=True`` is passed, so a password is
never sent to a second ecosystem behind the user's back.
"""

from typing import Callable, Dict, List, Optional

from .session import AuthError, GameSession

MCSKILL = "mcskill"
GRIBLAND = "gribland"

# The priority order. MCSkill first, as requested.
PRIORITY: List[str] = [MCSKILL, GRIBLAND]


def _login_mcskill(
    username: str,
    password: str,
    code: Optional[str] = None,
    client_name: Optional[str] = None,
) -> GameSession:
    # Imported lazily so that using only GribLand does not require the
    # gRPC / mcproto stack that the MCSkill client pulls in.
    from auth import send_request

    result = send_request(username, password)

    if not result.ok or result.sessionId is None or result.profile is None:
        raise AuthError(
            message=result.error or "login failed",
            provider=MCSKILL,
            code=result.code,
        )

    return GameSession(
        uuid=result.profile.uuid,
        access_token=result.sessionId.value,
        username=result.profile.username,
        provider=MCSKILL,
    )


def _login_gribland(
    username: str,
    password: str,
    code: Optional[str] = None,
    client_name: Optional[str] = None,
) -> GameSession:
    import gribland_auth

    if not client_name:
        raise AuthError(
            message=(
                "client_name is required for GribLand "
                "(e.g. 'SKYDRIVE-HITECH-TEST' or 'OneBlockProd')"
            ),
            provider=GRIBLAND,
            code="INVALID_ARGUMENT",
        )

    result = gribland_auth.send_request(
        username,
        password,
        code=code,
        client_name=client_name,
    )

    if not result.ok or result.game_session is None:
        raise AuthError(
            message=result.error or "login failed",
            provider=GRIBLAND,
            code=result.code,
        )

    game = result.game_session
    return GameSession(
        uuid=game.uuid,
        access_token=game.access_token,
        username=game.username,
        provider=GRIBLAND,
    )


Provider = Callable[..., GameSession]

PROVIDERS: Dict[str, Provider] = {
    MCSKILL: _login_mcskill,
    GRIBLAND: _login_gribland,
}


def authenticate(
    username: str,
    password: str,
    provider: Optional[str] = None,
    code: Optional[str] = None,
    client_name: Optional[str] = None,
    fallback: bool = False,
) -> GameSession:
    """Authenticate and return a ready-to-inject :class:`GameSession`.

    * ``provider=None`` uses the priority provider (MCSkill). With
      ``fallback=True`` the remaining providers are tried in priority
      order if MCSkill fails.
    * ``provider="mcskill"`` / ``"gribland"`` forces a single provider;
      ``fallback`` is then ignored.

    Raises :class:`AuthError` (the last failure) if no provider succeeds.
    """
    if provider is not None:
        key = provider.lower()
        if key not in PROVIDERS:
            raise AuthError(
                message=f"unknown provider '{provider}'",
                provider=provider,
                code="INVALID_ARGUMENT",
            )
        order = [key]
    else:
        order = PRIORITY if fallback else [PRIORITY[0]]

    last: Optional[AuthError] = None
    for key in order:
        try:
            return PROVIDERS[key](
                username,
                password,
                code=code,
                client_name=client_name,
            )
        except AuthError as exc:
            last = exc
            # Never silently forward a password to the next ecosystem when
            # the user asked for a specific provider.
            if provider is not None:
                raise

    assert last is not None
    raise last
