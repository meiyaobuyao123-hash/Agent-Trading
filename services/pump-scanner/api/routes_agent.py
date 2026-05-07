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


# ── R39 v5:进程级 chat 对话历史(in-memory,30 min TTL) ──────
# 用 conversation_id(或 user_id 兜底)作为 key,保留最近 20 轮 messages。
# 前端发同一 conversation_id 即可保持上下文(LLM 看到完整历史)。
# 进程重启 history 丢失(可接受 — 内测期);后续可换 Redis 持久化。
import time as _time
import uuid as _uuid

_chat_conversations: Dict[str, "_ChatConv"] = {}  # noqa: F821
_CHAT_CONV_TTL_S = 1800     # 30 min 不活跃就清
_CHAT_CONV_MAX_MSGS = 40    # 最近 20 轮(每轮 user+assistant = 2 条)


class _ChatConv:
    """单个 chat 对话上下文。messages 是 anthropic API 格式 list。"""
    __slots__ = ("conv_id", "messages", "last_seen")

    def __init__(self, conv_id: str):
        self.conv_id = conv_id
        self.messages: List[Dict[str, Any]] = []
        self.last_seen: float = _time.time()


def _resolve_conv(req_conv_id: Optional[str], user_id: str) -> "_ChatConv":
    """获取或新建 chat 对话。conv_id 缺则用 user_id 作 key 兜底(同一用户的 active 对话)。"""
    _gc_chat_conversations()
    key = req_conv_id or f"user:{user_id}"
    conv = _chat_conversations.get(key)
    if conv is None:
        new_id = req_conv_id or str(_uuid.uuid4())
        conv = _ChatConv(new_id)
        # 同时按 conv_id 和 user_id key 存,便于下次查
        _chat_conversations[new_id] = conv
        if not req_conv_id:
            _chat_conversations[f"user:{user_id}"] = conv
    conv.last_seen = _time.time()
    return conv


def _append_chat_message(conv: "_ChatConv", role: str, content: Any) -> None:
    """追加一条 message(role=user/assistant),超过 _CHAT_CONV_MAX_MSGS 截断老的。"""
    conv.messages.append({"role": role, "content": content})
    if len(conv.messages) > _CHAT_CONV_MAX_MSGS:
        # 截到最近 N 条,但保证第一条是 user(anthropic 要求)
        conv.messages = conv.messages[-_CHAT_CONV_MAX_MSGS:]
        while conv.messages and conv.messages[0].get("role") != "user":
            conv.messages.pop(0)


def _gc_chat_conversations() -> None:
    """清掉 30 min 不活跃的对话。每次有调用时顺便扫一下。"""
    cutoff = _time.time() - _CHAT_CONV_TTL_S
    expired = [k for k, c in _chat_conversations.items() if c.last_seen < cutoff]
    for k in expired:
        _chat_conversations.pop(k, None)


def _truncate_history(
    messages: List[Dict[str, Any]],
    max_user_turns: int = 8,
) -> List[Dict[str, Any]]:
    """R39 v5: 按"真用户回合"截断 anthropic 历史,避免砍断 tool_use/tool_result 配对。

    真用户回合 = role=="user" 且 content 是 str(普通用户输入)。
    tool_result 包装在 role=user, content=list 里,不算真用户回合。

    保留最近 max_user_turns 个真用户回合 + 它们之后的所有 LLM/tool 块。
    """
    if not messages:
        return messages
    user_turn_indices = [
        i for i, m in enumerate(messages)
        if m.get("role") == "user" and isinstance(m.get("content"), str)
    ]
    if len(user_turn_indices) <= max_user_turns:
        return messages
    cut_from = user_turn_indices[-max_user_turns]
    return messages[cut_from:]


# ── 请求/响应模型 ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户输入")
    context: Optional[Dict[str, Any]] = None
    # W3 D4: 可选 safety ctx,传入后跑 SafetyEngine.check_trade
    # 即使不传,全局 CB(任一 blocked 级 CB active)也会拦截所有 chat
    safety_ctx: Optional[Dict[str, Any]] = None
    # R39 v5: 多轮对话保持上下文。Flutter App 拿到 response.conversation_id
    # 下次发同一 ID,后端继续追加历史。空时后端用 user_id 维持当前 active 对话。
    conversation_id: Optional[str] = None


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
    conversation_id: Optional[str] = None  # R39 v5


# ── R40: 接 cost_guard / input_filter / rollout_gate / audit_log ──
# 参考 _check_safety_for_chat 的 helper-style;失败永远不阻断 chat(降级 + log)

_NIL_UUID = "00000000-0000-0000-0000-000000000000"


def _coerce_device_uuid(user_id: str) -> str:
    """security_audit_log.device_id 是 UUID NOT NULL。
    user_id 不一定是 UUID(DEV mode 下可能是任意字符串)→ 用 nil UUID 占位。
    生产 Supabase JWT 的 user_id 是 UUID 时直接用。
    """
    import re as _re
    if user_id and _re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", user_id, _re.I):
        return user_id
    return _NIL_UUID


