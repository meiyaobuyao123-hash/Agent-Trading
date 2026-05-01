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
import json
import logging
import os
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
    # W3 D4: 可选 safety ctx,传入后跑 SafetyEngine.check_trade
    # 即使不传,全局 CB(任一 blocked 级 CB active)也会拦截所有 chat
    safety_ctx: Optional[Dict[str, Any]] = None


def _check_safety_for_chat(safety_ctx: Optional[Dict[str, Any]]) -> Optional[str]:
    """W3 D4 chat 路径 safety pre-check。
    返回 None = 通过;返回 str = BLOCK 原因(用户可读)。

    检查 2 层:
      1. 全局 CB(任一 blocked 级 CB active)→ 永远拦
      2. 如果 safety_ctx 提供 → 跑 implemented HR(amount/regime/honeypot 等)

    这一步不消耗 user quota,不调 LLM。
    """
    try:
        from agent.safety_engine import get_safety_engine
        engine = get_safety_engine()
    except Exception:
        return None  # SafetyEngine 不可用时不阻断 chat(降级)

    # 1. 全局 CB(blocked 级)拦所有 chat
    if engine.get_global_state() == "blocked":
        active = engine.get_active_breakers()
        cb_id = next(iter(active.keys()), "CB?")
        cb_state = active.get(cb_id)
        reason = cb_state.reason if cb_state else "global blocked"
        return f"系统当前停机维护(CB {cb_id}: {reason}),请稍后重试"

    # 2. 用户传了 safety_ctx → 跑 HR
    if safety_ctx is not None:
        from agent.trade_executor import check_safety_for_trade
        ctx = {
            **safety_ctx,
            "action": safety_ctx.get("action", "chat"),
            "amount_usd": safety_ctx.get("amount_usd", 0),
        }
        block = check_safety_for_trade(ctx)
        if block is not None:
            return f"{block.rule_id}: {block.reason}"
    return None


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
    对话创建策略（非流式，保留兼容）

    用户发送自然语言，Claude 解析为 StrategySpec。
    返回策略规范和 AI 回复，用户确认后调 POST /strategies 创建。

    每次调用前检查用户月度 API 配额（默认 20 次/月）。
    W3 D4: 加 safety pre-check(全局 CB / 可选 ctx HR),BLOCK 时不消耗 quota / 不调 LLM。
    """
    # ── W3 D4 Safety pre-check(在 quota 之前;BLOCK 不消耗 quota)─
    safety_block = _check_safety_for_chat(req.safety_ctx)
    if safety_block is not None:
        return ChatResponse(
            strategy=None,
            message=f"⚠️ 安全策略阻止: {safety_block}",
            requires_confirmation=False,
        )
    # ─────────────────────────────────────────────────────────────

    # ── 用户 API 配额检查 ──────────────────────────────────────────
    quota_ok, quota_resp = await _check_and_consume_quota(user_id)
    if quota_resp is not None:
        return quota_resp  # type: ignore[return-value]
    # ─────────────────────────────────────────────────────────────

    # 自动注入最近策略 ID 到上下文（方便回测引用）
    from database import get_db as _get_db
    context = dict(req.context) if req.context else {}
    if "last_strategy_id" not in context:
        try:
            last = _get_db().table("strategies").select("id, name").order(
                "created_at", desc=True
            ).limit(1).execute()
            if last.data:
                context["last_strategy_id"] = last.data[0]["id"]
                context["last_strategy_name"] = last.data[0]["name"]
        except Exception:
            pass

    strategy_spec, ai_message = await _llm_parser.parse_strategy(
        req.message, context if context else None
    )

    return ChatResponse(
        strategy=strategy_spec,
        message=ai_message,
        requires_confirmation=strategy_spec is not None,
    )


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    user_id: str = Depends(get_current_user),
):
    """
    流式对话（打字机效果）— SSE 端点

    返回 text/event-stream，逐 token 推送 Claude 回复。
    消息格式：data: {"type":"delta","text":"..."}\n\n

    W3 D4: 加 safety pre-check(全局 CB / 可选 ctx HR),BLOCK 时直接返 SSE error 不调 LLM。
    """
    from fastapi.responses import StreamingResponse

    # ── W3 D4 Safety pre-check ──────────────────────────────────
    safety_block = _check_safety_for_chat(req.safety_ctx)
    if safety_block is not None:
        async def _safety_error():
            payload = json.dumps({
                'type': 'error',
                'message': f'⚠️ 安全策略阻止: {safety_block}',
            }, ensure_ascii=False)
            yield f"data: {payload}\n\n"
        return StreamingResponse(_safety_error(), media_type="text/event-stream")
    # ─────────────────────────────────────────────────────────────

    # 配额检查
    quota_ok, quota_resp = await _check_and_consume_quota(user_id)
    if quota_resp is not None:
        async def _quota_error():
            yield f"data: {json.dumps({'type': 'error', 'message': '月度 API 配额已用完'})}\n\n"
        return StreamingResponse(_quota_error(), media_type="text/event-stream")

    # 自动注入最近策略 ID
    from database import get_db as _get_db2
    context = dict(req.context) if req.context else {}
    if "last_strategy_id" not in context:
        try:
            last = _get_db2().table("strategies").select("id, name").order(
                "created_at", desc=True
            ).limit(1).execute()
            if last.data:
                context["last_strategy_id"] = last.data[0]["id"]
                context["last_strategy_name"] = last.data[0]["name"]
        except Exception:
            pass

    async def _event_generator():
        import json as _json
        try:
            async for event in _llm_parser.parse_strategy_stream(req.message, context if context else None):
                yield f"data: {_json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'type': 'error', 'message': str(e)[:200]})}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx 禁用缓冲
        },
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
    回测策略：支持 strategy_id 或 strategy spec JSON

    请求体示例:
      {"message": "strategy_id_uuid", "context": {"days": 7}}
      或 {"message": "策略 JSON spec"}
    """
    from agent.backtester import backtest_strategy
    import json

    days = 7
    spec = None

    # 先尝试从 context 或 message 中提取 strategy_id
    strategy_id = None
    context = req.context or {}
    if isinstance(context, dict):
        strategy_id = context.get("strategy_id")
        days = context.get("days", 7)

    # 如果 message 看起来像 UUID（strategy_id），从 DB 查
    msg = (req.message or "").strip()
    if not strategy_id and len(msg) == 36 and "-" in msg:
        strategy_id = msg

    # 尝试从请求体直接解析 strategy_id
    if not strategy_id:
        try:
            body = json.loads(msg) if msg.startswith("{") else {}
            strategy_id = body.get("strategy_id")
            days = body.get("days", days)
        except (json.JSONDecodeError, TypeError):
            pass

    if strategy_id:
        # 从 DB 查策略 spec
        try:
            db = get_db()
            res = db.table("agent_strategies").select("*").eq("id", strategy_id).single().execute()
            if res.data:
                spec = {
                    "name": res.data.get("name", ""),
                    "conditions": res.data.get("conditions", {}),
                    "filters": res.data.get("filters", {}),
                    "actions": res.data.get("actions", []),
                    "data_sources": res.data.get("data_sources", []),
                }
        except Exception as e:
            log.warning(f"查询策略 {strategy_id}: {e}")

    if spec is None:
        # 尝试解析为 JSON spec
        try:
            spec = json.loads(msg)
        except (json.JSONDecodeError, TypeError):
            # 不是 JSON，先用 LLM 解析
            result = await _llm_parser.parse_strategy(msg)
            if result is None:
                return {"error": "无法解析策略", "trigger_count": 0}
            spec, _ = result

    result = await backtest_strategy(spec, days=days)
    return result


