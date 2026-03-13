"""
设备令牌注册端点

端点：
- POST   /api/device/register   — 注册/更新设备推送令牌
- DELETE /api/device/unregister — 注销当前设备令牌

Python 3.9 兼容。
"""
import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user
from database import get_db

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/device", tags=["device"])


# ── 请求模型 ─────────────────────────────────────────────────

class RegisterTokenReq(BaseModel):
    token: str = Field(..., min_length=10, description="FCM/APNs 令牌")
    platform: str = Field(..., description="设备平台: ios | android")
    device_name: Optional[str] = Field(None, description="设备名称")

class UnregisterTokenReq(BaseModel):
    token: str = Field(..., min_length=10, description="要注销的令牌")


# ── 端点 ─────────────────────────────────────────────────────

@router.post("/register")
async def register_device_token(
    req: RegisterTokenReq,
    user_id: str = Depends(get_current_user),
):
    """
    注册/更新设备推送令牌

    使用 upsert（token 唯一），同一令牌更新而非重复插入。
    token 刷新时 Flutter 端自动调用。
    """
    if req.platform not in ("ios", "android"):
        raise HTTPException(
            status_code=400,
            detail="platform must be 'ios' or 'android'",
        )

    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        get_db().table("device_tokens").upsert(
            {
                "user_id": user_id,
                "token": req.token,
                "platform": req.platform,
                "device_name": req.device_name,
                "is_active": True,
                "last_registered_at": now_iso,
                "updated_at": now_iso,
            },
            on_conflict="token",
        ).execute()

        log.info(
            "Device token registered: user=%s platform=%s",
            user_id,
            req.platform,
        )
        return {"ok": True, "message": "Device token registered"}

    except Exception as e:
        log.error("Failed to register device token: %s", e)
        raise HTTPException(status_code=500, detail="Registration failed")


@router.delete("/unregister")
async def unregister_device_token(
    req: UnregisterTokenReq,
    user_id: str = Depends(get_current_user),
):
    """
    注销设备令牌（标记 is_active=false）

    用户登出或卸载 App 时调用。
    """
    try:
        get_db().table("device_tokens").update(
            {"is_active": False}
        ).eq("token", req.token).eq("user_id", user_id).execute()

        log.info("Device token unregistered: user=%s", user_id)
        return {"ok": True, "message": "Device token unregistered"}

    except Exception as e:
        log.error("Failed to unregister device token: %s", e)
        raise HTTPException(status_code=500, detail="Unregistration failed")