def _audit_log_safety_event(
    user_id: str,
    event_type: str,
    severity: str,
    payload: Dict[str, Any],
) -> None:
    """写一条 security_audit_log。
    event_type 必须是 schema enum 之一(safety_block / cb_trigger / hitl_decision 等)。
    失败永不抛(catch all)。
    """
    try:
        from local_db import _get_conn
        conn = _get_conn()
        device_uuid = _coerce_device_uuid(user_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO security_audit_log
                  (device_id, event_type, severity, payload)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (device_uuid, event_type, severity, json.dumps(payload, ensure_ascii=False, default=str)),
            )
        conn.commit()
    except Exception as e:
        log.warning("[audit] insert fail event=%s sev=%s err=%s", event_type, severity, e)


async def _check_guards_for_chat(
    req: ChatRequest,
    user_id: str,
) -> Optional[str]:
    """R40: chat pre-check 三合一(rollout_gate + input_filter + cost_guard)。
    返 None = 通过;返 str = BLOCK 原因。

    各步骤失败(import 失败 / DB down)→ 降级放行(不阻断 chat),只记 log。
    BLOCK 命中 → 写 security_audit_log(safety_block,severity warn/critical)。
    """
    # ── 1. rollout_gate("agent_v1" feature 默认 100,实际不拦,埋点用)─
    try:
        from agent.rollout_gate import is_in_rollout
        device_id = (req.context or {}).get("device_id") or user_id or ""
        if not is_in_rollout(device_id, "agent_v1"):
            _audit_log_safety_event(user_id, "safety_block", "warn", {
                "stage": "rollout_gate",
                "feature": "agent_v1",
                "device_id": device_id,
                "msg_head": (req.message or "")[:80],
            })
            return "Agent v1 未对当前设备开放(灰度)"
    except Exception as e:
        log.debug("[rollout_gate] skip: %s", e)

    # ── 2. input_filter(prompt injection / hitl_bypass / regulation_skirt)──
    try:
        from agent.input_filter import filter_combined
        res = filter_combined(req.message)
        if not res.passed:
            _audit_log_safety_event(user_id, "safety_block", "critical", {
                "stage": "input_filter",
                "matched_classes": res.matched_classes,
                "violations": res.violations[:5],
                "msg_head": (req.message or "")[:80],
            })
            return f"输入被安全过滤拦截({', '.join(res.matched_classes)})"
    except Exception as e:
        log.debug("[input_filter] skip: %s", e)

    # ── 3. cost_guard(全局月预算 / model 降级)─────────────
    try:
        from agent.cost_guard import get_cost_guard
        guard = get_cost_guard()
        allowed, actual_model, reason = await guard.check_before_call(
            intended_model="claude-haiku-4-5-20251001",
            intended_level="L2",
        )
        if not allowed:
            _audit_log_safety_event(user_id, "safety_block", "critical", {
                "stage": "cost_guard",
                "reason": reason,
                "msg_head": (req.message or "")[:80],
            })
            return f"系统月度预算限制:{reason}"
        # 通过 — 降级仅 log,不阻断
        if actual_model and actual_model != "claude-haiku-4-5-20251001":
            log.info("[cost_guard] model degraded → %s (%s)", actual_model, reason)
    except Exception as e:
        log.debug("[cost_guard] skip: %s", e)

    return None


def _enrich_context_with_memory_and_prompt(
    base_context: Dict[str, Any],
    user_id: str,
) -> Dict[str, Any]:
    """R40: 给 LLM context 注入 prompt_loader 灰度 meta + episodic_memory recall。

    只在新会话第一轮(parse_strategy 看到 conversation_history 空)时生效 —
    R39 v5 的 LLMParser 接到 history 时会跳过 context 注入。

    失败永不抛(只是 enrichment,不影响主流程)。
    """
    ctx = dict(base_context) if base_context else {}

    # ── prompt_loader 灰度 meta(P01 chat_clarify 当前选中版本)──
    try:
        from agent.prompt_loader import get_prompt_loader
        loader = get_prompt_loader()
        # lazy load:singleton 没人启动调 load_from_disk,首次访问空时 load 一次
        if not loader.list_prompts():
            n = loader.load_from_disk()
            log.info("[prompt_loader] lazy loaded %d prompt versions", n)
        device_id = ctx.get("device_id") or user_id or ""
        spec = loader.select_version("P01", device_id)  # frontmatter prompt_id="P01"
        if spec is not None:
            ctx["prompt_meta"] = {
                "id": "P01",
                "version": getattr(spec, "version", None),
                "status": getattr(spec, "status", None),
                "rollout_pct": getattr(spec, "rollout_pct", None),
                "model": (spec.frontmatter.get("model") if hasattr(spec, "frontmatter") else None),
            }
    except Exception as e:
        log.debug("[prompt_loader] skip enrichment: %s", e)

    # ── episodic_memory + semantic_memory(R40+R41:用单例,缓存生效)──
    try:
        from agent.memory import get_memory_manager
        mem = get_memory_manager()

        # episodic:user 最近 3 条历史案例(R40)
        episodes = mem.episodic.search(limit=3) if hasattr(mem, "episodic") else []
        if episodes:
            slim = []
            for ep in episodes[:3]:
                if isinstance(ep, dict):
                    slim.append({
                        "token": ep.get("token_symbol") or ep.get("token"),
                        "chain": ep.get("chain"),
                        "pnl_pct": ep.get("pnl_pct"),
                        "outcome": ep.get("outcome"),
                    })
            if slim:
                ctx["recent_episodes"] = slim

        # R41 P0:semantic 已 graduated 规则 top 5 注入,LLM 决策可参考
        active_rules = mem.semantic.get_all_active() if hasattr(mem, "semantic") else []
        if active_rules:
            ctx["active_semantic_rules"] = [
                {
                    "id": r.get("id"),
                    "summary": (r.get("content") or "")[:200],
                    "chain": r.get("chain"),
                    "trigger_source": r.get("trigger_source"),
                }
                for r in active_rules[:5]
            ]
    except Exception as e:
        log.debug("[memory] skip enrichment: %s", e)

    return ctx