# ── PRD-006: Regime 端点 ─────────────────────────────────────────

# ── PRD-007: 辩论记录端点 ──────────────────────────────────────

@router.get("/debates")
async def list_debates(
    limit: int = Query(50, ge=1, le=200),
    token_address: Optional[str] = Query(None, description="按代币过滤"),
    level: Optional[int] = Query(None, description="按辩论级别过滤 (1/2/3)"),
    user_id: str = Depends(get_current_user),
):
    """
    获取 Agent 辩论记录（PRD-007）

    返回多角色辩论的完整记录：分析师报告、辩论过程、结论、风控审查。
    """
    from database import get_db

    try:
        query = (
            get_db()
            .table("agent_debates")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )

        if token_address:
            query = query.eq("token_address", token_address)
        if level is not None:
            query = query.eq("debate_level", level)

        result = query.execute()
        rows = result.data or []
    except Exception as e:
        log.warning("Failed to fetch debates: %s", e)
        rows = []

    # 统计
    total = len(rows)
    l3_count = sum(1 for r in rows if r.get("debate_level") == 3)
    bull_wins = sum(1 for r in rows if r.get("conclusion_winner") == "bull")
    bear_wins = sum(1 for r in rows if r.get("conclusion_winner") == "bear")
    avg_confidence = 0.0
    if rows:
        confs = [float(r.get("conclusion_confidence") or 0) for r in rows]
        avg_confidence = sum(confs) / len(confs) if confs else 0

    # 编排器统计
    orchestrator_stats = {}
    try:
        from agent.multi_role_orchestrator import get_orchestrator
        orchestrator_stats = get_orchestrator().get_stats()
    except Exception:
        pass

    return {
        "debates": rows,
        "total": total,
        "stats": {
            "l3_count": l3_count,
            "bull_wins": bull_wins,
            "bear_wins": bear_wins,
            "avg_confidence": round(avg_confidence, 3),
            "orchestrator": orchestrator_stats,
        },
    }


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


