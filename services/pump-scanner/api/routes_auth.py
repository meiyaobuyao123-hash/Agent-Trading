"""
R46 — 账户认证 API endpoints

- POST /api/auth/register  邮箱+密码注册
- POST /api/auth/login     邮箱+密码登录
- POST /api/auth/google    Google ID token 登录(注册自动 upsert)
- GET  /api/auth/me        Bearer token → 返当前 user info
- POST /api/auth/logout    清 token(客户端层面,服务端 stateless JWT 无需后端清)

存储:本地 PG `users` 表(migration 044)
"""
from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
import re as _re
from pydantic import BaseModel, Field, validator

from agent.auth_service import (
    hash_password, verify_password,
    create_jwt, verify_jwt,
    verify_google_id_token,
)
from api.auth import get_current_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── 请求/响应 ─────────────────────────────────────────────

_EMAIL_RE = _re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _validate_email(v: str) -> str:
    v = (v or "").strip().lower()
    if not _EMAIL_RE.match(v):
        raise ValueError("邮箱格式不正确")
    return v


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=6, max_length=128)
    display_name: Optional[str] = Field(None, max_length=64)

    @validator("email")
    def _email(cls, v):
        return _validate_email(v)


class LoginRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=1, max_length=128)

    @validator("email")
    def _email(cls, v):
        return _validate_email(v)


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(..., min_length=10)
    display_name: Optional[str] = Field(None, max_length=64)


class AuthResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    user_id: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    error: Optional[str] = None