# ── R41 P0/P1: output_filter LLM 输出 + working_memory 埋点 ──

def _filter_llm_output(
    user_id: str,
    ai_message: str,
) -> str:
    """R41 P0:LLM 输出过 output_filter (C1-C5)。
    检测到违规话术(稳赚不赔/百倍/all in 等)→ 写 audit + 用 sanitized_text 替换。
    失败永不抛(降级返原文)。
    """
    if not ai_message:
        return ai_message
    try:
        from agent.output_filter import filter_output
        res = filter_output(ai_message, persona="中级")
        if not res.passed:
            _audit_log_safety_event(user_id, "safety_block", "warn", {
                "stage": "output_filter",
                "violations": (res.violations or [])[:5],
                "ai_msg_head": ai_message[:80],
            })
            return res.sanitized_text or "[输出被安全过滤]"
    except Exception as e:
        log.debug("[output_filter] skip: %s", e)
    return ai_message


def _record_chat_to_working_memory(
    user_id: str,
    user_message: str,
    ai_message: str,
    has_strategy: bool,
) -> None:
    """R41 P1:把本轮 chat 写进 working_memory(24h 滑动窗口)。
    给 reflection_loop 提供原料。失败永不抛。
    """
    try:
        from agent.memory import get_memory_manager
        mem = get_memory_manager()
        if not hasattr(mem, "working"):
            return
        mem.working.add({
            "kind": "chat",
            "user_id": user_id,
            "user_msg": (user_message or "")[:200],
            "ai_msg_head": (ai_message or "")[:200],
            "has_strategy": bool(has_strategy),
            "summary": f"chat: {(user_message or '')[:50]} → {(ai_message or '')[:50]}",
            "ts": _time.time(),
        })
    except Exception as e:
        log.debug("[working_memory] skip add: %s", e)


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

    # ── R40: rollout_gate + input_filter + cost_guard 三合一(BLOCK 不消耗 quota)─
    guard_block = await _check_guards_for_chat(req, user_id)
    if guard_block is not None:
        return ChatResponse(
            strategy=None,
            message=f"⚠️ {guard_block}",
            requires_confirmation=False,
        )
    # ─────────────────────────────────────────────────────────────

    # ── R47: Credit 算力检查(余额 < $0.0001 拒)─
    try:
        from agent import credit_service
        ok, reason = credit_service.can_proceed(user_id)
        if not ok:
            return ChatResponse(
                strategy=None,
                message=f"⚠️ {reason}。请先充值算力 → /app/credit",
                requires_confirmation=False,
            )
    except Exception as e:
        log.debug("[credit gate] skip: %s", e)
    # ─────────────────────────────────────────────────────────────

    # R39 root-cause:删掉关键词预触发 hack。
    # 现在 LLMParser 直接暴露 14 工具给 LLM(ALL_TOOLS),由 LLM 自己 route。
    # 见 agent/llm_parser.py — 用户问"涨幅 top"会自动调 query_top_movers,
    # 问"建策略"会自动调 create_strategy,无需关键词预筛。

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

    # R40: 注入 prompt_loader 灰度 meta + episodic_memory recall(只第一轮生效)
    context = _enrich_context_with_memory_and_prompt(context, user_id)

    # R39 v5: 接 4 层 memory(in-memory chat 对话历史)
    conv = _resolve_conv(req.conversation_id, user_id)
    history_snapshot = list(conv.messages)  # immutable snapshot 喂给 parser

    strategy_spec, ai_message, full_messages = await _llm_parser.parse_strategy(
        req.message,
        context if context else None,
        conversation_history=history_snapshot if history_snapshot else None,
    )

    # 把 parser 跑完的完整 messages(含 tool_use/tool_result + final assistant)写回 conv,
    # 截断到最近 8 个真用户回合避免无限增长 + 避免砍断 tool 配对
    conv.messages = _truncate_history(full_messages, max_user_turns=8)
    conv.last_seen = _time.time()

    # R41 P0:output_filter 过 LLM 输出(C1-C5);违规则 sanitized + 写 audit
    ai_message = _filter_llm_output(user_id, ai_message)

    # R41 P1:写 working_memory(24h 滑动窗口,给 reflection_loop 用)
    _record_chat_to_working_memory(user_id, req.message, ai_message, strategy_spec is not None)

    # R47: 按实际 LLM token 用量扣 credit
    try:
        from agent import credit_service
        usage = getattr(_llm_parser, "_last_usage", None) or {}
        if (usage.get("in") or 0) > 0 or (usage.get("out") or 0) > 0:
            credit_service.deduct(
                user_id,
                usage.get("model", "claude-sonnet-4-6"),
                int(usage.get("in", 0)),
                int(usage.get("out", 0)),
                request_id=conv.conv_id,
            )
    except Exception as e:
        log.debug("[credit deduct] skip: %s", e)

    return ChatResponse(
        strategy=strategy_spec,
        message=ai_message,
        requires_confirmation=strategy_spec is not None,
        conversation_id=conv.conv_id,
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

    # ── R40: rollout_gate + input_filter + cost_guard ────────────
    guard_block = await _check_guards_for_chat(req, user_id)
    if guard_block is not None:
        async def _guard_error():
            payload = json.dumps({
                'type': 'error',
                'message': f'⚠️ {guard_block}',
            }, ensure_ascii=False)
            yield f"data: {payload}\n\n"
        return StreamingResponse(_guard_error(), media_type="text/event-stream")
    # ─────────────────────────────────────────────────────────────

    # R39 root-cause:删掉关键词预触发 hack(stream 同步删除)。
    # LLMParser.parse_strategy_stream 内部已暴露 14 工具,LLM 自主 route。

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

    # R40: 注入 prompt_loader 灰度 meta + episodic_memory recall
    context = _enrich_context_with_memory_and_prompt(context, user_id)

    # R39 v5: 接 4 层 memory(in-memory chat 对话历史)
    conv = _resolve_conv(req.conversation_id, user_id)
    history_snapshot = list(conv.messages)

    async def _event_generator():
        import json as _json
        # 首条 yield meta 让 Flutter 拿到 conversation_id
        meta_evt = {"type": "meta", "conversation_id": conv.conv_id}
        yield f"data: {_json.dumps(meta_evt, ensure_ascii=False)}\n\n"

        final_messages: List[Dict[str, Any]] = []
        try:
            async for event in _llm_parser.parse_strategy_stream(
                req.message,
                context if context else None,
                conversation_history=history_snapshot if history_snapshot else None,
            ):
                # 拦截 final_messages 不下发 SSE,只用于持久化
                if event.get("type") == "final_messages":
                    final_messages = event.get("messages") or []
                    continue
                yield f"data: {_json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'type': 'error', 'message': str(e)[:200]})}\n\n"

        # 流结束后写回 conv(截断到最近 8 个真用户回合)
        if final_messages:
            conv.messages = _truncate_history(final_messages, max_user_turns=8)
            conv.last_seen = _time.time()

        # R41 P0:对累积的 assistant text 跑一次 output_filter;违规则 yield warning event
        # (流式不能 sanitize 已发出 token,只能事后告警 + 写 audit)
        try:
            assistant_text = ""
            for m in final_messages or []:
                if m.get("role") == "assistant" and isinstance(m.get("content"), str):
                    assistant_text = m["content"]  # 末尾那条
            if assistant_text:
                from agent.output_filter import filter_output
                fres = filter_output(assistant_text, persona="中级")
                if not fres.passed:
                    _audit_log_safety_event(user_id, "safety_block", "warn", {
                        "stage": "output_filter_stream",
                        "violations": (fres.violations or [])[:5],
                        "ai_msg_head": assistant_text[:80],
                    })
                    warning = {"type": "warning", "message": "本次回复含违规话术,请审慎参考"}
                    yield f"data: {_json.dumps(warning, ensure_ascii=False)}\n\n"
        except Exception as e:
            log.debug("[output_filter stream] skip: %s", e)

        # R41 P1:写 working_memory(同非流式)
        try:
            assistant_for_mem = ""
            for m in final_messages or []:
                if m.get("role") == "assistant" and isinstance(m.get("content"), str):
                    assistant_for_mem = m["content"]
            _record_chat_to_working_memory(user_id, req.message, assistant_for_mem, False)
        except Exception as e:
            log.debug("[working_memory stream] skip: %s", e)

        # R47: stream 路径也按 LLM token 用量扣 credit
        try:
            from agent import credit_service
            usage = getattr(_llm_parser, "_last_usage", None) or {}
            if (usage.get("in") or 0) > 0 or (usage.get("out") or 0) > 0:
                credit_service.deduct(
                    user_id,
                    usage.get("model", "claude-sonnet-4-6"),
                    int(usage.get("in", 0)),
                    int(usage.get("out", 0)),
                    request_id=conv.conv_id,
                )
        except Exception as e:
            log.debug("[credit deduct stream] skip: %s", e)

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
            # 不是 JSON，先用 LLM 解析(R39 v5 改 3 元组,R42 修 unpacking bug)
            parsed = await _llm_parser.parse_strategy(msg)
            if not parsed or len(parsed) < 1:
                return {"error": "无法解析策略", "trigger_count": 0}
            spec = parsed[0]  # (spec, ai_message, full_messages) → 取 spec
            if spec is None:
                return {"error": "LLM 解析失败", "trigger_count": 0}

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
    """[deprecated R37 path] 将策略从 paper 切换到 live 模式 — 走 R37 5 项硬门槛。
    新代码请用 POST /strategies/{id}/promote-to-live。
    """
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


# ── R42 P0.4: 用户主动 promote 流程 — 跳过 R37 5 项门槛,改为解锁条件 ──

class PromoteToLiveRequest(BaseModel):
    """R42 P0.4 用户主动 promote 请求体 — 解锁条件 4 项 checklist"""
    has_wallet: bool = Field(..., description="已连接钱包(WalletService.wallets 非空)")
    disclaimer_accepted: bool = Field(..., description="已读 + 同意《免责声明》")
    risk_acknowledged: bool = Field(..., description="已勾选'我知道会亏钱'")
    max_position_usd: Optional[float] = Field(None, description="单笔金额上限(默认 500,可调到 5000;R47 P6)")


@router.post("/strategies/{strategy_id}/promote-to-live")
async def promote_to_live(
    strategy_id: str,
    req: PromoteToLiveRequest,
    user_id: str = Depends(get_current_user),
):
    """R42 P0.4 用户主动 promote → live。

    取代 /go-live 的 R37 5 项硬门槛(30 天 30 笔 EV 回撤),改为:
    - 用户主动决策 + 4 项解锁条件 checklist
    - 通过 force=True bypass R37 门槛
    - 写 audit log: event_type=admin_action(用户级 promote 也算 admin action)
    - 在策略 risk_params 写入 max_position_usd(R47 P6:用户选 $500/$5000)
    """
    strategy = _strategy_mgr.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    if strategy.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="无权限操作")
    if strategy.get("mode") == "live":
        return {
            "strategy": strategy,
            "message": "策略已在实盘模式",
            "promoted": False,
        }

    # R42 P0.4 HR31 解锁条件硬检查
    missing = []
    if not req.has_wallet:
        missing.append("钱包未连接")
    if not req.disclaimer_accepted:
        missing.append("免责声明未同意")
    if not req.risk_acknowledged:
        missing.append("风险确认未勾选")
    if missing:
        return {
            "promoted": False,
            "error": "解锁条件不满足",
            "missing": missing,
        }

    # R47 P6 单笔金额上限:默认 $500 / 用户可调到 $5000
    max_position = float(req.max_position_usd or 500)
    max_position = max(10, min(5000, max_position))

    # 先写 max_position_usd 到策略,再 force=True go_live
    try:
        _strategy_mgr.update_strategy(strategy_id, {
            "max_position_usd": max_position,
        })
    except Exception as e:
        log.warning("[promote_to_live] 写 max_position 失败: %s", e)

    # R37 force=True 跳过 5 项门槛(用户主动决策免门槛)
    result = _strategy_mgr.go_live(strategy_id, force=True, actor="user")
    if not result:
        raise HTTPException(status_code=400, detail="切换失败:策略状态不允许(非 active 或非 paper)")

    # 写审计 log
    try:
        _audit_log_safety_event(user_id, "admin_action", "info", {
            "stage": "promote_to_live",
            "strategy_id": strategy_id,
            "max_position_usd": max_position,
            "disclaimer_accepted": True,
        })
    except Exception:
        pass

    return {
        "strategy": result,
        "message": f"已切换到实盘模式,单笔上限 ${max_position:.0f}",
        "promoted": True,
    }


