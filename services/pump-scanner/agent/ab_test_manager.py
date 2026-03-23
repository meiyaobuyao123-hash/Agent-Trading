"""
PRD-010 O10: A/B Test Manager

- create_test(config_a, config_b, duration_days) -> test_id
- get_group(test_id) -> "a" or "b" (random 50/50 per signal)
- get_config_for_group(test_id, group) -> config dict
- check_completion() -> auto-close expired tests, extend if <20 samples
"""

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import get_db

log = logging.getLogger(__name__)


class ABTestManager:
    """A/B test lifecycle: create -> assign signals -> auto-complete."""

    MIN_SAMPLES = 20
    MAX_EXTENSION_DAYS = 14  # 延长上限（从 started_at 起）

    async def create_test(
        self,
        config_a: dict,
        config_b: dict,
        duration_days: int = 7,
        proposal_id_a: Optional[str] = None,
        proposal_id_b: Optional[str] = None,
    ) -> str:
        """
        创建 A/B 测试。
        返回 test_id (UUID string)。
        """
        db = get_db()
        now = datetime.now(timezone.utc)
        ends_at = now + timedelta(days=duration_days)

        row = {
            "config_a": config_a,
            "config_b": config_b,
            "status": "running",
            "ends_at": ends_at.isoformat(),
        }
        if proposal_id_a:
            row["proposal_id_a"] = proposal_id_a
        if proposal_id_b:
            row["proposal_id_b"] = proposal_id_b

        res = db.table("agent_ab_tests").insert(row).execute()
        test_id = res.data[0]["id"]
        log.info("[ABTest] Created test %s, ends_at=%s", test_id, ends_at.isoformat())
        return test_id

    def get_group(self, test_id: str) -> str:
        """
        PRD-010 Q13: 按信号随机分流（非按策略）。
        每次调用独立随机，50/50 概率。
        """
        return "a" if random.random() < 0.5 else "b"

    def get_config_for_group(self, test_id: str, group: str) -> dict:
        """获取对应组的配置 dict。"""
        db = get_db()
        res = db.table("agent_ab_tests").select("config_a, config_b") \
            .eq("id", test_id).eq("status", "running").execute()

        if not res.data:
            return {}

        key = "config_a" if group == "a" else "config_b"
        return res.data[0].get(key) or {}

    def get_active_test(self) -> Optional[dict]:
        """获取当前正在运行的 A/B 测试（最多一个）。"""
        db = get_db()
        res = db.table("agent_ab_tests").select("*") \
            .eq("status", "running") \
            .order("started_at", desc=True) \
            .limit(1).execute()
        return res.data[0] if res.data else None

    async def check_completion(self):
        """
        检查到期测试 + 统计结果。
        - 到期且样本 >= 20: 完成并统计
        - 到期且样本 < 20: 延长 7 天（最多到 14 天）
        """
        db = get_db()
        now = datetime.now(timezone.utc)

        running = db.table("agent_ab_tests").select("*") \
            .eq("status", "running") \
            .lte("ends_at", now.isoformat()) \
            .execute()

        for test in (running.data or []):
            test_id = test["id"]

            # 统计 A 组和 B 组
            a_trades = db.table("agent_executions").select("*") \
                .eq("ab_test_id", test_id).eq("ab_group", "a").execute()
            b_trades = db.table("agent_executions").select("*") \
                .eq("ab_test_id", test_id).eq("ab_group", "b").execute()

            a_data = a_trades.data or []
            b_data = b_trades.data or []
            total = len(a_data) + len(b_data)

            # PRD-010 Q13: 样本不足延长
            if total < self.MIN_SAMPLES:
                started_at = _parse_dt(test.get("started_at", ""))
                max_end = started_at + timedelta(days=self.MAX_EXTENSION_DAYS) if started_at else None

                if max_end and now < max_end:
                    new_end = min(
                        now + timedelta(days=7),
                        max_end,
                    )
                    db.table("agent_ab_tests").update({
                        "ends_at": new_end.isoformat(),
                    }).eq("id", test_id).execute()
                    log.info("[ABTest] Extended %s to %s (samples=%d < %d)",
                             test_id, new_end.isoformat(), total, self.MIN_SAMPLES)
                    continue
                else:
                    log.warning("[ABTest] %s hit max extension with only %d samples, completing anyway",
                                test_id, total)

            # 统计并完成
            results_a = _calc_group_stats(a_data)
            results_b = _calc_group_stats(b_data)

            # 基于 Sharpe ratio 决定胜者
            sharpe_a = results_a.get("sharpe", 0)
            sharpe_b = results_b.get("sharpe", 0)
            if sharpe_a > sharpe_b:
                winner = "a"
            elif sharpe_b > sharpe_a:
                winner = "b"
            else:
                winner = None  # 平局

            db.table("agent_ab_tests").update({
                "status": "completed",
                "results_a": results_a,
                "results_b": results_b,
                "winner": winner,
                "completed_at": now.isoformat(),
            }).eq("id", test_id).execute()

            log.info("[ABTest] Completed %s: winner=%s, samples=%d (A=%d, B=%d)",
                     test_id, winner, total, len(a_data), len(b_data))


def _calc_group_stats(trades: List[dict]) -> dict:
    """计算一组交易的统计指标。"""
    if not trades:
        return {"trades": 0, "win_rate": 0, "pnl": 0, "sharpe": 0}

    pnl_list = []
    wins = 0
    total_pnl = 0.0

    for t in trades:
        pnl_pct = float(t.get("pnl_pct") or 0)
        pnl_list.append(pnl_pct)
        total_pnl += pnl_pct
        if pnl_pct > 0:
            wins += 1

    n = len(pnl_list)
    avg_pnl = total_pnl / n if n > 0 else 0

    # 简化 Sharpe ratio
    if n > 1:
        import math
        variance = sum((p - avg_pnl) ** 2 for p in pnl_list) / (n - 1)
        std = math.sqrt(variance) if variance > 0 else 0.001
        sharpe = avg_pnl / std if std > 0 else 0
    else:
        sharpe = 0

    return {
        "trades": n,
        "win_rate": round(wins / n, 4) if n > 0 else 0,
        "pnl": round(total_pnl, 4),
        "avg_pnl": round(avg_pnl, 4),
        "sharpe": round(sharpe, 4),
    }


def _parse_dt(s: str) -> Optional[datetime]:
    """Parse ISO datetime string."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None