# ══════════════════════════════════════════════════════════════
# PRD-008: 模拟盘 + 策略模板 + AI 主动推荐
# ══════════════════════════════════════════════════════════════

# ── 模拟盘端点 ────────────────────────────────────────────────

class TemplateCreateRequest(BaseModel):
    override: Optional[Dict[str, Any]] = None


@router.get("/paper-trades")
async def list_paper_trades(
    strategy_id: Optional[str] = Query(None, description="按策略过滤"),
    status: Optional[str] = Query(None, description="open/closed"),
    limit: int = Query(100, ge=1, le=500),
    user_id: str = Depends(get_current_user),
):
    """获取模拟交易记录"""
    from database import get_db

    try:
        query = (
            get_db()
            .table("agent_paper_trades")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if strategy_id:
            query = query.eq("strategy_id", strategy_id)
        if status:
            query = query.eq("status", status)

        result = query.execute()
        rows = result.data or []
    except Exception as e:
        log.warning("Failed to fetch paper trades: %s", e)
        rows = []

    return {"data": rows, "total": len(rows)}


@router.get("/paper-stats/{strategy_id}")
async def paper_stats(
    strategy_id: str,
    user_id: str = Depends(get_current_user),
):
    """获取策略的模拟盘统计"""
    # 验证策略归属
    strategy = _strategy_mgr.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    if strategy.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="无权限操作")

    from agent.paper_engine import get_paper_engine
    engine = get_paper_engine()
    stats = await engine.get_stats(strategy_id)
    return stats


@router.post("/strategies/{strategy_id}/go-live")
async def go_live(
    strategy_id: str,
    user_id: str = Depends(get_current_user),
):
    """将策略从 paper 切换到 live 模式"""
    strategy = _strategy_mgr.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    if strategy.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="无权限操作")
    if strategy.get("mode") == "live":
        return {"strategy": strategy, "message": "策略已在实盘模式"}

    result = _strategy_mgr.go_live(strategy_id)
    if not result:
        raise HTTPException(status_code=400, detail="切换失败：策略状态不允许")

    return {"strategy": result, "message": "已切换到实盘模式"}