# ── R42 P0.4: 一键降回 paper(无条件成功)──

@router.post("/strategies/{strategy_id}/demote-to-paper")
async def demote_to_paper(
    strategy_id: str,
    user_id: str = Depends(get_current_user),
):
    """一键降回 paper 模式 — 立即生效,无审批"""
    strategy = _strategy_mgr.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    if strategy.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="无权限操作")
    if strategy.get("mode") == "paper":
        return {"strategy": strategy, "message": "策略已在模拟盘模式"}

    result = _strategy_mgr.update_strategy(strategy_id, {"mode": "paper"})
    if not result:
        raise HTTPException(status_code=500, detail="降级失败")

    try:
        _audit_log_safety_event(user_id, "admin_action", "info", {
            "stage": "demote_to_paper",
            "strategy_id": strategy_id,
        })
    except Exception:
        pass

    return {"strategy": result, "message": "已降回模拟盘模式"}


# ── R42 P0.5: 策略 risk_params 编辑 ──

class RiskParamsUpdateRequest(BaseModel):
    """R42 P0.5 用户从 Flutter 改 risk_params"""
    max_slippage_pct: Optional[float] = Field(None, ge=0.001, le=0.5, description="0.01 = 1%")
    stop_loss_pct: Optional[float] = Field(None, ge=0.05, le=0.50, description="0.30 = 30%")
    take_profit_pct: Optional[float] = Field(None, ge=0.10, le=10.0, description="1.0 = 100%")
    max_position_usd: Optional[float] = Field(None, ge=10, le=5000, description="单笔上限")
    trailing_stop_pct: Optional[float] = Field(None, ge=0, le=0.5, description="追踪止损")
    priority_fee_sol: Optional[float] = Field(None, ge=0.0001, le=0.1, description="Solana 优先 Gas")
    mev_bribe_sol: Optional[float] = Field(None, ge=0, le=0.1, description="Jito MEV 贿赂")


