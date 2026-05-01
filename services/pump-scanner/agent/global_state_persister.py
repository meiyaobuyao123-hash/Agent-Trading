"""
Global State Persister — SafetyEngine CB 状态 ↔ 本地 PG agent_global_state 表
引用 docs/agent-pm/17-tech-plan.md Phase 0 + W3 D3
引用 migrations/local_pg/042_agent_global_state.sql

职责:
  1. 启动时:从 agent_global_state 表读 → 恢复 SafetyEngine._active_breakers(防重启丢状态)
  2. 运行时:每次 trip/release 触发 → SafetyEngine 调 _state_persister(payload) → 写 PG
  3. 写 history 表(变更审计,90d 保留)

设计:
  - 同步函数(psycopg2 阻塞调用,但单次写入 < 10ms,可接受)
  - 失败不抛(safety 高可用,DB 故障不阻断 CB 状态变化;由 SafetyEngine._notify_state_change 内部捕获)
  - 幂等:状态相同时跳过写入(对比 active_breakers 哈希)
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import json
import hashlib
import logging

log = logging.getLogger(__name__)

_LAST_PAYLOAD_HASH: str | None = None  # 内存幂等


def _hash_payload(payload: dict) -> str:
    """对 payload 做 hash,用于幂等检测。"""
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def persist_to_pg(payload: dict) -> bool:
    """SafetyEngine state_persister 回调入口。

    payload = {
      "state": "blocked" | "degraded" | "normal",
      "active_breakers": [{cb_id, name, tripped_at, auto_release_at, reason, severity}, ...]
    }

    返回是否成功写入(失败也吞掉异常返 False)。
    """
    global _LAST_PAYLOAD_HASH

    # 幂等检测
    h = _hash_payload(payload)
    if h == _LAST_PAYLOAD_HASH:
        return True  # 状态相同,跳过

    try:
        from local_db import _get_conn
    except ImportError as e:
        log.debug("local_db 不可用,跳过持久化: %s", e)
        return False

    try:
        conn = _get_conn()
    except Exception as e:
        log.warning("[GlobalState] PG 连接失败: %s", e)
        return False

    state = payload.get("state", "normal")
    breakers = payload.get("active_breakers", [])
    breakers_json = json.dumps(breakers, default=str)

    try:
        with conn.cursor() as cur:
            # 1. 更新单例
            cur.execute(
                """
                UPDATE agent_global_state
                   SET state = %s,
                       active_breakers = %s::jsonb,
                       updated_at = now(),
                       updated_by = 'safety_engine'
                 WHERE id = 1
                """,
                (state, breakers_json),
            )

            # 2. 写 history(检测 prev_state)
            cur.execute("SELECT state FROM agent_global_state WHERE id = 1")
            row = cur.fetchone()
            prev_state = row[0] if row else None

            cur.execute(
                """
                INSERT INTO agent_global_state_history
                  (prev_state, new_state, action, payload, updated_by)
                VALUES (%s, %s, %s, %s::jsonb, %s)
                """,
                (prev_state, state, "auto", breakers_json, "safety_engine"),
            )
        _LAST_PAYLOAD_HASH = h
        log.info("[GlobalState] persisted state=%s active_cbs=%d",
                 state, len(breakers))
        return True
    except Exception as e:
        msg = str(e).lower()
        if "does not exist" in msg or "undefined" in msg:
            log.debug("[GlobalState] agent_global_state 表不存在,跳过(migration 未跑)")
        else:
            log.warning("[GlobalState] 持久化失败: %s", e)
        return False


def load_from_pg() -> dict | None:
    """启动时从 PG 拉当前状态。返回 None 表示 DB 不可用或表不存在。
    payload 格式同 persist_to_pg。
    """
    try:
        from local_db import _get_conn
    except ImportError:
        return None

    try:
        conn = _get_conn()
    except Exception as e:
        log.warning("[GlobalState] PG 连接失败: %s", e)
        return None

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT state, active_breakers FROM agent_global_state WHERE id = 1"
            )
            row = cur.fetchone()
            if not row:
                return None
            state, breakers_json = row
            if isinstance(breakers_json, str):
                breakers = json.loads(breakers_json)
            else:
                breakers = breakers_json or []
            return {"state": state, "active_breakers": breakers}
    except Exception as e:
        msg = str(e).lower()
        if "does not exist" in msg or "undefined" in msg:
            log.debug("[GlobalState] 表不存在,跳过启动恢复")
            return None
        log.warning("[GlobalState] load 失败: %s", e)
        return None


def restore_engine_state(engine) -> int:
    """启动时调用:从 PG 恢复 SafetyEngine._active_breakers
    返回恢复的 CB 数量(0 = 无状态需恢复 / DB 不可用)。
    """
    payload = load_from_pg()
    if payload is None:
        return 0

    breakers = payload.get("active_breakers", [])
    if not breakers:
        return 0

    restored = 0
    for b in breakers:
        cb_id = b.get("cb_id")
        if not cb_id:
            continue
        # auto_release_at 可能已过期,trip 后下次 check_trade 自动释放
        try:
            engine.trip_breaker(cb_id, reason=f"[restored] {b.get('reason', '')}")
            # 恢复 tripped_at(保留原始时间)
            if cb_id in engine._active_breakers:
                state = engine._active_breakers[cb_id]
                tripped_at_str = b.get("tripped_at")
                if tripped_at_str:
                    try:
                        state.tripped_at = datetime.fromisoformat(
                            tripped_at_str.replace("Z", "+00:00")
                        )
                    except Exception:
                        pass
                auto_at_str = b.get("auto_release_at")
                if auto_at_str:
                    try:
                        state.auto_release_at = datetime.fromisoformat(
                            auto_at_str.replace("Z", "+00:00")
                        )
                    except Exception:
                        pass
                restored += 1
        except Exception as e:
            log.warning("[GlobalState] 恢复 %s 失败: %s", cb_id, e)

    log.info("[GlobalState] 启动恢复了 %d 个 active CB", restored)
    return restored


def attach_to_engine(engine) -> None:
    """便捷函数:把 persist_to_pg 注入到 SafetyEngine,并尝试启动恢复。
    失败不抛(safety 不能被基础设施故障阻断)。
    """
    try:
        engine.set_state_persister(persist_to_pg)
        restore_engine_state(engine)
    except Exception as e:
        log.warning("[GlobalState] attach 失败: %s", e)


def reset_persister_cache() -> None:
    """测试用:重置幂等缓存。"""
    global _LAST_PAYLOAD_HASH
    _LAST_PAYLOAD_HASH = None
