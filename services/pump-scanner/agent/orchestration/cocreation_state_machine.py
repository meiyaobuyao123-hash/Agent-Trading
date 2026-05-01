"""
共创流程状态机(S04 signal-strategy-builder + S05 trade-strategy-builder)

引用 docs/agent-pm/03-prd.md §2.4 共创 7 阶段
引用 docs/agent-pm/05-tool-catalog.md S04/S05
引用 docs/agent-pm/17-tech-plan.md Phase 2
引用 services/pump-scanner/migrations/local_pg/037_conversation_states.sql

7 阶段(stage 字段值):
  idle        初始(无 row,用户还没开口)
  clarifying  Agent 澄清提问 — Stage 1-2
  refining    Draft 生成 + 用户反馈微调 — Stage 3 + 5
  dry_run     历史预估(回溯 30d)— Stage 4
  confirming  最终确认 — Stage 6
  saved       已保存 — Stage 7
  aborted     用户主动放弃

设计原则:
  - 状态机本身不调 LLM,只负责 stage 转移 + 持久化
  - LLM 在 chat_loop 里调,根据当前 stage 选择 prompt template
  - 每次 chat 调用先 load_state → process → save_state
  - 30min 不活跃自动过期(SQL CHECK + cron 清理)

Python 3.9 兼容。
"""
from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


# ── stage 枚举与转移规则 ────────────────────────────────────

VALID_STAGES = {
    "clarifying", "refining", "dry_run", "confirming", "saved", "aborted",
}

# stage → next stage 候选(出于状态机正确性,LLM 决策让到哪个)
STAGE_TRANSITIONS: Dict[str, List[str]] = {
    "clarifying": ["clarifying", "refining", "aborted"],
    "refining": ["refining", "dry_run", "confirming", "aborted"],
    "dry_run": ["refining", "confirming", "aborted"],
    "confirming": ["confirming", "saved", "refining", "aborted"],
    "saved": [],   # terminal
    "aborted": [], # terminal
}


def is_valid_transition(from_stage: str, to_stage: str) -> bool:
    return to_stage in STAGE_TRANSITIONS.get(from_stage, [])


# ── 持久化(本地 PG conversation_states) ───────────────────

def _get_conn():
    """单例连接(复用 local_db._get_conn 风格)。"""
    from local_db import _get_conn as _lc
    return _lc()


def load_active_state(
    device_id: str,
    skill_name: str = "signal-strategy-builder",
) -> Optional[Dict[str, Any]]:
    """加载用户当前活跃的共创状态(非 saved/aborted/expired)。

    每个 device_id × skill_name 同时只允许一个活跃 state。
    若有多条(异常情况)取 updated_at 最新。
    """
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT conversation_id, device_id, skill_name, stage,
                       messages, draft_data, user_profile, dry_run_result,
                       created_at, updated_at, expires_at, saved_strategy_id
                FROM conversation_states
                WHERE device_id = %s
                  AND skill_name = %s
                  AND stage NOT IN ('saved','aborted')
                  AND expires_at > now()
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (device_id, skill_name),
            )
            row = cur.fetchone()
        if not row:
            return None
        return _row_to_dict(row)
    except Exception as e:
        log.warning("[cocreation] load_active_state failed: %s", e)
        return None