@router.patch("/strategies/{strategy_id}/risk-params")
async def update_risk_params(
    strategy_id: str,
    req: RiskParamsUpdateRequest,
    user_id: str = Depends(get_current_user),
):
    """R42 P0.5 更新策略风控参数(滑点/止盈止损/MEV/Gas Fee)。
    Flutter 详情页"风控设置"折叠区调用。

    传 None 的字段不改;传值的写 strategies 表对应字段。
    """
    strategy = _strategy_mgr.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    if strategy.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="无权限操作")

    updates = req.model_dump(exclude_none=True)
    if not updates:
        return {"strategy": strategy, "message": "无字段更新"}

    result = _strategy_mgr.update_strategy(strategy_id, updates)
    if not result:
        raise HTTPException(status_code=500, detail="更新失败")

    return {"strategy": result, "message": "风控参数已更新", "updated_fields": list(updates.keys())}


# ── R42 P0.4: 合并交易记录(paper + live)──

@router.get("/trades-merged/{strategy_id}")
async def list_trades_merged(
    strategy_id: str,
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(get_current_user),
):
    """R42 P0.4 同时拉 paper + live 交易记录,按时间倒序合并。

    返:
      {"trades": [...], "paper_count": N, "live_count": M, "total": N+M}
    每条带 mode 字段("paper"/"live")让 UI 区分。
    """
    strategy = _strategy_mgr.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    if strategy.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="无权限操作")

    from database import get_db
    db = get_db()

    paper_rows: List[Dict[str, Any]] = []
    live_rows: List[Dict[str, Any]] = []

    # paper trades
    try:
        res = (
            db.table("agent_paper_trades").select("*")
            .eq("user_id", user_id).eq("strategy_id", strategy_id)
            .order("created_at", desc=True).limit(limit).execute()
        )
        for r in (res.data or []):
            r["mode"] = "paper"
            paper_rows.append(r)
    except Exception as e:
        log.warning("[trades-merged] paper fetch fail: %s", e)

    # live executions(R42 P0.1 position_monitor 写,真实交易记录)
    try:
        res = (
            db.table("agent_executions").select("*")
            .eq("strategy_id", strategy_id)
            .order("created_at", desc=True).limit(limit).execute()
        )
        for r in (res.data or []):
            # 兼容字段:agent_executions 有 amount_usd / token_address / action
            r["mode"] = "live"
            r["asset"] = r.get("asset") or r.get("token_symbol") or (r.get("token_address", "")[:8])
            r["side"] = r.get("side") or r.get("action")
            live_rows.append(r)
    except Exception as e:
        log.warning("[trades-merged] live fetch fail: %s", e)

    merged = sorted(
        paper_rows + live_rows,
        key=lambda r: r.get("created_at", ""),
        reverse=True,
    )[:limit]

    return {
        "trades": merged,
        "paper_count": len(paper_rows),
        "live_count": len(live_rows),
        "total": len(merged),
    }


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


