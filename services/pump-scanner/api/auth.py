"""
JWT 认证 — Supabase JWT 验证

验证 Flutter App 发送的 Supabase JWT Token，
提取 user_id（sub claim）。

开发模式：如果 SUPABASE_JWT_SECRET 未设置，
跳过 JWT 验证，使用 dev-user 作为 user_id。

Python 3.9 兼容。
"""
import os
import logging
from typing import Optional

import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from dotenv import load_dotenv
load_dotenv(override=True)

log = logging.getLogger(__name__)

# R46 — 自建 JWT(取代 Supabase JWT;SUPABASE_JWT_SECRET 兼容旧 deploy)
# 优先 AUTH_JWT_SECRET,fallback SUPABASE_JWT_SECRET(向后兼容,未来可删)
JWT_SECRET = os.getenv("AUTH_JWT_SECRET") or os.getenv("SUPABASE_JWT_SECRET", "")
JWT_ALGORITHM = "HS256"

# R47 P4 加固:DEV bypass 必须双 env 才能开
#   - JWT_SECRET 未配 (向后兼容)
#   - AND ENVIRONMENT=development(显式开发环境)
# production 默认 ENVIRONMENT=production → 即使 JWT_SECRET 未配也强制 401
ENVIRONMENT = os.getenv("ENVIRONMENT", "production").lower()
DEV_MODE = (not JWT_SECRET) and (ENVIRONMENT == "development")

if not JWT_SECRET and ENVIRONMENT != "development":
    log.error(
        "AUTH_JWT_SECRET 未配 + ENVIRONMENT != development;"
        "API 将拒绝所有请求(401),配 ENVIRONMENT=development 才走 dev-user bypass"
    )
elif DEV_MODE:
    log.warning("AUTH_JWT_SECRET not set + ENVIRONMENT=development → DEV mode (auth bypassed)")

# FastAPI 安全方案
security = HTTPBearer(auto_error=False)

_DEV_USER_ID = "00000000-0000-0000-0000-000000000001"


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> str:
    """
    验证 JWT 并返回 user_id

    R47 P4 production 强制:
      - JWT_SECRET 未配 + ENVIRONMENT 不是 development → 401(无 dev-user 兜底)
      - 只有同时满足 JWT_SECRET 未配 AND ENVIRONMENT=development → DEV mode

    Returns:
        user_id (UUID string)

    Raises:
        HTTPException 401 if 认证失败
    """
    # R47 P4 — DEV mode 严格化,production 拒所有无 token 请求
    if DEV_MODE:
        return _DEV_USER_ID

    if not JWT_SECRET:
        # production 但 secret 没配 — 不能走 dev bypass,必须报 503 让运维知道
        raise HTTPException(
            status_code=503,
            detail="Server auth not configured (AUTH_JWT_SECRET missing in production)",
        )

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header",
        )

    token = credentials.credentials

    try:
        # R46 自建 JWT 不强制 audience(payload 用 {sub, email, exp, iat, provider})
        # Supabase JWT 兼容路径:audience='authenticated'
        # 先按自建 JWT(无 aud)解,失败 fallback Supabase 风格
        try:
            payload = jwt.decode(
                token, JWT_SECRET, algorithms=[JWT_ALGORITHM],
                options={"verify_exp": True, "verify_aud": False},
            )
        except jwt.InvalidTokenError:
            payload = jwt.decode(
                token, JWT_SECRET, algorithms=[JWT_ALGORITHM],
                audience="authenticated",
                options={"verify_exp": True, "verify_aud": True},
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
