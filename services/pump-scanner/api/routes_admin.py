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

实施(R37):
  Kill Switch = SafetyEngine CB14(severity=blocked, auto_release=null)+ 审计
  状态读 SafetyEngine.get_global_state();全局 blocked → 整个 Agent 直接拒所有 trade
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/api/admin", tags=["admin"])
log = logging.getLogger(__name__)

MOCK_MODE = os.environ.get("MOCK_MODE", "false").lower() == "true"

# CB14 = 管理员手工 Kill Switch(safety_policy.yaml 已注册)
KILL_SWITCH_CB_ID = "CB14"

# 简单 admin token 校验(R37 简版,header X-Admin-Token);production 用 RBAC
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")  # 空则不校验(开发期)


def _check_admin(x_admin_token: Optional[str]) -> None:
    """空 token = 开发期允许所有;否则严格匹配。"""
    if not ADMIN_TOKEN:
        return
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="invalid admin token")


def _write_audit(
    event_type: str,
    severity: str,
    payload: dict,
    device_id: Optional[str] = None,
) -> None:
    """写 security_audit_log(本地 PG)。失败不阻塞主流程。"""
    try:
        from local_db import _get_conn
    except ImportError:
        log.debug("[admin-audit] local_db unavailable, skip")
        return
    try:
        conn = _get_conn()
        # device_id 必填(NOT NULL)— admin 操作用全 0 UUID 占位
        did = device_id or "00000000-0000-0000-0000-000000000000"
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO security_audit_log
                  (device_id, event_type, severity, payload)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (did, event_type, severity, json.dumps(payload, default=str)),
            )
        log.info("[admin-audit] %s %s", event_type, payload.get("reason", ""))
    except Exception as e:
        msg = str(e).lower()
        if "does not exist" in msg or "undefined" in msg:
            log.debug("[admin-audit] table not found, skip")
        else:
            log.warning("[admin-audit] write failed: %s", e)


# ── 请求 schema ─────────────────────────────────────────────


class KillSwitchRequest(BaseModel):
    reason: str
    confirm: bool = False


class ReleaseRequest(BaseModel):
    reason: str
    confirm: bool = False


class CBResetRequest(BaseModel):
    reason: str


# ── Kill Switch ─────────────────────────────────────────────


