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
from typing import Any, Dict, List, Optional

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
    """bcrypt 加密密码。
    R46.2:cost factor 10(服务器单核 ~60-100ms,登录响应快 4 倍)。
    OWASP 2023 推荐最低 10 — 攻击者 GPU 暴破 10/12 都难。
    """
    if not plain:
        raise ValueError("空密码")
    salt = bcrypt.gensalt(rounds=10)
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

def _get_google_audiences() -> List[str]:
    """返所有合法 audience(Web client + iOS client + Android client 可共存)。

    R47 P3 — 多平台 OAuth client 必须各自独立(Google 强制要求按平台分类型),
    每个 client 颁发的 ID token 的 aud claim 是不同的 client ID。
    我们必须接受所有合法 audience。

    Env 优先级:
      GOOGLE_CLIENT_IDS  — 逗号分隔多个 client ID(推荐)
      GOOGLE_CLIENT_ID   — 单个(向后兼容,通常是 Web client)
      GOOGLE_IOS_CLIENT_ID — iOS client(显式追加)
    """
    out: List[str] = []
    multi = os.getenv("GOOGLE_CLIENT_IDS", "").strip()
    if multi:
        out += [x.strip() for x in multi.split(",") if x.strip()]
    single = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if single and single not in out:
        out.append(single)
    ios = os.getenv("GOOGLE_IOS_CLIENT_ID", "").strip()
    if ios and ios not in out:
        out.append(ios)
    android = os.getenv("GOOGLE_ANDROID_CLIENT_ID", "").strip()
    if android and android not in out:
        out.append(android)
    return out


def verify_google_id_token(id_token_str: str) -> Dict[str, Any]:
    """验证 Google ID token,返 user info dict。
    失败抛 ValueError(明显错误,caller 拦截返 401)。

    R47 P3 — 接受多 audience(Web + iOS + Android 各自独立 OAuth client)。
    依次尝试每个允许的 audience,任意一个验过即返。
    """
    audiences = _get_google_audiences()
    if not audiences:
        raise RuntimeError("GOOGLE_CLIENT_ID / GOOGLE_CLIENT_IDS env 未配")
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
    except ImportError as e:
        raise RuntimeError(f"google-auth 未装: {e}")

    request_obj = google_requests.Request()
    last_err: Optional[Exception] = None
    for aud in audiences:
        try:
            info = google_id_token.verify_oauth2_token(
                id_token_str, request_obj, aud,
            )
            return info
        except ValueError as e:
            last_err = e
            continue
    # 全部 audience 都没过
    raise ValueError(f"Google ID token audience 不匹配任何配置的 client(尝试 {len(audiences)} 个): {last_err}")


# ── 测试用:reset cache ─────────────────────────────────────

def _reset_for_test():
    """单测用 — 清缓存(目前只是 noop,留给后续 cache 用)"""
    pass
