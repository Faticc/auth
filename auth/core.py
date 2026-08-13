import grpc
from mcproto import AUTH_STUB, proto
from .models import (
    Profile,
    SessionId,
    AuthResult,
    SessionCheckResult,
    SessionCheckResult
)


def send_request(username: str, password: str) -> AuthResult:
    request = proto.auth_pb2.LoginRequest( # pyright: ignore[reportAttributeAccessIssue]
        username=username,
        password=password
    )

    try:
        response = AUTH_STUB.Login(request)

        if response.HasField("session_data"):
            session = response.session_data
            profile = Profile(
                uuid=session.profile.uuid,
                username=session.profile.username,
                skin_url=session.profile.skin_url
            )
            sessionId = SessionId(session.id)
            return AuthResult(ok=True, sessionId=sessionId, profile=profile)

        if response.HasField("mfa_required"):
            return AuthResult(ok=False, error="MFA required", code="MFA")

        return AuthResult(ok=False, error="Unknown response", code="UNKNOWN")

    except grpc.RpcError as e:
        return AuthResult(ok=False, error=e.details(), code=e.code().name)
    

def check_session(session_id: str) -> SessionCheckResult:
    request = proto.auth_pb2.GetProfileRequest() # pyright: ignore[reportAttributeAccessIssue]

    try:
        response = AUTH_STUB.GetProfile(
            request,
            metadata=[("session", session_id)]
        )

        profile = Profile(
            uuid=response.profile.uuid,
            username=response.profile.username,
            skin_url=response.profile.skin_url
        )

        return SessionCheckResult(
            valid=True,
            profile=profile
        )

    except grpc.RpcError as e:
        return SessionCheckResult(
            valid=False,
            error=e.details(),
            code=e.code().name
        )
