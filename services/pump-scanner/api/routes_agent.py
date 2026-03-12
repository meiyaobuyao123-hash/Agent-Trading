"""
Agent API 路由

端点：
- POST /api/agent/chat       — 对话创建策略（调 Claude）
- GET  /api/agent/strategies  — 策略列表
- POST /api/agent/strategies  — 创建策略
- PATCH /api/agent/strategies/:id — 更新策略
- DELETE /api/agent/strategies/:id — 删除策略
- GET  /api/agent/alerts      — 告警列表
- PATCH /api/agent/alerts/:id/read — 标记已读
- GET  /api/agent/alerts/unread-count — 未读数

Python 3.9 兼容。
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth import get_current_user
from agent.llm_parser import LLMParser
from agent.strategy_manager import StrategyManager
from agent.action_dispatcher import get_user_alerts, mark_alert_read, get_unread_count

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])

# 全局实例
_llm_parser = LLMParser()
_strategy_mgr = StrategyManager()


# ── 请求/响应模型 ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户输入")
    context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    strategy: Optional[Dict[str, Any]] = None
    message: str
    requires_confirmation: bool = True


class StrategyCreateRequest(BaseModel):
    spec: Dict[str, Any] = Field(..., description="策略规范")
    source_prompt: Optional[str] = None


class StrategyUpdateRequest(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    actions: Optional[List[Dict[str, Any]]] = None
    filters: Optional[Dict[str, Any]] = None
    cooldown_minutes: Optional[int] = None


# ── 对话端点 ──────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user_id: str = Depends(get_current_user),
):
    """
    对话创建策略

    用户发送自然语言，Claude 解析为 StrategySpec。
    返回策略规范和 AI 回复，用户确认后调 POST /strategies 创建。
    """
    strategy_spec, ai_message = await _llm_parser.parse_strategy(
        req.message, req.context
    )

    return ChatResponse(
        strategy=strategy_spec,
        message=ai_message,
        requires_confirmation=strategy_spec is not None,
    )


# ── 策略 CRUD ─────────────────────────────────────────────────

@router.get("/strategies")
async def list_strategies(
    status: Optional[str] = Query(None, description="按状态过滤"),
    user_id: str = Depends(get_current_user),
):
    """获取当前用户的策略列表"""
    strategies = _strategy_mgr.list_strategies(user_id, status=status)
    return {"strategies": strategies, "total": len(strategies)}


@router.post("/strategies")
async def create_strategy(
    req: StrategyCreateRequest,
    user_id: str = Depends(get_current_user),
):
    """创建新策略"""
    # 检查策略数量限制
    existing = _strategy_mgr.list_strategies(user_id)
    active_count = len([s for s in existing if s.get("status") != "archived"])
    if active_count >= 20:
        raise HTTPException(
            status_code=400,
            detail="策略数量已达上限（最多 20 个活跃策略）",
        )

    try:
        strategy = _strategy_mgr.create_strategy(
            user_id=user_id,
            spec=req.spec,
            source_prompt=req.source_prompt,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"strategy": strategy, "message": "策略创建成功"}


@router.patch("/strategies/{strategy_id}")
async def update_strategy(
    strategy_id: str,
    req: StrategyUpdateRequest,
    user_id: str = Depends(get_current_user),
):
    """更新策略"""
    # 验证策略属于当前用户
    strategy = _strategy_mgr.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    if strategy.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="无权限操作")

    updates = {}  # type: Dict[str, Any]
    if req.name is not None:
        updates["name"] = req.name
    if req.status is not None:
        updates["status"] = req.status
    if req.conditions is not None:
        updates["conditions"] = req.conditions
    if req.actions is not None:
        updates["actions"] = req.actions
    if req.filters is not None:
        updates["filters"] = req.filters
    if req.cooldown_minutes is not None:
        updates["cooldown_min"] = max(req.cooldown_minutes, 5)

    if not updates:
        raise HTTPException(status_code=400, detail="没有要更新的字段")

    result = _strategy_mgr.update_strategy(strategy_id, updates)
    if not result:
        raise HTTPException(status_code=500, detail="更新失败")

    return {"strategy": result, "message": "策略更新成功"}


@router.delete("/strategies/{strategy_id}")
async def delete_strategy(
    strategy_id: str,
    user_id: str = Depends(get_current_user),
):
    """删除策略"""
    strategy = _strategy_mgr.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    if strategy.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="无权限操作")

    success = _strategy_mgr.delete_strategy(strategy_id)
    if not success:
        raise HTTPException(status_code=500, detail="删除失败")

    return {"message": "策略已删除"}


# ── 告警端点 ──────────────────────────────────────────────────

@router.get("/alerts")
async def list_alerts(
    limit: int = Query(50, ge=1, le=200),
    unread_only: bool = Query(False),
    user_id: str = Depends(get_current_user),
):
    """获取用户告警列表"""
    alerts = get_user_alerts(user_id, limit=limit, unread_only=unread_only)
    unread = get_unread_count(user_id)

    return {
        "alerts": alerts,
        "total": len(alerts),
        "unread_count": unread,
    }


@router.patch("/alerts/{alert_id}/read")
async def read_alert(
    alert_id: str,
    user_id: str = Depends(get_current_user),
):
    """标记告警已读"""
    success = mark_alert_read(alert_id)
    if not success:
        raise HTTPException(status_code=500, detail="操作失败")

    return {"message": "已标记已读"}


@router.get("/alerts/unread-count")
async def unread_count(
    user_id: str = Depends(get_current_user),
):
    """获取未读告警数量"""
    count = get_unread_count(user_id)
    return {"unread_count": count}