# ═══════════════════════════════════════════════════════════
# W3 D5+: 共创状态机 endpoints (S04 signal-strategy-builder)
# ═══════════════════════════════════════════════════════════
#
# 端点:
#   GET  /cocreation/state                — 拿当前活跃 state(没有则 null)
#   POST /cocreation/start                — 创建新 state(初始 message)
#   POST /cocreation/{conv_id}/message    — 追加 message + 自动建议下一 stage
#   POST /cocreation/{conv_id}/transition — 显式状态转移(LLM 决策时用)
#   POST /cocreation/{conv_id}/abort      — 用户主动放弃
#
# 不调 LLM,只管 state 持久化与转移。Flutter 拿 stage 渲染 stepper。


class CocreationStartRequest(BaseModel):
    skill_name: str = Field("signal-strategy-builder")
    initial_message: Optional[str] = None


class CocreationMessageRequest(BaseModel):
    role: str = Field(..., description="user | assistant")
    content: str
    has_draft: Optional[bool] = False
    user_satisfied: Optional[bool] = None


class CocreationTransitionRequest(BaseModel):
    to_stage: str
    draft_data: Optional[Dict[str, Any]] = None
    dry_run_result: Optional[Dict[str, Any]] = None
    saved_strategy_id: Optional[str] = None


@router.get("/cocreation/state")
async def get_cocreation_state(
    skill_name: str = Query("signal-strategy-builder"),
    user_id: str = Depends(get_current_user),
):
    """获取用户当前活跃的共创 state。"""
    try:
        from agent.orchestration.cocreation_state_machine import load_active_state
        state = load_active_state(user_id, skill_name)
        return {"state": state}
    except Exception as e:
        log.warning("cocreation get_state failed: %s", e)
        return {"state": None, "error": str(e)[:120]}


