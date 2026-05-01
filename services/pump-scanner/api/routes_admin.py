"""
/api/admin/* — 管理员端点 (Kill Switch / 全局状态 / 演练)
引用 docs/agent-pm/17-tech-plan.md Phase 0
引用 docs/agent-pm/12-incident-response-sop.md

仅 admin role 可访问;所有操作必入 security_audit_log(event_type='admin_action').

接口:
  POST /api/admin/agent/kill-switch       全局 BLOCKED < 10s(任何理由都能用)
  POST /api/admin/agent/kill-switch/release  解除 kill switch(必须二次确认)
  GET  /api/admin/agent/state              查全局状态(blocked/degraded/normal)
  POST /api/admin/cost/refresh             手动刷新 CostGuard
  POST /api/admin/cb/{cb_id}/reset         重置指定熔断器
  GET  /api/admin/cb                       列出所有熔断器状态

状态:🔴 v0.1 stub(W3-W4 实施;Kill Switch 是 launch criteria 必备)
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import os

router = APIRouter(prefix="/api/admin", tags=["admin"])

MOCK_MODE = os.environ.get("MOCK_MODE", "false").lower() == "true"


class KillSwitchRequest(BaseModel):
    reason: str
    confirm: bool = False


@router.post("/agent/kill-switch")
async def kill_switch(req: KillSwitchRequest):
    """1 键关闭整个 Agent < 10s。
    实施细节:
      - UPDATE agent_global_state SET status='blocked', reason=...
      - 通知 event_bus 发 'agent.killed' 事件
      - 所有 trade_executor / loops 立即停
      - 写 security_audit_log event_type='kill_switch'
    """
    if not req.confirm:
        raise HTTPException(status_code=400, detail="必须 confirm=true")
    if MOCK_MODE:
        return {"ok": True, "reason": req.reason, "took_ms": 50}
    raise HTTPException(status_code=501, detail="W3-W4 实施")


@router.post("/agent/kill-switch/release")
async def release_kill_switch(reason: str, confirm: bool = False):
    if not confirm:
        raise HTTPException(status_code=400, detail="必须 confirm=true")
    if MOCK_MODE:
        return {"ok": True, "reason": reason}
    raise HTTPException(status_code=501, detail="W3-W4 实施")


@router.get("/agent/state")
async def agent_state():
    if MOCK_MODE:
        return {"status": "normal", "since": "2026-05-01T00:00:00Z", "active_cbs": []}
    raise HTTPException(status_code=501, detail="W3-W4 实施")


@router.post("/cost/refresh")
async def cost_refresh():
    if MOCK_MODE:
        return {"monthly_used_usd": 0, "level": "NORMAL", "pct": 0}
    raise HTTPException(status_code=501, detail="W3-W4 实施")


@router.post("/cb/{cb_id}/reset")
async def cb_reset(cb_id: str, reason: str):
    if MOCK_MODE:
        return {"ok": True, "cb_id": cb_id}
    raise HTTPException(status_code=501, detail="W3-W4 实施")


@router.get("/cb")
async def cb_list():
    if MOCK_MODE:
        return {"breakers": [{"id": f"CB{i:02d}", "active": False} for i in range(1, 14)]}
    raise HTTPException(status_code=501, detail="W3-W4 实施")