@router.put("/strategies/{strategy_id}/rename")
async def rename_strategy(
    strategy_id: str,
    request: Request,
    user_id: str = Depends(get_current_user),
):
    """修改策略名称"""
    body = await request.json()
    new_name = body.get("name", "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="名称不能为空")

    strategy = _strategy_mgr.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")

    ok = _strategy_mgr.rename_strategy(strategy_id, new_name)
    if not ok:
        raise HTTPException(status_code=500, detail="重命名失败")

    return {"success": True, "name": new_name}


# ── 策略模板端点 ──────────────────────────────────────────────

@router.get("/templates")
async def list_templates(
    user_id: str = Depends(get_current_user),
):
    """获取所有策略模板"""
    from agent.templates import list_templates as _list_templates
    templates = _list_templates()
    return {"templates": templates, "total": len(templates)}


@router.post("/templates/{template_id}/create")
async def create_from_template(
    template_id: str,
    req: TemplateCreateRequest,
    user_id: str = Depends(get_current_user),
):
    """从模板创建策略（支持参数覆盖）"""
    from agent.templates import create_from_template as _create

    # 检查策略数量限制
    existing = _strategy_mgr.list_strategies(user_id)
    active_count = len([s for s in existing if s.get("status") != "archived"])
    if active_count >= 20:
        raise HTTPException(
            status_code=400,
            detail="策略数量已达上限（最多 20 个活跃策略）",
        )

    try:
        spec = _create(
            template_id=template_id,
            user_id=user_id,
            override=req.override,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        strategy = _strategy_mgr.create_strategy(
            user_id=user_id,
            spec=spec,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "strategy": strategy,
        "message": f"从模板 '{template_id}' 创建成功（paper 模式）",
    }


# ── 模拟盘 vs 实盘对比 ───────────────────────────────────────

@router.get("/compare/{strategy_id}")
async def compare_paper_live(
    strategy_id: str,
    user_id: str = Depends(get_current_user),
):
    """模拟盘 vs 实盘数据对比 (v1.1 Q6)"""
    strategy = _strategy_mgr.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    if strategy.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="无权限操作")

    from agent.paper_engine import get_paper_engine
    engine = get_paper_engine()
    comparison = await engine.get_comparison(strategy_id)
    return comparison


# ═══════════════════════════════════════════════════════════════
# W3 D4 — HITL 待审批队列(对接 docs/agent-pm/05-tool-catalog.md T09)
# 引用 migrations/local_pg/036_pending_approvals_wal.sql
# MOCK_MODE=true 时返 fixture(后端真实施 W7-W12)
# ═══════════════════════════════════════════════════════════════

class HitlDecision(BaseModel):
    signature: Optional[str] = Field(default=None, description="用户签名(Face ID + wallet sig)")
    note: Optional[str] = Field(default=None, max_length=500)


def _mock_pending_approval(approval_id: str = "mock-approval-001") -> Dict[str, Any]:
    """Mock fixture(MOCK_MODE 用)"""
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    now = _dt.now(_tz.utc)
    return {
        "approval_id": approval_id,
        "strategy_id": "strat-mock-1",
        "trigger_conditions_matched": [
            "聪明钱净流入 > $30000",
            "1h 涨幅 > 15%",
        ],
        "thesis_id": "demo-uuid-thesis-001",
        "token_address": "TRUMPmGjJgGgqPZkMP9KrYwoRrsAtwHzuKbMHvYn3D9",
        "token_symbol": "TRUMP",
        "chain": "solana",
        "amount_usd": 250.0,
        "remaining_authorization_usd": 1750.0,  # 用户授权剩余
        "status": "pending",
        "created_at": now.isoformat(),
        "expires_at": (now + _td(minutes=15)).isoformat(),
    }


@router.get("/pending-approvals")
async def list_pending_approvals(
    user_id: str = Depends(get_current_user),
    status: str = "pending",
    limit: int = 20,
):
    """W3 D4:列出 HITL 待审批队列。

    MOCK_MODE=true 时返 fixture(W7-W12 真实施查 pending_approvals 表)。
    """
    if os.environ.get("MOCK_MODE", "false").lower() == "true":
        return {
            "approvals": [_mock_pending_approval()],
            "total": 1,
            "user_id": user_id,
        }
    # TODO W7-W12: 查 local_pg.pending_approvals WHERE device_id=user_id AND status=...
    return {"approvals": [], "total": 0, "user_id": user_id}


@router.post("/pending-approvals/{approval_id}/approve")
async def approve_pending_approval(
    approval_id: str,
    decision: HitlDecision,
    user_id: str = Depends(get_current_user),
):
    """W3 D4:用户批准 HITL 审批。

    MOCK_MODE 返 success;真实施需:
      1. 验证签名(Face ID + wallet sig)
      2. UPDATE pending_approvals SET status='approved', signature=..., decided_at=now()
      3. 写 security_audit_log(event_type='hitl_decision', severity='info')
      4. 触发 trade_executor.execute_trade(safety_ctx={...})
    """
    if not decision.signature:
        raise HTTPException(status_code=400, detail="signature 必填(Face ID + wallet)")
    if os.environ.get("MOCK_MODE", "false").lower() == "true":
        return {
            "ok": True,
            "approval_id": approval_id,
            "status": "approved",
            "tx_hash": "0xMOCK_TX_HASH",
        }
    # TODO W7-W12 真实施
    raise HTTPException(status_code=501, detail="W7-W12 实施;当前请用 MOCK_MODE=true")


@router.post("/pending-approvals/{approval_id}/reject")
async def reject_pending_approval(
    approval_id: str,
    decision: HitlDecision,
    user_id: str = Depends(get_current_user),
):
    """W3 D4:用户拒绝 HITL 审批。"""
    if os.environ.get("MOCK_MODE", "false").lower() == "true":
        return {
            "ok": True,
            "approval_id": approval_id,
            "status": "rejected",
        }
    raise HTTPException(status_code=501, detail="W7-W12 实施;当前请用 MOCK_MODE=true")


# ═══════════════════════════════════════════════════════════
# W3 D5+: Memory rules CRUD + Reviews(对接 Phase 3 Flutter UI)
# ═══════════════════════════════════════════════════════════
#
# 设计:
#   - GET  /memory/rules                — 列表(读 agent_memory type=semantic)
#   - PATCH /memory/rules/{id}          — 启用/禁用(改 is_active)
#   - DELETE /memory/rules/{id}         — 删除(改 is_active=false + status=archived)
#   - POST /memory/rule-proposals/{id}/approve — 采纳提议(MOCK,后续接 reflection)
#   - GET  /reviews?period=daily        — 复盘(MOCK,后续接 S07 review-engine)


def _shadow_remaining_iso(shadow_until: Optional[str]) -> Optional[str]:
    return shadow_until


def _to_semantic_rule(row: Dict[str, Any]) -> Dict[str, Any]:
    """把 Supabase agent_memory row 映射成 Flutter SemanticRule schema。"""
    sd = row.get("structured_data") or {}
    if not isinstance(sd, dict):
        sd = {}
    cw = row.get("comply_win", 0) or 0
    cl = row.get("comply_lose", 0) or 0
    total = cw + cl
    win_rate = cw / total if total > 0 else 0.0

    is_active = bool(row.get("is_active", True))
    shadow_until = row.get("shadow_mode_until")
    dormant_since = row.get("dormant_since")
    if shadow_until:
        status = "shadow"
    elif dormant_since:
        status = "dormant"
    elif is_active:
        status = "active"
    else:
        status = "disabled"

    return {
        "rule_id": str(row.get("id", "")),
        "human_readable": row.get("content", "")[:280],
        "formal_condition": {
            "condition": sd.get("condition", ""),
            "action": sd.get("action", ""),
        },
        "active_regimes": sd.get("active_regimes", []) or [],
        "evidence": {
            "sample_size": total,
            "win_rate_diff": round((win_rate - 0.5) * 100, 1),
            "wilson_ci_lower": row.get("wilson_ci_lower"),
            "regimes_observed": sd.get("regimes_observed", []) or [],
        },
        "status": status,
        "shadow_mode_until": shadow_until,
        "dormant_since": dormant_since,
        "match_count": row.get("match_count", row.get("usage_count", 0)) or 0,
        "propose_count": row.get("propose_count_so_far", 0) or 0,
        "created_at": row.get("created_at") or "1970-01-01T00:00:00Z",
        "updated_at": row.get("updated_at") or row.get("created_at")
        or "1970-01-01T00:00:00Z",
    }


@router.get("/memory/rules")
async def list_memory_rules(
    user_id: str = Depends(get_current_user),
):
    """列出所有 semantic 规则(active + shadow + dormant + disabled)给 Flutter 记忆管理页。

    后端读 Supabase `agent_memory` 表(type=semantic),映射成 Flutter SemanticRule schema。
    若 DB 不可达,返回空数组而不是 500(Flutter 会自动 fallback 到本地 mock)。
    """
    if os.environ.get("MOCK_MODE", "false").lower() == "true":
        # MOCK_MODE 下返同样 shape 的占位数据,让 Flutter 测试期能联调
        return {"rules": [], "source": "mock"}

    try:
        from database import get_db

        res = (
            get_db()
            .table("agent_memory")
            .select("*")
            .eq("type", "semantic")
            .order("importance", desc=True)
            .limit(100)
            .execute()
        )
        rows = res.data or []
        rules = [_to_semantic_rule(r) for r in rows]
        return {"rules": rules, "source": "db", "count": len(rules)}
    except Exception as e:
        log.warning("list_memory_rules failed: %s", e)
        return {"rules": [], "source": "error", "error": str(e)[:120]}


class MemoryRuleUpdate(BaseModel):
    status: Optional[str] = Field(
        None, description="active | disabled (启用/禁用),其他状态由系统管理"
    )


@router.patch("/memory/rules/{rule_id}")
async def update_memory_rule(
    rule_id: str,
    payload: MemoryRuleUpdate,
    user_id: str = Depends(get_current_user),
):
    """启用/禁用规则。status='active' → is_active=true,status='disabled' → false。"""
    if payload.status not in ("active", "disabled"):
        raise HTTPException(status_code=400, detail="status must be 'active' or 'disabled'")

    if os.environ.get("MOCK_MODE", "false").lower() == "true":
        return {"ok": True, "rule_id": rule_id, "status": payload.status}

    try:
        from database import get_db
        is_active = payload.status == "active"
        get_db().table("agent_memory").update(
            {"is_active": is_active}
        ).eq("id", rule_id).execute()
        # 强制 SemanticMemory 缓存刷新
        try:
            from agent.memory import get_memory_manager
            get_memory_manager().semantic.force_refresh()
        except Exception:
            pass
        return {"ok": True, "rule_id": rule_id, "status": payload.status}
    except Exception as e:
        log.warning("update_memory_rule failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.delete("/memory/rules/{rule_id}")
async def delete_memory_rule(
    rule_id: str,
    user_id: str = Depends(get_current_user),
):
    """软删除规则:is_active=false,保留行用于审计。"""
    if os.environ.get("MOCK_MODE", "false").lower() == "true":
        return {"ok": True, "rule_id": rule_id, "deleted": True}

    try:
        from database import get_db
        get_db().table("agent_memory").update(
            {"is_active": False}
        ).eq("id", rule_id).execute()
        try:
            from agent.memory import get_memory_manager
            get_memory_manager().semantic.force_refresh()
        except Exception:
            pass
        return {"ok": True, "rule_id": rule_id, "deleted": True}
    except Exception as e:
        log.warning("delete_memory_rule failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.post("/memory/rule-proposals/{proposal_id}/approve")
async def approve_rule_proposal(
    proposal_id: str,
    user_id: str = Depends(get_current_user),
):
    """采纳规则提议 → 进入 14 天 Shadow Mode。

    MOCK_MODE 直接返成功;真实施需要 reflection 表 + S07 → SemanticMemory.try_promote
    (W7-W12)。
    """
    if os.environ.get("MOCK_MODE", "false").lower() == "true":
        return {
            "ok": True,
            "proposal_id": proposal_id,
            "promoted_rule_id": f"sm-{proposal_id[-6:]}",
            "shadow_mode_days": 14,
        }
    raise HTTPException(
        status_code=501,
        detail="规则采纳真实施在 W7-W12;当前请用 MOCK_MODE=true",
    )


# ── Reviews (复盘) ───────────────────────────────────────────────

def _mock_review(period: str, target_date: Optional[str]) -> Dict[str, Any]:
    """MOCK 复盘报告。Flutter UI 测试用,真实施在 S07 review-engine(W7-W12)。"""
    from datetime import datetime, timedelta, timezone
    if target_date:
        try:
            dt = datetime.fromisoformat(target_date)
        except Exception:
            dt = datetime.now(timezone.utc)
    else:
        dt = datetime.now(timezone.utc)

    delta = {"daily": 1, "weekly": 7, "monthly": 30}.get(period, 1)
    period_from = dt - timedelta(days=delta)
    period_to = dt

    metrics_per_period = {
        "daily": {"trades": 4, "win_rate": 0.75, "ev_pct": 2.1, "sharpe": 1.8},
        "weekly": {"trades": 18, "win_rate": 0.61, "ev_pct": 1.4, "sharpe": 1.8},
        "monthly": {"trades": 64, "win_rate": 0.58, "ev_pct": 1.1, "sharpe": 1.6},
    }
    m = metrics_per_period.get(period, metrics_per_period["daily"])

    headline_per_period = {
        "daily": "今日 4 笔 — 胜率 75%,EV +2.1%",
        "weekly": "本周 18 笔 — 胜率 61%,EV +1.4%,夏普 1.8",
        "monthly": "本月 64 笔 — 胜率 58%,EV +1.1%,最大回撤 -6.2%",
    }
    body_per_period = {
        "daily": "上午 SOL TRENDING_UP,聪明钱跟单 3 笔全胜;下午 EVM regime 转 RANGING,1 笔小亏出场。整体执行符合策略框架。",
        "weekly": "本周 RANGING 与 TRENDING_UP 各占一半。聪明钱跟单胜率高于规则触发,建议在 RANGING 期间收紧 BC 进场阈值至 8%。",
        "monthly": "全月 64 笔,SOL 链占 70%。CRISIS 出现 1 次但风控生效未触发交易。最大回撤 -6.2% 出现在 04-22 BTC 急跌窗口。",
    }

    return {
        "review_id": f"mock-{period}-{int(dt.timestamp())}",
        "period": period,
        "period_from": period_from.isoformat(),
        "period_to": period_to.isoformat(),
        "summary": {
            "headline": headline_per_period.get(period, headline_per_period["daily"]),
            "body": body_per_period.get(period, body_per_period["daily"]),
        },
        "insights": [
            {
                "type": "win_pattern",
                "text": "聪明钱 elite ≥ 75 + 流动性 > $50K + Regime ∈ {TRENDING_UP, BREAKOUT} 时,胜率 78% (n=14)",
                "evidence_trade_ids": ["t-2031", "t-2034", "t-2038"],
                "llm_judge_score": 0.82,
            },
            {
                "type": "loss_pattern",
                "text": "BC < 5% + 持有时长 > 4h 全部亏损 (n=5),建议加 4h 强制平仓",
                "evidence_trade_ids": ["t-1998", "t-2001", "t-2007"],
                "llm_judge_score": 0.71,
            },
            {
                "type": "risk_warning",
                "text": "CRISIS 期间 1 笔仍触发(HR16 已修),整体风险暴露在阈值内",
                "evidence_trade_ids": ["t-2042"],
                "llm_judge_score": 0.65,
            },
        ],
        "rule_proposals": [
            {
                "proposal_id": "rp-001",
                "human_readable": "RANGING regime 期间,BC 进场阈值从 5% 收紧到 8%",
                "formal_condition": {
                    "when": {"regime": "RANGING", "bc_pct": {"<": 8}},
                    "then": {"block_entry": True},
                },
                "sample_size": 22,
                "win_rate_diff": 12.4,
                "wilson_ci_lower": 0.58,
                "active_regimes": ["RANGING"],
                "reflection_id": "refl-2026-04-29",
            },
            {
                "proposal_id": "rp-002",
                "human_readable": "BC < 5% 且持仓 > 4h 强制平仓",
                "formal_condition": {
                    "when": {"bc_pct": {"<": 5}, "hold_hours": {">": 4}},
                    "then": {"force_close": True},
                },
                "sample_size": 14,
                "win_rate_diff": 8.7,
                "wilson_ci_lower": 0.51,
                "active_regimes": ["RANGING", "HIGH_VOLATILITY"],
                "reflection_id": "refl-2026-04-30",
            },
        ],
        "metrics": {
            "trade_count": m["trades"],
            "win_rate": m["win_rate"],
            "ev_pct": m["ev_pct"],
            "sharpe": m["sharpe"],
            "max_drawdown_pct": -6.2,
            "profit_factor": 1.92,
            "kelly_fraction": 0.18,
        },
        "cold_start_state": "normal",
        "source": "mock",
    }


@router.get("/reviews")
async def get_review(
    period: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    date: Optional[str] = Query(None, description="ISO 日期,默认今天"),
    user_id: str = Depends(get_current_user),
):
    """日/周/月复盘报告。

    v1(本次):S07 review_engine 真实施 — 从 agent_executions + token_performance
              汇总 metrics + 规则化产出 insights/rule_proposals。
    v2(后续):接 Claude Haiku 4.5 写 headline + body + 提议规则。

    Cold start:
      - trade_count=0 → "暂无交易,Agent 还在观察"
      - trade_count<5 → "样本不足"
    """
    if os.environ.get("MOCK_MODE", "false").lower() == "true":
        return _mock_review(period, date)

    try:
        from agent.review_engine import generate_review
        return await generate_review(period=period, target_date=date, user_id=user_id)
    except Exception as e:
        log.warning("review_engine failed, falling back to mock: %s", e)
        return _mock_review(period, date)