@router.post("/agent/kill-switch")
async def kill_switch(
    req: KillSwitchRequest,
    x_admin_token: Optional[str] = Header(default=None),
):
    """1 键关闭整个 Agent < 10s。

    实施:
      - SafetyEngine.trip_breaker(CB14, reason) → severity=blocked + auto_release=null
      - get_global_state() 立即返 'blocked';trade_executor 拒所有新单
      - 写 security_audit_log event_type='kill_switch' severity='critical'
    """
    _check_admin(x_admin_token)
    if not req.confirm:
        raise HTTPException(status_code=400, detail="必须 confirm=true")

    if MOCK_MODE:
        return {"ok": True, "reason": req.reason, "took_ms": 50, "mode": "mock"}

    t0 = time.time()
    try:
        from agent.safety_engine import get_safety_engine
        engine = get_safety_engine()
        state = engine.trip_breaker(KILL_SWITCH_CB_ID, f"manual:{req.reason}")
        took_ms = int((time.time() - t0) * 1000)
        if state is None:
            raise HTTPException(status_code=500, detail=f"{KILL_SWITCH_CB_ID} 未注册(safety_policy.yaml 缺)")
        _write_audit(
            event_type="kill_switch",
            severity="critical",
            payload={
                "action": "trip",
                "cb_id": KILL_SWITCH_CB_ID,
                "reason": req.reason,
                "took_ms": took_ms,
                "global_state": engine.get_global_state(),
            },
        )
        log.critical("[kill-switch] TRIPPED reason=%s took_ms=%d", req.reason, took_ms)
        return {
            "ok": True,
            "reason": req.reason,
            "took_ms": took_ms,
            "global_state": engine.get_global_state(),
            "cb_id": KILL_SWITCH_CB_ID,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.exception("[kill-switch] failed")
        raise HTTPException(status_code=500, detail=f"kill switch failed: {e}")


@router.post("/agent/kill-switch/release")
async def release_kill_switch(
    req: ReleaseRequest,
    x_admin_token: Optional[str] = Header(default=None),
):
    """解除 Kill Switch(必须 confirm=true 二次确认)。"""
    _check_admin(x_admin_token)
    if not req.confirm:
        raise HTTPException(status_code=400, detail="必须 confirm=true")

    if MOCK_MODE:
        return {"ok": True, "reason": req.reason, "mode": "mock"}

    try:
        from agent.safety_engine import get_safety_engine
        engine = get_safety_engine()
        released = engine.release_breaker(KILL_SWITCH_CB_ID, manual=True)
        _write_audit(
            event_type="kill_switch",
            severity="warn",
            payload={
                "action": "release",
                "cb_id": KILL_SWITCH_CB_ID,
                "reason": req.reason,
                "was_active": released,
                "global_state": engine.get_global_state(),
            },
        )
        log.warning("[kill-switch] RELEASED was_active=%s reason=%s", released, req.reason)
        return {
            "ok": True,
            "released": released,
            "global_state": engine.get_global_state(),
        }
    except Exception as e:
        log.exception("[kill-switch] release failed")
        raise HTTPException(status_code=500, detail=f"release failed: {e}")


@router.get("/agent/state")
async def agent_state():
    """查全局状态(无需 admin token,用于 Flutter 客户端 polling)。"""
    if MOCK_MODE:
        return {"status": "normal", "since": "2026-05-01T00:00:00Z", "active_cbs": []}
    try:
        from agent.safety_engine import get_safety_engine
        engine = get_safety_engine()
        actives = engine.get_active_breakers()
        return {
            "status": engine.get_global_state(),
            "active_cbs": [
                {
                    "cb_id": s.cb_id,
                    "name": s.name,
                    "tripped_at": s.tripped_at.isoformat(),
                    "auto_release_at": (
                        s.auto_release_at.isoformat() if s.auto_release_at else None
                    ),
                    "reason": s.reason,
                    "severity": s.severity,
                }
                for s in actives.values()
            ],
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log.exception("[admin-state] failed")
        raise HTTPException(status_code=500, detail=str(e))


# ── Cost / CB 管理 ──────────────────────────────────────────


@router.post("/cost/refresh")
async def cost_refresh(x_admin_token: Optional[str] = Header(default=None)):
    _check_admin(x_admin_token)
    if MOCK_MODE:
        return {"monthly_used_usd": 0, "level": "NORMAL", "pct": 0, "mode": "mock"}
    try:
        from agent.cost_guard import get_cost_guard
        guard = get_cost_guard()
        guard.refresh()
        return {
            "monthly_used_usd": guard.monthly_used_usd(),
            "level": guard.current_level().value,
            "pct": guard.usage_pct(),
        }
    except Exception as e:
        log.exception("[cost-refresh] failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cb/{cb_id}/reset")
async def cb_reset(
    cb_id: str,
    req: CBResetRequest,
    x_admin_token: Optional[str] = Header(default=None),
):
    """人工重置任意 CB(包括 CB14 Kill Switch)。"""
    _check_admin(x_admin_token)
    if MOCK_MODE:
        return {"ok": True, "cb_id": cb_id, "mode": "mock"}
    try:
        from agent.safety_engine import get_safety_engine
        engine = get_safety_engine()
        released = engine.release_breaker(cb_id, manual=True)
        _write_audit(
            event_type="cb_trigger",
            severity="warn",
            payload={"action": "release", "cb_id": cb_id, "reason": req.reason, "was_active": released},
        )
        return {"ok": True, "cb_id": cb_id, "released": released, "global_state": engine.get_global_state()}
    except Exception as e:
        log.exception("[cb-reset] failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/shadow-eval")
async def shadow_eval(x_admin_token: Optional[str] = Header(default=None)):
    """手动触发 Semantic Shadow Mode 评估(R37 P0-4)。
    生产环境每 6h 由 cron 自动跑;此 endpoint 用于演练。
    """
    _check_admin(x_admin_token)
    if MOCK_MODE:
        return {"graduated": 0, "dormant": 0, "failed": 0, "errors": 0, "mode": "mock"}
    try:
        from agent.memory import get_memory_manager
        counts = get_memory_manager().semantic.evaluate_shadow_rules()
        return counts
    except Exception as e:
        log.exception("[shadow-eval] failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hitl/scan-timeouts")
async def hitl_scan_timeouts(x_admin_token: Optional[str] = Header(default=None)):
    """手动触发 HITL 5/15/60min 扫描(R37 P0-3)。
    生产环境每 60s 由 cron 自动跑;此 endpoint 用于演练 / 紧急清队列。
    """
    _check_admin(x_admin_token)
    if MOCK_MODE:
        return {"repushed": 0, "degraded": 0, "expired": 0, "errors": 0, "mode": "mock"}
    try:
        from agent.loops.hitl_timeout_loop import scan_and_escalate
        counts = await scan_and_escalate()
        return counts
    except Exception as e:
        log.exception("[hitl-scan] failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cb")
async def cb_list():
    """所有 CB 当前状态(active=true 表示已触发)。"""
    if MOCK_MODE:
        return {"breakers": [{"id": f"CB{i:02d}", "active": False} for i in range(1, 15)]}
    try:
        from agent.safety_engine import get_safety_engine
        engine = get_safety_engine()
        actives = engine.get_active_breakers()
        # 列出全部 CB(active 与否 + 触发详情)
        all_cbs = []
        for cb_id, cb in engine._cb_index.items():
            state = actives.get(cb_id)
            all_cbs.append({
                "id": cb_id,
                "name": cb.get("name", cb_id),
                "severity": cb.get("severity", "blocked"),
                "active": state is not None,
                "tripped_at": state.tripped_at.isoformat() if state else None,
                "auto_release_at": (
                    state.auto_release_at.isoformat() if state and state.auto_release_at else None
                ),
                "reason": state.reason if state else None,
            })
        return {"breakers": all_cbs, "global_state": engine.get_global_state()}
    except Exception as e:
        log.exception("[cb-list] failed")
        raise HTTPException(status_code=500, detail=str(e))
