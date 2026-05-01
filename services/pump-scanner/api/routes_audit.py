"""
/api/audit/* — 安全审计日志查询(三级权限:用户/Admin/法务)
引用 docs/agent-pm/08-safety-policy.md §11.5
引用 docs/agent-pm/17-tech-plan.md Phase 0
引用 migration 035_security_audit_log.sql

权限分级:
  user:  只能查自己 device_id 的 log
  admin: 全量查
  legal: 全量查 + 导出 CSV/JSON

状态:🔴 v0.1 stub(W3-W4 实施)
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Literal
import os

router = APIRouter(prefix="/api/audit", tags=["audit"])

MOCK_MODE = os.environ.get("MOCK_MODE", "false").lower() == "true"


@router.get("/logs")
async def list_audit_logs(
    device_id: str | None = None,
    event_type: str | None = None,
    severity: Literal["info", "warn", "error", "critical"] | None = None,
    since: str | None = None,
    limit: int = Query(default=100, le=1000),
):
    """三级权限按 caller role 过滤。
    user role 必须传自己的 device_id,否则 403。
    """
    if MOCK_MODE:
        return {"logs": [], "total": 0}
    raise HTTPException(status_code=501, detail="audit query W3-W4 实施")


@router.get("/export")
async def export_audit_logs(
    format: Literal["csv", "json"] = "json",
    since: str | None = None,
    until: str | None = None,
):
    """法务专用,导出审计日志(对应 docs/agent-pm/08-safety-policy.md §11.5)。"""
    if MOCK_MODE:
        return {"format": format, "rows": 0, "url": None}
    raise HTTPException(status_code=403, detail="legal role required;W3-W4 实施权限校验")


@router.get("/summary")
async def audit_summary(days: int = Query(default=7, le=180)):
    """审计摘要:近 N 天各 event_type / severity 分布。"""
    if MOCK_MODE:
        return {"days": days, "by_type": {}, "by_severity": {}}
    raise HTTPException(status_code=501, detail="W3-W4 实施")
