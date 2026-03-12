"""
Risk Management API 路由

端点：
- GET  /api/agent/risk-status             — 风控状态摘要
- POST /api/agent/risk/circuit-breaker/reset — 手动关闭熔断器

Python 3.9 兼容。
"""
import logging

from fastapi import APIRouter, Depends

from api.auth import get_current_user
from agent.risk_manager import get_risk_manager

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["risk"])


@router.get("/risk-status")
async def risk_status(
    user_id: str = Depends(get_current_user),
):
    """获取风控状态摘要"""
    risk_mgr = get_risk_manager()
    summary = risk_mgr.get_risk_summary()
    return {"risk": summary}


@router.post("/risk/circuit-breaker/reset")
async def reset_circuit_breaker(
    user_id: str = Depends(get_current_user),
):
    """手动关闭熔断器"""
    risk_mgr = get_risk_manager()
    was_active = risk_mgr._circuit_breaker_active
    risk_mgr.deactivate_circuit_breaker()

    log.info(f"Circuit breaker reset by user {user_id} (was_active={was_active})")

    return {
        "message": "Circuit breaker deactivated" if was_active else "Circuit breaker was not active",
        "was_active": was_active,
    }
