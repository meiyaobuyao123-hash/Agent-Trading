"""
Optimizer API 路由

端点：
- GET  /api/optimizer/runs          — 优化运行列表
- GET  /api/optimizer/runs/{id}     — 运行详情（含完整对话）
- GET  /api/optimizer/proposals     — 所有提案
- POST /api/optimizer/proposals/{id}/approve — 审批通过
- POST /api/optimizer/proposals/{id}/reject  — 审批拒绝
- GET  /api/optimizer/metrics       — 指标趋势
- POST /api/optimizer/trigger       — 手动触发优化
"""

import logging
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from database import get_db

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/optimizer", tags=["optimizer"])


# ── 运行记录 ───────────────────────────────────────

@router.get("/runs")
async def list_runs(limit: int = 20):
    """优化运行列表"""
    db = get_db()
    res = db.table("optimization_runs") \
        .select("id, run_date, status, analysis, tokens_used, cost_usd, started_at, completed_at") \
        .order("started_at", desc=True) \
        .limit(limit) \
        .execute()
    return {"runs": res.data, "count": len(res.data)}


@router.get("/runs/{run_id}")
async def get_run(run_id: int):
    """运行详情（含完整对话记录）"""
    db = get_db()
    res = db.table("optimization_runs") \
        .select("*") \
        .eq("id", run_id) \
        .execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return res.data[0]


# ── 提案 ───────────────────────────────────────────

@router.get("/proposals")
async def list_proposals(status: Optional[str] = None, limit: int = 50):
    """所有提案列表"""
    db = get_db()
    query = db.table("optimization_proposals") \
        .select("*") \
        .order("created_at", desc=True) \
        .limit(limit)

    if status:
        query = query.eq("status", status)

    res = query.execute()
    return {"proposals": res.data, "count": len(res.data)}


class ReviewRequest(BaseModel):
    comment: Optional[str] = None
    reviewer: str = "portal_user"


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: int, body: ReviewRequest):
    """审批通过 — 应用优化方案"""
    db = get_db()

    # 检查方案状态
    res = db.table("optimization_proposals") \
        .select("*") \
        .eq("id", proposal_id) \
        .execute()

    if not res.data:
        raise HTTPException(status_code=404, detail="方案不存在")

    proposal = res.data[0]
    if proposal["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"方案状态为 {proposal['status']}，只有 pending 才能审批"
        )

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    # 更新状态为 approved
    db.table("optimization_proposals").update({
        "status": "approved",
        "reviewed_by": body.reviewer,
        "reviewed_at": now,
        "review_comment": body.comment,
    }).eq("id", proposal_id).execute()

    # 应用方案
    from optimizer_agent import apply_proposal
    result = apply_proposal(proposal_id)

    return {
        "proposal_id": proposal_id,
        "status": "approved_and_applied",
        "apply_result": result,
        "message": "方案已批准并应用，需要重启服务才能完全生效",
    }


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(proposal_id: int, body: ReviewRequest):
    """审批拒绝"""
    db = get_db()

    res = db.table("optimization_proposals") \
        .select("id, status") \
        .eq("id", proposal_id) \
        .execute()

    if not res.data:
        raise HTTPException(status_code=404, detail="方案不存在")

    if res.data[0]["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"方案状态为 {res.data[0]['status']}，只有 pending 才能审批"
        )

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    db.table("optimization_proposals").update({
        "status": "rejected",
        "reviewed_by": body.reviewer,
        "reviewed_at": now,
        "review_comment": body.comment,
    }).eq("id", proposal_id).execute()

    return {
        "proposal_id": proposal_id,
        "status": "rejected",
        "message": "方案已拒绝",
    }


# ── 指标趋势 ───────────────────────────────────────

@router.get("/metrics")
async def get_metrics(days: int = 30):
    """指标趋势数据"""
    db = get_db()
    res = db.table("optimization_metrics_history") \
        .select("*") \
        .order("snapshot_date", desc=True) \
        .limit(days) \
        .execute()
    return {"metrics": res.data, "count": len(res.data)}


# ── 手动触发 ───────────────────────────────────────

@router.post("/trigger")
async def trigger_optimization(mode: str = "auto"):
    """
    手动触发一次优化（异步执行）。
    mode: "auto"（Governor 自动选择）| "pump" | "hot"
    """
    async def _run():
        try:
            if mode == "hot":
                from optimizer_agent import run_hot_optimization
                result = await asyncio.to_thread(run_hot_optimization)
            elif mode == "pump":
                from optimizer_agent import run_optimization
                result = await asyncio.to_thread(run_optimization)
            else:
                from governor import run_governor
                result = await run_governor()
            log.info(f"手动触发优化完成 (mode={mode}): {result}")
        except Exception as e:
            log.error(f"手动触发优化失败: {e}")

    asyncio.create_task(_run())

    return {
        "status": "triggered",
        "mode": mode,
        "message": f"{'热币' if mode == 'hot' else 'Pump' if mode == 'pump' else '自动'}优化已在后台启动",
    }
