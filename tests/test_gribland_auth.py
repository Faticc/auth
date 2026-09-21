import io
import json
import unittest
import urllib.error
from unittest import mock

from gribland_auth import check_session, create_game_session, send_request


class FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = json.dumps(body).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(status, body):
    return urllib.error.HTTPError(
        "https://x", status, "err", {}, io.BytesIO(json.dumps(body).encode())
    )


TOKEN = {"accessToken": "tok", "refreshToken": "ref", "expiresIn": 3600}
USER = {"id": 1, "name": "Steve", "uuid": "abc", "group": {"name": "player"}}


class LoginTests(unittest.TestCase):
    def test_success_fetches_profile(self):
        calls = []

        def fake(request, timeout):
            calls.append(request)
            if request.full_url.endswith("/authentication/login"):
                return FakeResponse(200, TOKEN)
            return FakeResponse(200, USER)

        with mock.patch("urllib.request.urlopen", fake):
            result = send_request("Steve", "pw")

        self.assertTrue(result.ok)
        self.assertEqual(result.sessionId.value, "tok")
        self.assertEqual(result.refresh_token, "ref")
        self.assertEqual(result.profile.username, "Steve")
        self.assertEqual(result.profile.group, "player")
        self.assertEqual(
            json.loads(calls[0].data),
            {"ident": "Steve", "password": "pw", "code": None},
        )
        self.assertEqual(calls[1].get_header("Authorization"), "Bearer tok")

    def test_login_returns_game_session_when_client_given(self):
        urls = []

        def fake(request, timeout):
            urls.append(request.full_url)
            if request.full_url.endswith("/authentication/login"):
                return FakeResponse(200, TOKEN)
            if "/minecraft/createSession/" in request.full_url:
                return FakeResponse(200, {"uuid": "abc",
                                          "accessToken": "f" * 64,
                                          "username": "Steve"})
            return FakeResponse(200, USER)

        with mock.patch("urllib.request.urlopen", fake):
            result = send_request("Steve", "pw", client_name="OneBlockProd")

        self.assertTrue(result.ok)
        self.assertEqual(result.game_session.access_token, "f" * 64)
        self.assertEqual(result.game_session.username, "Steve")
        self.assertTrue(urls[-1].endswith("/minecraft/createSession/OneBlockProd"))

    def test_login_without_client_skips_exchange(self):
        urls = []

        def fake(request, timeout):
            urls.append(request.full_url)
            if request.full_url.endswith("/authentication/login"):
                return FakeResponse(200, TOKEN)
            return FakeResponse(200, USER)

        with mock.patch("urllib.request.urlopen", fake):
            result = send_request("Steve", "pw")

        self.assertTrue(result.ok)
        self.assertIsNone(result.game_session)
        self.assertFalse(any("createSession" in u for u in urls))

    def test_exchange_failure_marks_login_failed_but_keeps_jwt(self):
        def fake(request, timeout):
            if request.full_url.endswith("/authentication/login"):
                return FakeResponse(200, TOKEN)
            if "/minecraft/createSession/" in request.full_url:
                raise http_error(400, {"message": "unknown client"})
            return FakeResponse(200, USER)

        with mock.patch("urllib.request.urlopen", fake):
            result = send_request("Steve", "pw", client_name="Nope")

        self.assertFalse(result.ok)
        self.assertEqual(result.code, "INVALID_ARGUMENT")
        self.assertEqual(result.error, "unknown client")
        self.assertEqual(result.sessionId.value, "tok")
        self.assertIsNone(result.game_session)

    def test_snake_case_token(self):
        body = {"access_token": "tok", "refresh_token": "ref", "expires_in": 5}

        def fake(request, timeout):
            if request.full_url.endswith("/authentication/login"):
                return FakeResponse(200, body)
            raise http_error(500, {})

        with mock.patch("urllib.request.urlopen", fake):
            result = send_request("Steve", "pw")

        self.assertTrue(result.ok)
        self.assertEqual(result.sessionId.value, "tok")
        self.assertEqual(result.expires_in, 5)
        self.assertIsNone(result.profile)

    def test_mfa_required(self):
        err = http_error(422, {"message": "messages.login.otp_required"})
        with mock.patch("urllib.request.urlopen", side_effect=err):
            result = send_request("Steve", "pw")
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "MFA")

    def test_mfa_incorrect(self):
        err = http_error(422, {"message": "messages.login.otp_incorrect"})
        with mock.patch("urllib.request.urlopen", side_effect=err):
            result = send_request("Steve", "pw", code="000000")
        self.assertEqual(result.code, "MFA_INVALID")

    def test_bad_credentials(self):
        err = http_error(401, {"message": "bad credentials"})
        with mock.patch("urllib.request.urlopen", side_effect=err):
            result = send_request("Steve", "pw")
        self.assertEqual((result.ok, result.code, result.error),
                         (False, "UNAUTHENTICATED", "bad credentials"))

    def test_falls_back_to_second_domain(self):
        hosts = []

        def fake(request, timeout):
            hosts.append(request.full_url.split("/")[2])
            if len(hosts) == 1:
                raise urllib.error.URLError("down")
            return FakeResponse(200, USER)

        with mock.patch("urllib.request.urlopen", fake):
            result = check_session("tok")

        self.assertTrue(result.valid)
        self.assertEqual(hosts, ["launcher.gribland.net", "launcher-cf.gribland.net"])

    def test_all_domains_down(self):
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError("down")):
            result = send_request("Steve", "pw")
        self.assertEqual(result.code, "UNAVAILABLE")


