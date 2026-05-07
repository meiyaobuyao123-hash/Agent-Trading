"""
R47 P6 — 半自动交易服务

职责:
  1. action_dispatcher 单笔 ≥ $500 时 → create_pending() 入表
  2. cron(每 1s)扫 status='pending' AND execute_after < now() → execute_pending()
  3. 用户调 cancel endpoint → cancel_pending()(防 race:UPDATE WHERE status='pending')

API:
  create_pending(user_id, strategy_id, chain, token_address, token_symbol, action, amount_usd, slippage_pct, trigger_context, cancel_window_sec) → pending_id
  list_user_pending(user_id, limit=20) → list of pending trades
  cancel_pending(pending_id, user_id) → (cancelled: bool, reason: Optional[str])
  fetch_due_pending() → list of pending trades whose execute_after < now() (cron 用)
  mark_executed(pending_id, tx_hash) / mark_failed(pending_id, error)

失败永不抛(返默认值或 False),让 caller 降级处理。

Python 3.9 兼容。
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


def _get_conn():
    from local_db import _get_conn as _gc
    return _gc()


def create_pending(
    user_id: str,
    strategy_id: Optional[str],
    chain: str,
    token_address: str,
    token_symbol: Optional[str],
    action: str,
    amount_usd: float,
    slippage_pct: Optional[float] = None,
    trigger_context: Optional[Dict[str, Any]] = None,
    cancel_window_sec: int = 10,
) -> Optional[str]:
    """写入 pending_semi_auto_trades,返 pending_id。失败返 None。"""
    if not user_id or amount_usd <= 0:
        return None
    if action not in ("buy", "sell"):
        return None

    execute_after = datetime.now(timezone.utc) + timedelta(seconds=cancel_window_sec)

    try:
        import json as _json
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pending_semi_auto_trades
                  (user_id, strategy_id, chain, token_address, token_symbol,
                   action, amount_usd, slippage_pct, trigger_context, execute_after)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                RETURNING id
                """,
                (
                    user_id, strategy_id, chain, token_address, token_symbol,
                    action, Decimal(str(amount_usd)),
                    Decimal(str(slippage_pct)) if slippage_pct else None,
                    _json.dumps(trigger_context or {}, default=str),
                    execute_after,
                ),
            )
            row = cur.fetchone()
        conn.commit()
        if not row:
            return None
        pending_id = str(row[0])
        log.info(
            "[semi_auto] created pending=%s user=%s %s %s $%.2f exec_after=%s",
            pending_id[:8], user_id[:8], action, token_address[:10],
            amount_usd, execute_after.isoformat(),
        )
        return pending_id
    except Exception as e:
        log.error("[semi_auto] create_pending failed: %s", e)
        return None


