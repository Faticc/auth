import grpc
import auth.auth_pb2 as auth_pb2
import auth.auth_pb2_grpc as auth_pb2_grpc

SERVER = "launchernew.mcskill.ru:443"


class Profile:
    def __init__(self, uuid: str, username: str, skin_url: str):
        self.uuid = uuid
        self.username = username
        self.skin_url = skin_url


def send_request(username: str, password: str):
    channel = grpc.secure_channel(SERVER, grpc.ssl_channel_credentials())
    stub = auth_pb2_grpc.AuthServiceStub(channel)

    request = auth_pb2.LoginRequest(
        username=username,
        password=password
    )

    try:
        response = stub.Login(request)

        # Успешная авторизация
        if response.HasField("session_data"):
            session = response.session_data
            profile = Profile(
                uuid=session.profile.uuid,
                username=session.profile.username,
                skin_url=session.profile.skin_url
            )
            return profile, session.id

        # MFA
        if response.HasField("mfa_required"):
            return {"error": "MFA required", "code": "MFA"}

        return {"error": "Unknown response", "code": "UNKNOWN"}

    except grpc.RpcError as e:
        
        return {
            "error": e.details(),
            "code": e.code().name
        }

if __name__ == "__main__":
    username = input("Username: ")
    password = input("Password: ")

    result = send_request(username, password)
    print(result)