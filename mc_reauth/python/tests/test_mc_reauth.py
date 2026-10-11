"""Tests for the mc_reauth Python layer.

The two auth backends (``auth`` for MCSkill, ``gribland_auth`` for GribLand)
are stubbed, so these run without the gRPC stack or any network access.
Run with:  python -m unittest discover -s mc_reauth/python/tests
"""

import json
import socket
import sys
import threading
import types
import unittest
from dataclasses import dataclass
from typing import Optional


def _install_stub_backends(mcskill_ok=True):
    @dataclass
    class Prof:
        uuid: str
        username: str
        skin_url: str = ""

    @dataclass
    class Sid:
        value: str

    @dataclass
    class AuthRes:
        ok: bool
        sessionId: Optional[Sid] = None
        profile: Optional[Prof] = None
        error: Optional[str] = None
        code: Optional[str] = None

    auth = types.ModuleType("auth")

    def mc_send(u, p):
        if mcskill_ok:
            return AuthRes(True, Sid("mcskill-token"), Prof("uuid-mc", u))
        return AuthRes(False, error="bad creds", code="UNAUTHENTICATED")

    auth.send_request = mc_send
    sys.modules["auth"] = auth

    grib = types.ModuleType("gribland_auth")

    @dataclass
    class GS:
        uuid: str
        access_token: str
        username: str

    @dataclass
    class GRes:
        ok: bool
        game_session: Optional[GS] = None
        error: Optional[str] = None
        code: Optional[str] = None

    def gr_send(u, p, code=None, client_name=None):
        assert client_name, "client_name must be forwarded"
        return GRes(True, GS("uuid-gr", "grib-token", u))

    grib.send_request = gr_send
    sys.modules["gribland_auth"] = grib


class ProviderTests(unittest.TestCase):
    def test_priority_default_is_mcskill(self):
        _install_stub_backends(mcskill_ok=True)
        from mc_reauth.providers import authenticate

        s = authenticate("admin", "pw")
        self.assertEqual(s.provider, "mcskill")
        self.assertEqual(s.access_token, "mcskill-token")
        self.assertEqual(s.uuid, "uuid-mc")
        self.assertEqual(s.username, "admin")

    def test_explicit_gribland_maps_game_session(self):
        _install_stub_backends()
        from mc_reauth.providers import authenticate

        s = authenticate("admin", "pw", provider="gribland",
                         client_name="SKYDRIVE-HITECH-TEST")
        self.assertEqual(s.provider, "gribland")
        self.assertEqual(s.access_token, "grib-token")

    def test_gribland_requires_client_name(self):
        _install_stub_backends()
        from mc_reauth.providers import authenticate
        from mc_reauth.session import AuthError

        with self.assertRaises(AuthError) as ctx:
            authenticate("admin", "pw", provider="gribland")
        self.assertEqual(ctx.exception.code, "INVALID_ARGUMENT")

    def test_no_fallback_does_not_leak_to_second_provider(self):
        _install_stub_backends(mcskill_ok=False)
        from mc_reauth.providers import authenticate
        from mc_reauth.session import AuthError

        with self.assertRaises(AuthError) as ctx:
            authenticate("admin", "pw")  # provider=None, fallback=False
        self.assertEqual(ctx.exception.provider, "mcskill")

    def test_fallback_tries_gribland(self):
        _install_stub_backends(mcskill_ok=False)
        from mc_reauth.providers import authenticate

        s = authenticate("admin", "pw", fallback=True,
                         client_name="OneBlockProd")
        self.assertEqual(s.provider, "gribland")

    def test_pinned_provider_ignores_fallback(self):
        _install_stub_backends(mcskill_ok=False)
        from mc_reauth.providers import authenticate
        from mc_reauth.session import AuthError

        with self.assertRaises(AuthError):
            authenticate("admin", "pw", provider="mcskill", fallback=True)

    def test_unknown_provider(self):
        _install_stub_backends()
        from mc_reauth.providers import authenticate
        from mc_reauth.session import AuthError

        with self.assertRaises(AuthError) as ctx:
            authenticate("a", "b", provider="hypixel")
        self.assertEqual(ctx.exception.code, "INVALID_ARGUMENT")


class ControlTests(unittest.TestCase):
    def test_apply_session_roundtrip(self):
        from mc_reauth import control
        from mc_reauth.session import GameSession

        received = {}

        def agent(sock):
            conn, _ = sock.accept()
            data = b""
            while b"\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            received.update(json.loads(data.split(b"\n")[0].decode()))
            conn.sendall(b'{"ok":true,"strategy":"value-shape"}\n')
            conn.close()

        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        port = srv.getsockname()[1]
        srv.listen(1)
        t = threading.Thread(target=agent, args=(srv,))
        t.start()

        gs = GameSession("069a79f444e94726a5befca90e38aaf5",
                         "TOKEN123", "Notch", "mcskill")
        reply = control.apply_session(gs, port=port)
        t.join()
        srv.close()

        self.assertEqual(received, {
            "uuid": "069a79f444e94726a5befca90e38aaf5",
            "accessToken": "TOKEN123",
            "username": "Notch",
        })
        self.assertTrue(reply["ok"])
        self.assertEqual(reply["strategy"], "value-shape")

    def test_control_error_when_no_agent(self):
        from mc_reauth import control
        from mc_reauth.session import GameSession

        gs = GameSession("u", "t", "n", "mcskill")
        with self.assertRaises(control.ControlError):
            control.apply_session(gs, port=1, timeout=0.5)

    def test_ping_negative(self):
        from mc_reauth import control

        self.assertFalse(control.ping(port=1, timeout=0.5))


if __name__ == "__main__":
    unittest.main()