class SessionTests(unittest.TestCase):
    def test_valid(self):
        with mock.patch("urllib.request.urlopen",
                        return_value=FakeResponse(200, USER)):
            result = check_session("tok")
        self.assertTrue(result.valid)
        self.assertEqual(result.profile.uuid, "abc")

    def test_invalid(self):
        err = http_error(401, {"message": "Unauthenticated."})
        with mock.patch("urllib.request.urlopen", side_effect=err):
            result = check_session("bad")
        self.assertEqual((result.valid, result.code),
                         (False, "UNAUTHENTICATED"))


GAME = {"uuid": "abc", "accessToken": "f" * 64, "username": "Steve"}


class GameSessionTests(unittest.TestCase):
    def test_success(self):
        calls = []

        def fake(request, timeout):
            calls.append(request)
            return FakeResponse(200, GAME)

        with mock.patch("urllib.request.urlopen", fake):
            result = create_game_session("jwt", "SKYDRIVE-HITECH-TEST")

        self.assertTrue(result.ok)
        self.assertEqual(result.session.access_token, "f" * 64)
        self.assertEqual(result.session.username, "Steve")
        self.assertEqual(calls[0].get_method(), "GET")
        self.assertTrue(calls[0].full_url.endswith(
            "/minecraft/createSession/SKYDRIVE-HITECH-TEST"))
        self.assertEqual(calls[0].get_header("Authorization"), "Bearer jwt")
        self.assertIsNone(calls[0].data)

    def test_unauthorized(self):
        err = http_error(401, {"message": "Unauthenticated."})
        with mock.patch("urllib.request.urlopen", side_effect=err):
            result = create_game_session("bad", "OneBlockProd")
        self.assertEqual((result.ok, result.code),
                         (False, "UNAUTHENTICATED"))

    def test_incomplete_response(self):
        with mock.patch("urllib.request.urlopen",
                        return_value=FakeResponse(200, {"uuid": "abc"})):
            result = create_game_session("jwt", "OneBlockProd")
        self.assertEqual((result.ok, result.code), (False, "UNKNOWN"))

    def test_unreachable(self):
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError("down")):
            result = create_game_session("jwt", "OneBlockProd")
        self.assertEqual(result.code, "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
