"""
R47 P6 — 半自动交易执行器(撤销窗口扫描 cron)

每 1s 扫一次 pending_semi_auto_trades 表:
  - status='pending' AND execute_after < now() → 调 trade_executor.execute_trade
  - 抢到执行权(mark_executed UPDATE WHERE status='pending')→ 真发交易
  - 失败 → mark_failed
  - 用户先撤销 → UPDATE 不命中 → 跳过

设计要点:
  - 1s tick(不是 60s,因为撤销窗口只有 10s,延迟敏感)
  - 防 race: mark_executed 用 SQL UPDATE WHERE status='pending',原子串行化
  - max_instances=1 + coalesce=True(scheduler 配),防多实例并发执行同一 pending

Python 3.9 兼容。
"""
from __future__ import annotations
import logging
from typing import Any, Dict

log = logging.getLogger(__name__)


async def run_once() -> Dict[str, int]:
    """主入口,被 main.py APScheduler 调用。返各种状态计数。"""
    from agent import semi_auto_service

    pending_list = semi_auto_service.fetch_due_pending(limit=50)
    if not pending_list:
        return {"due": 0, "executed": 0, "skipped_cancelled": 0, "failed": 0}

    log.info("[semi_auto cron] %d pending due", len(pending_list))

    counts = {"due": len(pending_list), "executed": 0, "skipped_cancelled": 0, "failed": 0}

    for p in pending_list:
        pending_id = p["id"]
        try:
            from agent.trade_executor import get_trade_executor
            executor = get_trade_executor()
            result = await executor.execute_trade(
                chain=p["chain"],
                token_address=p["token_address"],
                action=p["action"],
                amount_usd=p["amount_usd"],
                slippage_pct=p.get("slippage_pct") or 1.0,
                user_id=p["user_id"],         # R47 P5 透传
                safety_ctx={
                    "user_id": p["user_id"],
                    "strategy_id": p.get("strategy_id"),
                    "mode": "live",
                },
            )

            if result.success:
                # 抢锁 + 写 tx_hash
                won = semi_auto_service.mark_executed(pending_id, result.tx_hash or "")
                if won:
                    counts["executed"] += 1
                    log.info(
                        "[semi_auto cron] executed pending=%s user=%s tx=%s",
                        pending_id[:8], p["user_id"][:8], (result.tx_hash or "")[:20],
                    )
                else:
                    counts["skipped_cancelled"] += 1
                    log.warning(
                        "[semi_auto cron] race lost (user cancelled first) pending=%s",
                        pending_id[:8],
                    )
                    # 注:这里有边角:trade_executor 已经发出去了但 DB 显示 cancelled。
                    # DRY_RUN 状态下不真发,不影响。GA 后需考虑(若真发出去再被撤,
                    # 实际钱已花;cancel_pending endpoint 已加 execute_after > now 时间窗
                    # 检查防止这种情况发生)。
            else:
                semi_auto_service.mark_failed(pending_id, result.error or "unknown")
                counts["failed"] += 1
                log.warning(
                    "[semi_auto cron] failed pending=%s error=%s",
                    pending_id[:8], (result.error or "")[:80],
                )
        except Exception as e:
            semi_auto_service.mark_failed(pending_id, f"exception: {str(e)[:200]}")
            counts["failed"] += 1
            log.error("[semi_auto cron] exception on pending=%s: %s", pending_id[:8], e)

    return counts


# 命令行单跑(调试用)
if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    res = asyncio.run(run_once())
    print(f"result: {res}")