def cancel_pending(pending_id: str, user_id: str) -> Tuple[bool, Optional[str]]:
    """用户撤销。

    返 (cancelled, reason):
      - (True, None) — 成功
      - (False, "not_found") — id 不存在或不属于该 user
      - (False, "already_executed") — 已被 cron 执行
      - (False, "already_cancelled") — 已撤销
      - (False, "window_expired") — 已超时来不及撤销

    防 race:UPDATE WHERE status='pending' RETURNING — 同一行串行化。
    """
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            # 先查存在 + 当前状态
            cur.execute(
                "SELECT status, execute_after FROM pending_semi_auto_trades "
                "WHERE id = %s AND user_id = %s",
                (pending_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return False, "not_found"
            cur_status = row[0]
            execute_after = row[1]

            if cur_status == "executed":
                return False, "already_executed"
            if cur_status == "cancelled":
                return False, "already_cancelled"
            if cur_status != "pending":
                return False, cur_status  # expired / failed

            # 时间窗检查:即使 cron 还没扫,过了时间就不让撤(避免和 cron race)
            now = datetime.now(timezone.utc)
            if execute_after <= now:
                return False, "window_expired"

            # 原子更新
            cur.execute(
                """
                UPDATE pending_semi_auto_trades
                   SET status = 'cancelled',
                       cancelled_at = now(),
                       cancel_reason = 'user_cancel'
                 WHERE id = %s AND user_id = %s AND status = 'pending'
                RETURNING id
                """,
                (pending_id, user_id),
            )
            updated = cur.fetchone()
        conn.commit()
        if not updated:
            # cron 已抢到 → 此 UPDATE WHERE status='pending' 不命中
            return False, "race_lost_to_cron"
        log.info("[semi_auto] user cancelled pending=%s user=%s", pending_id[:8], user_id[:8])
        return True, None
    except Exception as e:
        log.error("[semi_auto] cancel_pending failed: %s", e)
        return False, f"db_error: {str(e)[:80]}"


def fetch_due_pending(limit: int = 50) -> List[Dict[str, Any]]:
    """cron 用:拉所有 status='pending' AND execute_after < now() 的 trade。"""
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, strategy_id, chain, token_address, token_symbol,
                       action, amount_usd, slippage_pct, trigger_context
                  FROM pending_semi_auto_trades
                 WHERE status = 'pending' AND execute_after < now()
                 ORDER BY execute_after
                 LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall() or []
        return [
            {
                "id": str(r[0]),
                "user_id": str(r[1]),
                "strategy_id": str(r[2]) if r[2] else None,
                "chain": r[3],
                "token_address": r[4],
                "token_symbol": r[5],
                "action": r[6],
                "amount_usd": float(r[7]),
                "slippage_pct": float(r[8]) if r[8] else None,
                "trigger_context": r[9] or {},
            }
            for r in rows
        ]
    except Exception as e:
        log.warning("[semi_auto] fetch_due_pending failed: %s", e)
        return []


def mark_executed(pending_id: str, tx_hash: Optional[str]) -> bool:
    """cron 执行成功后 mark。

    防 race:UPDATE WHERE status='pending' — 若用户刚撤销,UPDATE 不命中,cron 跳过。
    返 True = 抢到执行权,False = 用户先撤销了。
    """
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pending_semi_auto_trades
                   SET status = 'executed',
                       executed_at = now(),
                       tx_hash = %s
                 WHERE id = %s AND status = 'pending'
                RETURNING id
                """,
                (tx_hash, pending_id),
            )
            row = cur.fetchone()
        conn.commit()
        return bool(row)
    except Exception as e:
        log.error("[semi_auto] mark_executed failed: %s", e)
        return False


def mark_failed(pending_id: str, error: str) -> bool:
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pending_semi_auto_trades
                   SET status = 'failed',
                       error_message = %s
                 WHERE id = %s AND status = 'pending'
                """,
                (error[:500], pending_id),
            )
        conn.commit()
        return True
    except Exception as e:
        log.error("[semi_auto] mark_failed failed: %s", e)
        return False


def list_user_pending(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, strategy_id, chain, token_address, token_symbol,
                       action, amount_usd, status, created_at, execute_after,
                       executed_at, cancelled_at, tx_hash
                  FROM pending_semi_auto_trades
                 WHERE user_id = %s
                 ORDER BY created_at DESC
                 LIMIT %s
                """,
                (user_id, limit),
            )
            rows = cur.fetchall() or []
        return [
            {
                "id": str(r[0]),
                "strategy_id": str(r[1]) if r[1] else None,
                "chain": r[2],
                "token_address": r[3],
                "token_symbol": r[4],
                "action": r[5],
                "amount_usd": float(r[6]),
                "status": r[7],
                "created_at": r[8].isoformat() if r[8] else None,
                "execute_after": r[9].isoformat() if r[9] else None,
                "executed_at": r[10].isoformat() if r[10] else None,
                "cancelled_at": r[11].isoformat() if r[11] else None,
                "tx_hash": r[12],
            }
            for r in rows
        ]
    except Exception as e:
        log.warning("[semi_auto] list_user_pending failed: %s", e)
        return []
