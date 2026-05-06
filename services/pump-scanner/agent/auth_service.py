"""
R46 — 账户认证服务

helpers:
  - hash_password(plain) → bcrypt hash
  - verify_password(plain, hash) → bool
  - create_jwt(user_id, email, expires_days=7) → token str
  - verify_jwt(token) → payload dict (失败抛 jwt.PyJWTError)
  - verify_google_id_token(id_token) → {sub, email, name, picture, ...} (失败抛 ValueError)

JWT secret 来源:env AUTH_JWT_SECRET(GA 必须配)
Google 验证:Google 公钥(免 google credentials,只配 GOOGLE_CLIENT_ID env)

Python 3.9 兼容。
"""
from __future__ import annotations
import logging
import os
import time
from typing import Any, Dict, Optional

import bcrypt
import jwt as pyjwt

log = logging.getLogger(__name__)

JWT_SECRET = os.getenv("AUTH_JWT_SECRET", "")
JWT_ALGO = "HS256"
JWT_DEFAULT_DAYS = 7


def _get_google_client_id() -> str:
    """惰性读取 GOOGLE_CLIENT_ID(测试时可改 env)"""
    return os.getenv("GOOGLE_CLIENT_ID", "")


def _get_google_client_secret() -> str:
    """R46.1 — 后端 OAuth code-exchange 用(redirect flow)"""
    return os.getenv("GOOGLE_CLIENT_SECRET", "")


async def exchange_google_code(code: str, redirect_uri: str) -> Dict[str, Any]:
    """R46.1 — Authorization Code Flow:用 code + client_secret 换 ID token + access_token。

    返 dict:{id_token, access_token, expires_in, token_type, scope, ...}
    任何错误抛 ValueError(caller 拦截返 401)。
    """
    client_id = _get_google_client_id()
    client_secret = _get_google_client_secret()
    if not client_id or not client_secret:
        raise RuntimeError("GOOGLE_CLIENT_ID 或 GOOGLE_CLIENT_SECRET env 未配")

    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            data = await resp.json()
            if resp.status != 200 or "error" in data:
                raise ValueError(
                    f"Google token exchange 失败: {data.get('error_description') or data.get('error') or resp.status}"
                )
            return data


# ── bcrypt 密码 ─────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """bcrypt 加密密码,默认 cost factor 12(~250ms 单核)"""
    if not plain:
        raise ValueError("空密码")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    """验证密码;失败返 False(不抛)"""
    if not plain or not password_hash:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception as e:
        log.warning("[auth] verify_password fail: %s", e)
        return False


# ── 自建 JWT ────────────────────────────────────────────────

def create_jwt(
    user_id: str,
    email: str,
    expires_days: int = JWT_DEFAULT_DAYS,
    provider: str = "email",
) -> str:
    """签 HS256 JWT。
    payload: {sub: user_id, email, exp, iat, provider}
    """
    if not JWT_SECRET:
        raise RuntimeError("AUTH_JWT_SECRET env 未配,GA 前必须设置")
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + expires_days * 86400,
        "provider": provider,
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def verify_jwt(token: str) -> Dict[str, Any]:
    """验证 JWT;过期/签名错抛 PyJWTError"""
    if not JWT_SECRET:
        raise RuntimeError("AUTH_JWT_SECRET env 未配")
    return pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])


# ── Google OAuth ID token 验证 ──────────────────────────────

def verify_google_id_token(id_token_str: str) -> Dict[str, Any]:
    """验证 Google ID token,返 user info dict。
    失败抛 ValueError(明显错误,caller 拦截返 401)。

    返字段(Google ID token 标准):
      sub:Google 用户 ID(永久不变)
      email:用户邮箱
      email_verified:邮箱是否经 Google 验证
      name / given_name / family_name / picture
      iss / aud / exp / iat
    """
    client_id = _get_google_client_id()
    if not client_id:
        raise RuntimeError("GOOGLE_CLIENT_ID env 未配")
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
    except ImportError as e:
        raise RuntimeError(f"google-auth 未装: {e}")

    # google-auth 会:
    # 1. 拉 Google 公钥(自动 cache)
    # 2. 验签
    # 3. 验 aud == GOOGLE_CLIENT_ID
    # 4. 验 exp 未过期
    # 5. 验 iss == accounts.google.com / https://accounts.google.com
    request_obj = google_requests.Request()
    info = google_id_token.verify_oauth2_token(
        id_token_str, request_obj, client_id,
    )
    return info


# ── 测试用:reset cache ─────────────────────────────────────

def _reset_for_test():
    """单测用 — 清缓存(目前只是 noop,留给后续 cache 用)"""
    pass
