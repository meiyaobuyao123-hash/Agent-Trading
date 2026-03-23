"""
Agent API 路由

端点：
- POST /api/agent/chat       — 对话创建策略（调 Claude）
- GET  /api/agent/strategies  — 策略列表
- POST /api/agent/strategies  — 创建策略
- PATCH /api/agent/strategies/:id — 更新策略
- DELETE /api/agent/strategies/:id — 删除策略
- GET  /api/agent/executions/:strategy_id — 策略交易记录 + 汇总
- GET  /api/agent/alerts      — 告警列表
- PATCH /api/agent/alerts/:id/read — 标记已读
- GET  /api/agent/alerts/unread-count — 未读数

Python 3.9 兼容。
"""
import asyncio
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
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

    每次调用前检查用户月度 API 配额（默认 20 次/月）。
    """
    # ── 用户 API 配额检查 ──────────────────────────────────────────
    quota_ok, quota_resp = await _check_and_consume_quota(user_id)
    if quota_resp is not None:
        return quota_resp  # type: ignore[return-value]
    # ─────────────────────────────────────────────────────────────

    strategy_spec, ai_message = await _llm_parser.parse_strategy(
        req.message, req.context
    )

    return ChatResponse(
        strategy=strategy_spec,
        message=ai_message,
        requires_confirmation=strategy_spec is not None,
    )


async def _check_and_consume_quota(
    user_id: str,
) -> tuple:
    """
    检查并消耗用户的月度 API 配额。

    逻辑：
      1. 查询 user_api_quota 表
      2. 如果 period_start != 当月1日，重置计数
      3. 如果 used_count >= quota_limit，返回 429
      4. 否则 used_count += 1，upsert 更新

    Returns:
        (True, None)           — 配额充足，可继续处理
        (False, JSONResponse)  — 配额耗尽，返回 429 响应
    """
    from database import get_db

    # 当月第一天（用于判断是否需要重置）
    today = date.today()
    period_start_this_month = date(today.year, today.month, 1)

    db = get_db()

    try:
        # 查询现有配额记录
        res = await asyncio.to_thread(
            lambda: db.table("user_api_quota")
            .select("used_count, quota_limit, period_start")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        row = res.data if res and res.data else None
    except Exception as e:
        log.warning("查询 user_api_quota 失败，放行请求: %s", e)
        # 查询失败时不阻断用户，宽松处理
        return (True, None)

    if row is None:
        # 首次使用：创建初始记录（used_count=1）
        new_row = {
            "user_id": user_id,
            "period_start": period_start_this_month.isoformat(),
            "used_count": 1,
            "quota_limit": 20,
        }
        try:
            await asyncio.to_thread(
                lambda: db.table("user_api_quota").upsert(new_row).execute()
            )
        except Exception as e:
            log.warning("创建 user_api_quota 失败: %s", e)
        return (True, None)

    # 解析现有记录
    used_count = int(row.get("used_count", 0))
    quota_limit = int(row.get("quota_limit", 20))
    period_start_str = row.get("period_start", "")

    # 判断是否需要重置（新的月份）
    try:
        row_period = date.fromisoformat(str(period_start_str))
    except (ValueError, TypeError):
        row_period = period_start_this_month

    if row_period != period_start_this_month:
        # 新月份：重置计数
        used_count = 0
        log.info("用户 %s 配额已重置（新月份）", user_id)

    # 检查配额是否耗尽
    if used_count >= quota_limit:
        log.info(
            "用户 %s 月度配额已用完: used=%d limit=%d",
            user_id, used_count, quota_limit,
        )
        return (False, JSONResponse(
            status_code=429,
            content={
                "error": "quota_exceeded",
                "used": used_count,
                "limit": quota_limit,
                "message": "本月免费次数已用完",
            },
        ))

    # 消耗一次配额
    new_used = used_count + 1
    upsert_data = {
        "user_id": user_id,
        "period_start": period_start_this_month.isoformat(),
        "used_count": new_used,
        "quota_limit": quota_limit,
    }
    try:
        await asyncio.to_thread(
            lambda: db.table("user_api_quota").upsert(upsert_data).execute()
        )
        log.debug("用户 %s 配额消耗: %d/%d", user_id, new_used, quota_limit)
    except Exception as e:
        log.warning("更新 user_api_quota 失败（放行请求）: %s", e)

    return (True, None)


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


# ── 交易记录端点 ─────────────────────────────────────────────

@router.get("/executions/{strategy_id}")
async def list_executions(
    strategy_id: str,
    limit: int = Query(100, ge=1, le=500),
    user_id: str = Depends(get_current_user),
):
    """获取策略的交易记录 + 汇总统计"""
    from database import get_db

    # 验证策略归属
    strategy = _strategy_mgr.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    if strategy.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="无权限操作")

    try:
        resp = (
            get_db()
            .table("agent_executions")
            .select("*")
            .eq("strategy_id", strategy_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = resp.data or []
    except Exception as e:
        log.warning("Failed to fetch executions: %s", e)
        rows = []

    # 计算汇总（按 token 分组计算 PnL）
    total_buy = 0.0
    total_sell = 0.0
    buy_count = 0
    sell_count = 0
    confirmed = 0
    failed = 0
    total_gas = 0.0
    by_token = {}  # type: Dict[str, Dict[str, float]]

    for r in rows:
        amt = float(r.get("amount_usd") or 0)
        gas = float(r.get("gas_fee_usd") or 0)
        total_gas += gas
        status = r.get("status", "")
        if status == "confirmed":
            confirmed += 1
        elif status == "failed":
            failed += 1

        token_key = r.get("token_address", "unknown")
        if token_key not in by_token:
            by_token[token_key] = {"buy": 0.0, "sell": 0.0}

        if r.get("action") == "buy":
            buy_count += 1
            total_buy += amt
            by_token[token_key]["buy"] += amt
        elif r.get("action") == "sell":
            sell_count += 1
            total_sell += amt
            by_token[token_key]["sell"] += amt

    realized_pnl = sum(
        v["sell"] - v["buy"] for v in by_token.values()
    ) - total_gas

    summary = {
        "total_buy_usd": round(total_buy, 2),
        "total_sell_usd": round(total_sell, 2),
        "realized_pnl": round(realized_pnl, 2),
        "total_gas_usd": round(total_gas, 2),
        "buy_count": buy_count,
        "sell_count": sell_count,
        "confirmed_count": confirmed,
        "failed_count": failed,
        "total_count": len(rows),
    }

    return {"data": rows, "summary": summary}


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
    success = mark_alert_read(alert_id, user_id=user_id)
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


# ── PRD-005: 记忆系统端点 ──────────────────────────────────────

@router.get("/memory")
async def get_memory_stats(
    user_id: str = Depends(get_current_user),
):
    """
    获取记忆系统状态

    返回短期/中期/长期记忆统计 + 最近事件 + 活跃规则列表。
    """
    from agent.memory import get_memory_manager

    mem = get_memory_manager()
    stats = mem.get_stats()

    # 最近短期事件（10条）
    recent_events = mem.working.get_recent(10)
    # 只返回摘要
    recent_summaries = [
        {"summary": e.get("summary", str(e)[:80]), "type": e.get("type", ""), "ts": e.get("_ts", 0)}
        for e in recent_events
    ]

    # 活跃 semantic 规则
    active_rules = mem.semantic.get_all_active()
    rules_summary = []
    for r in active_rules:
        sd = r.get("structured_data") or {}
        cw = r.get("comply_win", 0) or 0
        cl = r.get("comply_lose", 0) or 0
        total = cw + cl
        rules_summary.append({
            "id": r.get("id", ""),
            "condition": sd.get("condition", "") if isinstance(sd, dict) else "",
            "action": sd.get("action", "") if isinstance(sd, dict) else "",
            "comply_win": cw,
            "comply_lose": cl,
            "violate_win": r.get("violate_win", 0) or 0,
            "violate_lose": r.get("violate_lose", 0) or 0,
            "comply_win_rate": round(cw / total * 100, 1) if total > 0 else None,
            "usage_count": r.get("usage_count", 0) or 0,
            "content": r.get("content", "")[:100],
            "created_at": r.get("created_at", ""),
        })

    return {
        "stats": stats,
        "recent_events": recent_summaries,
        "active_rules": rules_summary,
    }


# ── 表现分析 ────────────────────────────────────────────

@router.get("/performance/{strategy_id}")
async def strategy_performance(
    strategy_id: str,
    days: int = Query(30, ge=1, le=90),
    user_id: str = Depends(get_current_user),
):
    """获取策略表现指标（胜率/PNL/夏普率）"""
    from agent.performance_analytics import get_strategy_performance
    result = await get_strategy_performance(strategy_id, days)
    return result


@router.get("/portfolio")
async def portfolio_summary(
    user_id: str = Depends(get_current_user),
):
    """获取用户持仓汇总"""
    from agent.performance_analytics import get_portfolio_summary
    result = await get_portfolio_summary(user_id)
    return result


@router.get("/daily-pnl")
async def daily_pnl(
    days: int = Query(7, ge=1, le=30),
    user_id: str = Depends(get_current_user),
):
    """获取每日 P&L 汇总"""
    from agent.performance_analytics import get_daily_pnl_summary
    result = await get_daily_pnl_summary(user_id, days)
    return result


# ── 策略回测 ────────────────────────────────────────────

@router.post("/backtest")
async def backtest(
    req: ChatRequest,
    user_id: str = Depends(get_current_user),
):
    """
    回测策略：输入策略规范，返回历史模拟结果

    请求体示例: {"message": "策略 JSON spec"}
    """
    from agent.backtester import backtest_strategy
    import json

    # 尝试解析为 JSON spec
    try:
        spec = json.loads(req.message)
    except (json.JSONDecodeError, TypeError):
        # 不是 JSON，先用 LLM 解析
        result = await _llm_parser.parse_strategy(req.message)
        if result is None:
            return {"error": "无法解析策略", "trigger_count": 0}
        spec, _ = result

    days = (req.context or {}).get("days", 7)
    result = await backtest_strategy(spec, days=days)
    return result


# ── PRD-006: Regime 端点 ─────────────────────────────────────────

@router.get("/regime")
async def get_regime_status(
    user_id: str = Depends(get_current_user),
):
    """获取当前市场 Regime 状态"""
    try:
        from agent.regime_detector import get_regime_detector
        detector = get_regime_detector()
        return detector.get_stats()
    except Exception as e:
        log.warning("Regime status error: %s", e)
        return {"global_regime": "RANGING", "error": str(e)}


@router.get("/regime/history")
async def get_regime_history(
    days: int = Query(14, ge=1, le=90),
    asset: Optional[str] = Query(None, description="BTC/SOL/ETH"),
    transitions_only: bool = Query(False, description="只看切换记录"),
    user_id: str = Depends(get_current_user),
):
    """获取 Regime 历史记录"""
    from database import get_db
    from datetime import date, timedelta

    cutoff = (date.today() - timedelta(days=days)).isoformat()

    try:
        query = get_db().table("agent_regime_history").select("*") \
            .gte("created_at", f"{cutoff}T00:00:00Z") \
            .order("created_at", desc=True) \
            .limit(500)

        if asset:
            query = query.eq("asset", asset)
        if transitions_only:
            query = query.eq("is_transition", True)

        res = query.execute()
        rows = res.data or []
    except Exception as e:
        log.warning("Regime history error: %s", e)
        rows = []

    return {
        "data": rows,
        "total": len(rows),
        "period_days": days,
    }


@router.get("/regime/audit")
async def get_regime_audit(
    days: int = Query(14, ge=1, le=90),
    user_id: str = Depends(get_current_user),
):
    """获取 Regime 审计报告（O7 工具数据）"""
    from optimizer_tools import tool_read_regime_history
    return tool_read_regime_history(days=days)