def create_state(
    device_id: str,
    skill_name: str = "signal-strategy-builder",
    initial_message: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """创建新的共创状态(stage=clarifying)。"""
    conv_id = str(uuid.uuid4())
    messages: List[Dict[str, Any]] = []
    if initial_message:
        messages.append({
            "role": "user",
            "content": initial_message,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversation_states
                  (conversation_id, device_id, skill_name, stage, messages)
                VALUES (%s, %s, %s, 'clarifying', %s::jsonb)
                RETURNING conversation_id, device_id, skill_name, stage,
                          messages, draft_data, user_profile, dry_run_result,
                          created_at, updated_at, expires_at, saved_strategy_id
                """,
                (conv_id, device_id, skill_name, json.dumps(messages)),
            )
            row = cur.fetchone()
        return _row_to_dict(row) if row else None
    except Exception as e:
        log.warning("[cocreation] create_state failed: %s", e)
        return None


def append_message(
    conversation_id: str,
    role: str,
    content: str,
    keep_last_n: int = 20,
) -> bool:
    """追加一条消息;只保留最近 N 条(默认 20)。"""
    if role not in ("user", "assistant", "system"):
        return False
    msg = {
        "role": role,
        "content": content,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT messages FROM conversation_states WHERE conversation_id = %s",
                (conversation_id,),
            )
            r = cur.fetchone()
            if not r:
                return False
            existing = r[0] if isinstance(r[0], list) else (r[0] or [])
            new = (existing + [msg])[-keep_last_n:]
            cur.execute(
                """
                UPDATE conversation_states
                SET messages = %s::jsonb,
                    updated_at = now(),
                    expires_at = now() + INTERVAL '30 minutes'
                WHERE conversation_id = %s
                """,
                (json.dumps(new), conversation_id),
            )
        return True
    except Exception as e:
        log.warning("[cocreation] append_message failed: %s", e)
        return False


def transition(
    conversation_id: str,
    to_stage: str,
    *,
    draft_data: Optional[Dict[str, Any]] = None,
    dry_run_result: Optional[Dict[str, Any]] = None,
    saved_strategy_id: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """状态转移。返回 (ok, error)。

    - 校验 to_stage 是 valid 转移
    - 写入对应字段(draft_data / dry_run_result / saved_strategy_id)
    - saved/aborted 是 terminal,转移后不能再改
    """
    if to_stage not in VALID_STAGES:
        return False, f"invalid stage: {to_stage}"
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT stage FROM conversation_states WHERE conversation_id = %s",
                (conversation_id,),
            )
            r = cur.fetchone()
            if not r:
                return False, "conversation not found"
            current = r[0]
            if not is_valid_transition(current, to_stage):
                return False, f"invalid transition: {current} -> {to_stage}"

            sets = ["stage = %s", "updated_at = now()",
                    "expires_at = now() + INTERVAL '30 minutes'"]
            params: List[Any] = [to_stage]
            if draft_data is not None:
                sets.append("draft_data = %s::jsonb")
                params.append(json.dumps(draft_data))
            if dry_run_result is not None:
                sets.append("dry_run_result = %s::jsonb")
                params.append(json.dumps(dry_run_result))
            if saved_strategy_id is not None:
                sets.append("saved_strategy_id = %s")
                params.append(saved_strategy_id)
            params.append(conversation_id)
            cur.execute(
                f"UPDATE conversation_states SET {', '.join(sets)} "
                f"WHERE conversation_id = %s",
                params,
            )
        return True, None
    except Exception as e:
        log.warning("[cocreation] transition failed: %s", e)
        return False, str(e)[:200]


def cleanup_expired(batch: int = 100) -> int:
    """清理过期未完成的会话(stage in clarifying/refining/dry_run/confirming + expires_at < now)。

    设为 aborted 而不是 DELETE — 保留行用于审计。
    返回处理条数。
    """
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE conversation_states
                SET stage = 'aborted', updated_at = now()
                WHERE stage NOT IN ('saved','aborted')
                  AND expires_at < now()
                """
            )
            return cur.rowcount or 0
    except Exception as e:
        log.warning("[cocreation] cleanup_expired failed: %s", e)
        return 0


# ── 路由辅助:供 chat_loop 决定下一 stage ───────────────────

def suggest_next_stage(
    current_stage: str,
    user_text: str,
    has_draft: bool,
    user_satisfied: Optional[bool] = None,
) -> str:
    """启发式建议下一 stage(LLM 不调时的 fallback)。

    - clarifying:用户消息够长/具体 → refining
    - refining:已 draft + 用户没否定 → dry_run
    - dry_run:dry run 完成 → confirming
    - confirming:用户明确确认 → saved
    - 任何 stage:用户说"算了/取消" → aborted
    """
    text = (user_text or "").strip().lower()

    # abort 触发词
    abort_words = ("取消", "算了", "不要了", "放弃", "abort", "cancel")
    if any(w in text for w in abort_words):
        return "aborted"

    # confirm / 进入 saved
    confirm_words = ("确认", "确定", "保存", "ok", "yes", "好的", "可以")

    if current_stage == "clarifying":
        # 用户消息 ≥ 10 字符 + 含意图词 → 进 refining
        intent_words = ("聪明钱", "买", "卖", "策略", "btc", "eth", "sol", "跟单",
                        "follow", "trade", "swing", "long", "short", "scalp")
        if len(text) >= 10 or any(w in text for w in intent_words):
            return "refining"
        return "clarifying"

    if current_stage == "refining":
        if user_satisfied is True:
            return "dry_run"
        if has_draft and any(w in text for w in confirm_words):
            return "dry_run"
        return "refining"

    if current_stage == "dry_run":
        return "confirming"  # dry run 完成默认进 confirming

    if current_stage == "confirming":
        if any(w in text for w in confirm_words):
            return "saved"
        # 用户提反馈 → 回 refining
        return "refining"

    return current_stage  # terminal 不动


# ── helpers ─────────────────────────────────────────────────

def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "conversation_id": str(row[0]),
        "device_id": str(row[1]),
        "skill_name": row[2],
        "stage": row[3],
        "messages": row[4] if isinstance(row[4], list) else (row[4] or []),
        "draft_data": row[5],
        "user_profile": row[6],
        "dry_run_result": row[7],
        "created_at": row[8].isoformat() if row[8] else None,
        "updated_at": row[9].isoformat() if row[9] else None,
        "expires_at": row[10].isoformat() if row[10] else None,
        "saved_strategy_id": str(row[11]) if row[11] else None,
    }
