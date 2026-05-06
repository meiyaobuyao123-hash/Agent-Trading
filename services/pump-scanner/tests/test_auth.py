"""
R46 — 后端 auth_service 单测

覆盖:
  - hash_password / verify_password round trip
  - JWT sign / verify / 过期 / 错 secret
  - Google ID token 验证(mock google.oauth2.id_token.verify_oauth2_token)

跑法:
  cd services/pump-scanner
  python3 -m pytest tests/test_auth.py -v
"""
from __future__ import annotations
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def with_jwt_secret():
    """配 AUTH_JWT_SECRET env"""
    old = os.environ.get("AUTH_JWT_SECRET")
    os.environ["AUTH_JWT_SECRET"] = "test_secret_for_unit_test_xxx"
    # 重新 import 让模块读 env
    import importlib
    import agent.auth_service as mod
    importlib.reload(mod)
    yield mod
    if old is not None:
        os.environ["AUTH_JWT_SECRET"] = old
    else:
        os.environ.pop("AUTH_JWT_SECRET", None)
    importlib.reload(mod)


@pytest.fixture
def no_jwt_secret():
    old = os.environ.get("AUTH_JWT_SECRET")
    os.environ.pop("AUTH_JWT_SECRET", None)
    import importlib
    import agent.auth_service as mod
    importlib.reload(mod)
    yield mod
    if old is not None:
        os.environ["AUTH_JWT_SECRET"] = old
    importlib.reload(mod)


# ═════════════════════════════════════════════════════════
# bcrypt
# ═════════════════════════════════════════════════════════

class TestPassword:

    def test_hash_verify_round_trip(self):
        from agent.auth_service import hash_password, verify_password
        plain = "MyP@ssword123"
        h = hash_password(plain)
        assert h.startswith("$2")  # bcrypt 格式
        assert verify_password(plain, h) is True

    def test_wrong_password_fails(self):
        from agent.auth_service import hash_password, verify_password
        h = hash_password("right")
        assert verify_password("wrong", h) is False

    def test_empty_inputs_fail(self):
        from agent.auth_service import verify_password
        assert verify_password("", "any") is False
        assert verify_password("any", "") is False

    def test_hash_empty_raises(self):
        from agent.auth_service import hash_password
        with pytest.raises(ValueError):
            hash_password("")

    def test_different_hashes_for_same_password(self):
        """salt 随机 → 同密码两次 hash 不同"""
        from agent.auth_service import hash_password
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2


# ═════════════════════════════════════════════════════════
# JWT
# ═════════════════════════════════════════════════════════

class TestJwt:

    def test_create_verify_round_trip(self, with_jwt_secret):
        token = with_jwt_secret.create_jwt("user-123", "a@b.com", expires_days=7)
        payload = with_jwt_secret.verify_jwt(token)
        assert payload["sub"] == "user-123"
        assert payload["email"] == "a@b.com"
        assert payload["provider"] == "email"
        assert payload["exp"] > int(time.time())

    def test_create_no_secret_raises(self, no_jwt_secret):
        with pytest.raises(RuntimeError) as exc:
            no_jwt_secret.create_jwt("u", "a@b.com")
        assert "AUTH_JWT_SECRET" in str(exc.value)

    def test_verify_no_secret_raises(self, no_jwt_secret):
        with pytest.raises(RuntimeError):
            no_jwt_secret.verify_jwt("any.token.string")

    def test_expired_token_raises(self, with_jwt_secret):
        import jwt as pyjwt
        # 手工签一个过期 token
        old_payload = {"sub": "u", "email": "x@y.com", "exp": int(time.time()) - 100}
        old_token = pyjwt.encode(old_payload, "test_secret_for_unit_test_xxx", algorithm="HS256")
        with pytest.raises(pyjwt.ExpiredSignatureError):
            with_jwt_secret.verify_jwt(old_token)

    def test_wrong_secret_raises(self, with_jwt_secret):
        token = with_jwt_secret.create_jwt("u", "a@b.com")
        # 切 secret
        os.environ["AUTH_JWT_SECRET"] = "different_secret"
        import importlib
        import agent.auth_service as mod
        importlib.reload(mod)
        try:
            import jwt as pyjwt
            with pytest.raises(pyjwt.InvalidSignatureError):
                mod.verify_jwt(token)
        finally:
            os.environ["AUTH_JWT_SECRET"] = "test_secret_for_unit_test_xxx"
            importlib.reload(mod)

    def test_provider_field(self, with_jwt_secret):
        token = with_jwt_secret.create_jwt("u", "a@b.com", provider="google")
        payload = with_jwt_secret.verify_jwt(token)
        assert payload["provider"] == "google"


# ═════════════════════════════════════════════════════════
# Google ID token 验证
# ═════════════════════════════════════════════════════════

class TestGoogleVerify:

    def test_no_client_id_raises(self):
        from agent.auth_service import verify_google_id_token
        old = os.environ.get("GOOGLE_CLIENT_ID")
        os.environ.pop("GOOGLE_CLIENT_ID", None)
        try:
            with pytest.raises(RuntimeError) as exc:
                verify_google_id_token("any_token")
            assert "GOOGLE_CLIENT_ID" in str(exc.value)
        finally:
            if old is not None:
                os.environ["GOOGLE_CLIENT_ID"] = old

    def test_verify_calls_google_oauth2(self):
        """mock google-auth 库,验证 caller 行为"""
        os.environ["GOOGLE_CLIENT_ID"] = "client.apps.googleusercontent.com"
        try:
            from agent.auth_service import verify_google_id_token
            with patch("google.oauth2.id_token.verify_oauth2_token") as mock_verify:
                mock_verify.return_value = {
                    "sub": "google-uid-123",
                    "email": "user@gmail.com",
                    "email_verified": True,
                    "name": "Test User",
                    "picture": "https://lh3.googleusercontent.com/x",
                }
                info = verify_google_id_token("fake_id_token")
            assert info["sub"] == "google-uid-123"
            assert info["email"] == "user@gmail.com"
            assert info["name"] == "Test User"
            mock_verify.assert_called_once()
            # 验证 client_id 传对了
            args = mock_verify.call_args[0]
            assert args[2] == "client.apps.googleusercontent.com"
        finally:
            os.environ.pop("GOOGLE_CLIENT_ID", None)

    def test_invalid_token_raises_value_error(self):
        os.environ["GOOGLE_CLIENT_ID"] = "client.apps.googleusercontent.com"
        try:
            from agent.auth_service import verify_google_id_token
            with patch("google.oauth2.id_token.verify_oauth2_token",
                      side_effect=ValueError("expired token")):
                with pytest.raises(ValueError) as exc:
                    verify_google_id_token("bad_token")
                assert "expired" in str(exc.value)
        finally:
            os.environ.pop("GOOGLE_CLIENT_ID", None)