class UserInfo(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    provider: str        # 'email' / 'google'
    created_at: Optional[str] = None


# ── 本地 PG helper ────────────────────────────────────────

def _get_local_db_conn():
    try:
        from local_db import _get_conn
        return _get_conn()
    except ImportError as e:
        raise HTTPException(503, f"本地 DB 不可用: {e}")
    except Exception as e:
        raise HTTPException(503, f"本地 DB 连接失败: {e}")


def _row_to_user_info(row, provider: str = "email") -> dict:
    """psycopg2 row(tuple) → user dict"""
    return {
        "id": str(row[0]),
        "email": row[1],
        "display_name": row[2],
        "avatar_url": row[3],
        "provider": provider,
        "created_at": row[4].isoformat() if row[4] else None,
    }


# ── Endpoints ────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    """邮箱+密码注册。
    - email 已存在 → 400(请用登录)
    - 成功 → 创建用户 + 返 JWT
    """
    pwd_hash = hash_password(req.password)
    conn = _get_local_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (email, password_hash, display_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (email) DO NOTHING
                RETURNING id, email, display_name, avatar_url, created_at
                """,
                (req.email.lower(), pwd_hash, req.display_name),
            )
            row = cur.fetchone()
        conn.commit()
    except Exception as e:
        log.error("[auth/register] DB error: %s", e)
        raise HTTPException(500, f"注册失败: {str(e)[:200]}")

    if not row:
        # 邮箱已存在(ON CONFLICT DO NOTHING 不返行)
        raise HTTPException(400, "邮箱已注册,请直接登录")

    user_id = str(row[0])
    try:
        token = create_jwt(user_id, req.email.lower(), provider="email")
    except RuntimeError as e:
        raise HTTPException(503, str(e))

    return AuthResponse(
        success=True,
        token=token,
        user_id=user_id,
        email=req.email.lower(),
        display_name=req.display_name,
    )


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    """邮箱+密码登录。"""
    conn = _get_local_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, password_hash, display_name, avatar_url, is_active
                FROM users
                WHERE email = %s
                """,
                (req.email.lower(),),
            )
            row = cur.fetchone()
            if not row or not row[5]:
                raise HTTPException(401, "邮箱或密码错误")
            user_id, email, pwd_hash, display_name, avatar_url, _is_active = row

            if not pwd_hash:
                raise HTTPException(401, "此邮箱仅支持 Google 登录,请用 Google 登录")
            if not verify_password(req.password, pwd_hash):
                raise HTTPException(401, "邮箱或密码错误")

            # 更新 last_login_at
            try:
                cur.execute(
                    "UPDATE users SET last_login_at = now() WHERE id = %s",
                    (user_id,),
                )
            except Exception:
                pass
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("[auth/login] DB error: %s", e)
        raise HTTPException(500, f"登录失败: {str(e)[:200]}")

    try:
        token = create_jwt(str(user_id), email, provider="email")
    except RuntimeError as e:
        raise HTTPException(503, str(e))

    return AuthResponse(
        success=True,
        token=token,
        user_id=str(user_id),
        email=email,
        display_name=display_name,
    )


@router.post("/google", response_model=AuthResponse)
async def google_login(req: GoogleLoginRequest):
    """Google ID token 登录(自动 upsert user)。"""
    try:
        google_info = verify_google_id_token(req.id_token)
    except RuntimeError as e:
        # GOOGLE_CLIENT_ID 没配 / google-auth 没装
        raise HTTPException(503, str(e))
    except Exception as e:
        log.warning("[auth/google] token verify fail: %s", e)
        raise HTTPException(401, f"Google 验证失败: {str(e)[:120]}")

    google_id = google_info.get("sub")
    email = (google_info.get("email") or "").lower()
    name = google_info.get("name") or req.display_name
    picture = google_info.get("picture")

    if not google_id or not email:
        raise HTTPException(401, "Google ID token 缺 sub/email")

    conn = _get_local_db_conn()
    try:
        with conn.cursor() as cur:
            # upsert:email 已存在 → 绑定 google_id;否则创建
            cur.execute(
                """
                INSERT INTO users (email, google_id, display_name, avatar_url, email_verified, last_login_at)
                VALUES (%s, %s, %s, %s, TRUE, now())
                ON CONFLICT (email) DO UPDATE SET
                  google_id     = COALESCE(users.google_id, EXCLUDED.google_id),
                  display_name  = COALESCE(users.display_name, EXCLUDED.display_name),
                  avatar_url    = COALESCE(users.avatar_url, EXCLUDED.avatar_url),
                  last_login_at = now()
                RETURNING id, email, display_name, avatar_url
                """,
                (email, google_id, name, picture),
            )
            row = cur.fetchone()
        conn.commit()
    except Exception as e:
        log.error("[auth/google] DB error: %s", e)
        raise HTTPException(500, f"Google 登录失败: {str(e)[:200]}")

    user_id = str(row[0])
    try:
        token = create_jwt(user_id, email, provider="google")
    except RuntimeError as e:
        raise HTTPException(503, str(e))

    return AuthResponse(
        success=True,
        token=token,
        user_id=user_id,
        email=email,
        display_name=row[2],
    )


@router.get("/me", response_model=UserInfo)
async def me(user_id: str = Depends(get_current_user)):
    """返当前登录 user(Bearer token 必须有效)。
    DEV mode 下 user_id = "00000000-0000-0000-0000-000000000001"(dev-user),返占位 user。
    """
    if user_id == "00000000-0000-0000-0000-000000000001":
        # DEV bypass
        return UserInfo(
            id=user_id, email="dev@helix.local",
            display_name="Dev User", provider="dev",
        )

    conn = _get_local_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, display_name, avatar_url, created_at,
                       password_hash IS NOT NULL AS has_password,
                       google_id IS NOT NULL AS has_google
                FROM users
                WHERE id = %s AND is_active = TRUE
                """,
                (user_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "用户不存在或已禁用")
    except HTTPException:
        raise
    except Exception as e:
        log.error("[auth/me] DB error: %s", e)
        raise HTTPException(500, f"查询失败: {str(e)[:200]}")

    provider = "google" if row[6] else ("email" if row[5] else "unknown")
    return UserInfo(
        id=str(row[0]),
        email=row[1],
        display_name=row[2],
        avatar_url=row[3],
        provider=provider,
        created_at=row[4].isoformat() if row[4] else None,
    )


@router.post("/logout")
async def logout():
    """登出。stateless JWT,服务端只返成功 — 客户端清 token 即可。"""
    return {"success": True, "message": "已登出"}
