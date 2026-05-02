"""
HITL 5/15/60min 超时升级 — R37 P0-3
引用 docs/agent-pm/04-agent-spec.md §3.2 + 11-launch-criteria-hitl.md HITL escalation

行为(每 60s 跑一次,scan pending_approvals where status='pending'):
  - 5min(creation+5min): 推送提醒(re-push,push_resent_at 幂等)
  - 15min(creation+15min): 降级为 notify_only(decision_reason 标记 'hitl_15min_degraded')
                          注:status 仍 pending,允许用户继续 approve 直到 60min
                          但 trade_executor 看到 'hitl_15min_degraded' 标记后不再执行真金,改 paper
  - 60min(creation+60min,= expires_at): 自动 expire(status='expired',
                                          decision_reason='hitl_60min_timeout',audit_log)

可手动触发(routes_admin 用于演练):
  POST /api/admin/hitl/scan-timeouts → 跑一次扫描,返本次升级条数

idempotency:
  - 5min 推送:push_resent_at 是 NULL 才推
  - 15min 降级:decision_reason 不含 'hitl_15min_degraded' 才标(SET WHERE 防重复)
  - 60min:status='pending' AND now() >= expires_at,转 expired
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

log = logging.getLogger(__name__)


# ── 时间常数(允许测试 monkeypatch) ────────────────────────────


REPUSH_AFTER_MIN = 5
DEGRADE_AFTER_MIN = 15


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def scan_and_escalate() -> Dict[str, int]:
    """扫一次 pending_approvals 表,执行 5/15/60 升级。
    返回 {repushed, degraded, expired, errors}。

    无副作用前提下整体返 {repushed:0, degraded:0, expired:0} —
    生产环境 cron 每分钟跑一次。
    """
    counts = {"repushed": 0, "degraded": 0, "expired": 0, "errors": 0}
    try:
        from local_db import _get_conn
    except ImportError:
        log.debug("[hitl-timeout] local_db unavailable, skip")
        return counts

    try:
        conn = _get_conn()
    except Exception as e:
        log.warning("[hitl-timeout] PG connect fail: %s", e)
        counts["errors"] += 1
        return counts

    now = _utcnow()
    repush_threshold = now - timedelta(minutes=REPUSH_AFTER_MIN)
    degrade_threshold = now - timedelta(minutes=DEGRADE_AFTER_MIN)

    try:
        # ── 1. 60min 过期(status pending → expired)─────
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pending_approvals
                   SET status = 'expired',
                       decision_reason = COALESCE(decision_reason, '') ||
                                          CASE WHEN decision_reason IS NULL OR decision_reason = ''
                                               THEN 'hitl_60min_timeout'
                                               ELSE ';hitl_60min_timeout' END,
                       decided_at = now()
                 WHERE status = 'pending'
                   AND expires_at <= %s
                RETURNING approval_id, device_id, strategy_id, amount_usd
                """,
                (now,),
            )
            expired_rows = cur.fetchall() or []
            counts["expired"] = len(expired_rows)
            for row in expired_rows:
                # 写 audit
                try:
                    cur.execute(
                        """
                        INSERT INTO security_audit_log
                          (device_id, event_type, severity, payload, approval_id)
                        VALUES (%s, 'hitl_decision', 'warn', %s::jsonb, %s)
                        """,
                        (
                            row[1],
                            json.dumps({
                                "action": "auto_expire",
                                "approval_id": str(row[0]),
                                "strategy_id": str(row[2]),
                                "amount_usd": float(row[3]) if row[3] else None,
                                "reason": "60min_timeout",
                            }),
                            row[0],
                        ),
                    )
                except Exception as e:
                    log.warning("[hitl-timeout] audit insert fail: %s", e)
                    counts["errors"] += 1

        # ── 2. 15min 降级(标 decision_reason)──────────
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pending_approvals
                   SET decision_reason = COALESCE(decision_reason, '') ||
                                          CASE WHEN decision_reason IS NULL OR decision_reason = ''
                                               THEN 'hitl_15min_degraded:notify_only'
                                               ELSE ';hitl_15min_degraded:notify_only' END
                 WHERE status = 'pending'
                   AND created_at <= %s
                   AND (decision_reason IS NULL OR decision_reason NOT LIKE %s)
                RETURNING approval_id, device_id, strategy_id
                """,
                (degrade_threshold, "%hitl_15min_degraded%"),
            )
            degraded_rows = cur.fetchall() or []
            counts["degraded"] = len(degraded_rows)
            for row in degraded_rows:
                try:
                    cur.execute(
                        """
                        INSERT INTO security_audit_log
                          (device_id, event_type, severity, payload, approval_id)
                        VALUES (%s, 'hitl_decision', 'info', %s::jsonb, %s)
                        """,
                        (
                            row[1],
                            json.dumps({
                                "action": "degrade_to_notify_only",
                                "approval_id": str(row[0]),
                                "strategy_id": str(row[2]),
                                "reason": "15min_no_response",
                            }),
                            row[0],
                        ),
                    )
                except Exception as e:
                    log.warning("[hitl-timeout] audit insert fail: %s", e)
                    counts["errors"] += 1

        # ── 3. 5min 重推(push_resent_at 幂等)───────────
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pending_approvals
                   SET push_resent_at = now()
                 WHERE status = 'pending'
                   AND push_resent_at IS NULL
                   AND created_at <= %s
                RETURNING approval_id, device_id, strategy_id, amount_usd
                """,
                (repush_threshold,),
            )
            repush_rows = cur.fetchall() or []
            counts["repushed"] = len(repush_rows)
            # 真推送(失败不阻塞 — push_resent_at 已写,下次 cron 不会重复)
            for row in repush_rows:
                await _try_send_repush(row[1], row[0], row[2], row[3])

        log.info(
            "[hitl-timeout] scan: repushed=%d degraded=%d expired=%d errors=%d",
            counts["repushed"], counts["degraded"], counts["expired"], counts["errors"],
        )
    except Exception as e:
        log.exception("[hitl-timeout] scan failed")
        counts["errors"] += 1

    return counts


async def _try_send_repush(device_id, approval_id, strategy_id, amount_usd) -> None:
    """5min 重推 — 失败不阻塞(push_resent_at 已 set)。"""
    try:
        from agent.push_service import send_push, build_deep_link
        deep_link = build_deep_link("hitl_approval", approval_id=str(approval_id))
        await send_push(
            device_id=str(device_id),
            title="审批等待中",
            body=f"策略触发提醒(${amount_usd or '?'}),5 分钟后将降级为通知模式",
            data={
                "category": "hitl_approval",
                "deep_link": deep_link,
                "approval_id": str(approval_id),
                "strategy_id": str(strategy_id),
            },
        )
    except Exception as e:
        log.debug("[hitl-timeout] re-push skipped: %s", e)


def is_approval_degraded(decision_reason: str | None) -> bool:
    """判断 approval 是否已降级到 notify_only(15min 升级)。
    用于 trade_executor / approve endpoint 决定是否走真金 vs paper。
    """
    if not decision_reason:
        return False
    return "hitl_15min_degraded" in decision_reason