@router.post("/cocreation/start")
async def start_cocreation(
    req: CocreationStartRequest,
    user_id: str = Depends(get_current_user),
):
    """创建新的共创 state(stage=clarifying)。"""
    try:
        from agent.orchestration.cocreation_state_machine import (
            create_state,
            load_active_state,
        )
        # 已有活跃 state 直接返回(避免重复创建)
        existing = load_active_state(user_id, req.skill_name)
        if existing:
            return {"state": existing, "reused": True}
        state = create_state(user_id, req.skill_name, req.initial_message)
        if not state:
            raise HTTPException(status_code=500, detail="create_state failed")
        return {"state": state, "reused": False}
    except HTTPException:
        raise
    except Exception as e:
        log.warning("cocreation start failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.post("/cocreation/{conv_id}/message")
async def append_cocreation_message(
    conv_id: str,
    req: CocreationMessageRequest,
    user_id: str = Depends(get_current_user),
):
    """追加 message;基于启发式建议下一 stage(不强制转移)。"""
    try:
        from agent.orchestration.cocreation_state_machine import (
            append_message,
            load_active_state,
            suggest_next_stage,
        )
        ok = append_message(conv_id, req.role, req.content)
        if not ok:
            raise HTTPException(status_code=404, detail="conversation not found")
        # 基于当前 stage + 用户消息建议下一 stage
        # 重新 load 拿到当前 stage
        state = None
        try:
            from local_db import _get_conn
            conn = _get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT stage, draft_data FROM conversation_states WHERE conversation_id = %s",
                    (conv_id,),
                )
                row = cur.fetchone()
                if row:
                    current_stage = row[0]
                    has_draft = row[1] is not None
                    suggested = suggest_next_stage(
                        current_stage, req.content,
                        has_draft=has_draft,
                        user_satisfied=req.user_satisfied,
                    )
                    return {"ok": True, "current_stage": current_stage,
                            "suggested_next_stage": suggested}
        except Exception:
            pass
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        log.warning("cocreation message failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.post("/cocreation/{conv_id}/transition")
async def transition_cocreation(
    conv_id: str,
    req: CocreationTransitionRequest,
    user_id: str = Depends(get_current_user),
):
    """显式状态转移。"""
    try:
        from agent.orchestration.cocreation_state_machine import transition
        ok, err = transition(
            conv_id, req.to_stage,
            draft_data=req.draft_data,
            dry_run_result=req.dry_run_result,
            saved_strategy_id=req.saved_strategy_id,
        )
        if not ok:
            raise HTTPException(status_code=400, detail=err or "transition failed")
        return {"ok": True, "stage": req.to_stage}
    except HTTPException:
        raise
    except Exception as e:
        log.warning("cocreation transition failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.post("/cocreation/{conv_id}/abort")
async def abort_cocreation(
    conv_id: str,
    user_id: str = Depends(get_current_user),
):
    """用户主动放弃。"""
    try:
        from agent.orchestration.cocreation_state_machine import transition
        ok, err = transition(conv_id, "aborted")
        if not ok:
            raise HTTPException(status_code=400, detail=err or "abort failed")
        return {"ok": True, "stage": "aborted"}
    except HTTPException:
        raise
    except Exception as e:
        log.warning("cocreation abort failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)[:200])


# ── /cocreation/chat — LLM 串联完整 loop ──────────────────────


class CocreationChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    skill_name: str = Field("signal-strategy-builder")


class ScoutEvaluateRequest(BaseModel):
    """手动触发 ScoutLoop 评估一个信号(测试 / Scout 接入桥)。"""
    signal_payload: Dict[str, Any] = Field(..., description="数据载荷(对齐 DataEvent.data)")
    source: str = Field(..., min_length=1, description="hot_coin/pump/kol/smart_money/...")
    chain: Optional[str] = None
    token_address: Optional[str] = None
    token_name: Optional[str] = None
    mode_override: Optional[str] = None
    dry_run: bool = True
    max_dispatch: int = Field(5, ge=1, le=20)


@router.post("/scout/evaluate")
async def scout_evaluate(
    req: ScoutEvaluateRequest,
    user_id: str = Depends(get_current_user),
):
    """手动触发 ScoutLoop:给一个信号 → 返回命中策略 + NotifyLoop verdicts。

    生产环境的 EventBus 自动订阅由 main.py / event_listener.py 负责。
    本端点用于测试 / 调试 / Scout 路径手动触发。
    默认 dry_run=true(避免误触发真金)。
    """
    try:
        from agent.loops.scout_loop import get_scout_loop
        loop = get_scout_loop()
        result = await loop.process(
            signal_payload=req.signal_payload,
            source=req.source,
            chain=req.chain,
            token_address=req.token_address,
            token_name=req.token_name,
            mode_override=req.mode_override,
            dry_run=req.dry_run,
            max_dispatch=req.max_dispatch,
        )
        return {
            "ok": result.ok, "source": result.source,
            "strategies_evaluated": result.strategies_evaluated,
            "triggered": result.triggered,
            "dispatched": result.dispatched,
            "skipped_daily_limit": result.skipped_daily_limit,
            "notify_results": result.notify_results,
            "error": result.error,
            "latency_ms": result.latency_ms,
        }
    except Exception as e:
        log.warning("scout evaluate failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)[:200])


class NotifyTriggerRequest(BaseModel):
    """手动触发 notify_loop(测试 / Scout 接入桥)。"""
    event: Dict[str, Any] = Field(...,
        description="StrategyTriggeredEvent dict(strategy_id/user_id/strategy_name/matched_token/matched_chain/trigger_context)")
    mode: str = Field("paper", pattern="^(paper|notify|auto)$")
    thesis: Optional[Dict[str, Any]] = None
    account_balance_usd: float = 1000.0
    portfolio_pct_in_chain: float = 0.0
    recent_trades_24h: int = 0
    fixed_pct: float = 0.05
    dry_run: bool = False


@router.post("/notify/trigger")
async def notify_trigger(
    req: NotifyTriggerRequest,
    user_id: str = Depends(get_current_user),
):
    """手动触发 notify_loop(Scout 接入前的桥;dry_run 测试用)。"""
    try:
        from agent.loops.notify_loop import get_notify_loop
        loop = get_notify_loop()
        result = await loop.process(
            event=req.event,
            mode=req.mode,
            thesis=req.thesis,
            account_balance_usd=req.account_balance_usd,
            portfolio_pct_in_chain=req.portfolio_pct_in_chain,
            recent_trades_24h=req.recent_trades_24h,
            position_mode="fixed_pct",
            fixed_pct=req.fixed_pct,
            dry_run=req.dry_run,
        )
        return {
            "ok": result.ok, "verdict": result.verdict, "mode": result.mode,
            "reason": result.reason,
            "position_usd": result.position_usd,
            "capped_by": result.capped_by,
            "safety_block": result.safety_block,
            "risk_block": result.risk_block,
            "paper_trade": result.paper_trade,
            "approval_id": result.approval_id,
            "push_sent_count": result.push_sent_count,
            "push_deep_link": result.push_deep_link,
            "latency_ms": result.latency_ms,
            "extra": result.extra,
        }
    except Exception as e:
        log.warning("notify trigger failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)[:200])


class ReflectRunRequest(BaseModel):
    trigger: str = Field("daily", pattern="^(daily|count|emergency)$")
    lookback_days: int = Field(7, ge=1, le=90)
    emergency_pnl_pct: Optional[float] = None
    emergency_amount_usd: Optional[float] = None


@router.post("/reflect/run")
async def reflect_run(
    req: ReflectRunRequest,
    user_id: str = Depends(get_current_user),
):
    """手动触发反思 cycle(Admin / debug 用)。

    cron 自动触发由 main.py 的 scheduler 注册(daily 20:00)。
    """
    try:
        from agent.loops.reflect_loop import get_reflect_loop
        loop = get_reflect_loop()
        result = await loop.run_cycle(
            device_id=user_id,
            trigger=req.trigger,
            lookback_days=req.lookback_days,
            emergency_pnl_pct=req.emergency_pnl_pct,
            emergency_amount_usd=req.emergency_amount_usd,
        )
        return {
            "ok": result.ok,
            "trigger": result.trigger,
            "trades_analyzed": result.trades_analyzed,
            "new_rules_proposed": result.new_rules_proposed,
            "dedupe_skipped": result.dedupe_skipped,
            "gate_blocked": result.gate_blocked,
            "promoted": result.promoted,
            "promoted_rule_ids": result.promoted_rule_ids,
            "reflection_id": result.reflection_id,
            "error": result.error,
            "latency_ms": result.latency_ms,
        }
    except Exception as e:
        log.warning("reflect run failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.post("/cocreation/chat")
async def cocreation_chat(
    req: CocreationChatRequest,
    user_id: str = Depends(get_current_user),
):
    """共创 chat 主入口 — 接 P01/P11 + 状态机 + T12。

    单 turn 处理:
      load_active_state → append user → 路由到 stage handler →
      调 LLM(失败降级)→ 解析 → transition → append assistant → 返回
    """
    try:
        from agent.loops.chat_loop import get_cocreation_loop
        loop = get_cocreation_loop()
        result = await loop.handle(
            device_id=user_id,
            user_message=req.message,
            skill_name=req.skill_name,
        )
        return {
            "ok": result.ok,
            "assistant_text": result.assistant_text,
            "stage": result.stage,
            "conversation_id": result.conversation_id,
            "draft_data": result.draft_data,
            "saved_strategy_id": result.saved_strategy_id,
            "suggested_next_stage": result.suggested_next_stage,
            "source": result.source,
            "error": result.error,
            "extra": result.extra,
        }
    except Exception as e:
        log.warning("cocreation chat failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)[:200])


# ──────────────────────────────────────────────────────────────
# R47 P6 — 半自动交易撤销窗口 endpoints
# ──────────────────────────────────────────────────────────────

@router.get("/trades/pending")
async def list_pending_semi_auto(
    limit: int = 20,
    user_id: str = Depends(get_current_user),
):
    """列出当前用户的半自动交易(pending / executed / cancelled / failed 全部)。
    R47 P6 — 给 UI 倒计时页 + 历史列表用。
    """
    from agent import semi_auto_service
    return {"trades": semi_auto_service.list_user_pending(user_id, limit=limit)}


@router.post("/trades/pending/{pending_id}/cancel")
async def cancel_pending_semi_auto(
    pending_id: str,
    user_id: str = Depends(get_current_user),
):
    """R47 P6 — 用户在 10s 撤销窗口内撤销半自动交易。

    返:
      {"cancelled": true}                          → 成功
      {"cancelled": false, "reason": "..."}        → 失败(已超时/已执行/已撤销/race)
    """
    from agent import semi_auto_service
    cancelled, reason = semi_auto_service.cancel_pending(pending_id, user_id)
    if cancelled:
        return {"cancelled": True}
    return {"cancelled": False, "reason": reason or "unknown"}

