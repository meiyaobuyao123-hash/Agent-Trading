"""
JWT 认证 — Supabase JWT 验证

验证 Flutter App 发送的 Supabase JWT Token，
提取 user_id（sub claim）。

Python 3.9 兼容。
"""
import os
import logging
from typing import Optional

import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

log = logging.getLogger(__name__)

# Supabase JWT Secret（从环境变量或 config 获取）
JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
JWT_ALGORITHM = "HS256"

# FastAPI 安全方案
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> str:
    """
    验证 JWT 并返回 user_id

    用于 FastAPI 路由依赖注入：
        @router.get("/strategies")
        async def list_strategies(user_id: str = Depends(get_current_user)):
            ...

    Returns:
        user_id (UUID string)

    Raises:
        HTTPException 401 if 认证失败
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header",
        )

    token = credentials.credentials

    try:
        # 解码 Supabase JWT
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            audience="authenticated",
            options={
                "verify_exp": True,
                "verify_aud": True,
            },
        )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token: missing user ID",
            )

        return user_id

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired",
        )
    except jwt.InvalidAudienceError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token audience",
        )
    except jwt.InvalidTokenError as e:
        log.warning(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[str]:
    """
    可选的 JWT 验证（不强制）

    用于支持匿名访问的端点
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
