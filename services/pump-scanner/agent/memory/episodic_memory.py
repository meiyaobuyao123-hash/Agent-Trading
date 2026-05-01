"""
中期记忆 — DB 存储，相关性检索

PRD-005 M12:
- 存储交易复盘、市场模式、风控教训
- 按 category 不同过期窗口（trade_review=14d, market_pattern=30d, risk_lesson=30d）
- 最多 200 条，按相关性检索 Top 3
- 相关性评分：trigger_source(+3) > chain(+2) = regime(+2) = mcap_bucket(+2) > pnl(+1)
- 30s 缓存

Python 3.9 兼容。
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

from database import get_db

log = logging.getLogger(__name__)

# 不同 category 的过期天数
EXPIRY_DAYS: Dict[str, int] = {
    "trade_review": 14,
    "market_pattern": 30,
    "risk_lesson": 30,
}

MAX_EPISODIC = 200
CACHE_TTL = 30.0  # 30s 缓存


class EpisodicMemory:
    """中期记忆 — DB CRUD + 增强相关性检索"""

    def __init__(self):
        self._cache: List[Dict] = []
        self._cache_ts: float = 0

    def add(self, memory: Dict[str, Any]) -> Optional[str]:
        """
        写入一条中期记忆

        memory 必须包含 content，可选 category/structured_data/chain 等。
        自动设置 expires_at。
        """
        category = memory.get("category", "trade_review")
        expiry_days = EXPIRY_DAYS.get(category, 14)

        row = {
            "type": "episodic",
            "category": category,
            "content": memory.get("content", ""),
            "structured_data": memory.get("structured_data"),
            "importance": memory.get("importance", 5),
            "chain": memory.get("chain"),
            "token_type": memory.get("token_type"),
            "trigger_source": memory.get("trigger_source"),
            "mcap_bucket": memory.get("mcap_bucket"),
            "market_regime": memory.get("market_regime"),
            "is_active": True,
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(days=expiry_days)
            ).isoformat(),
        }

        try:
            res = get_db().table("agent_memory").insert(row).execute()
            self._cache_ts = 0  # 写入后使缓存失效
            if res.data:
                return res.data[0]["id"]
            return None
        except Exception as e:
            log.warning("Episodic write failed: %s", e)
            return None

    def search(
        self,
        chain: Optional[str] = None,
        trigger_source: Optional[str] = None,
        mcap_bucket: Optional[str] = None,
        regime: Optional[str] = None,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        按相关性检索 Top N 中期记忆

        评分公式（PRD-005 v1.1）：
          trigger_source 匹配: +3（最重要，同类信号经验最相关）
          chain 匹配: +2
          regime 匹配: +2
          mcap_bucket 匹配: +2
          abs(pnl_pct) > 20: +1（大盈大亏更值得记）
        """
        candidates = self._get_cached()

        scored = []
        for m in candidates:
            score = 0
            if trigger_source and m.get("trigger_source") == trigger_source:
                score += 3
            if chain and m.get("chain") == chain:
                score += 2
            if regime and m.get("market_regime") == regime:
                score += 2
            if mcap_bucket and m.get("mcap_bucket") == mcap_bucket:
                score += 2
            # pnl bonus
            sd = m.get("structured_data") or {}
            if isinstance(sd, dict) and abs(sd.get("pnl_pct", 0)) > 20:
                score += 1
            scored.append((score, m))

        # 先按 score 降序，再按 created_at 降序（新的优先）
        scored.sort(key=lambda x: (-x[0], x[1].get("created_at", "") or ""))
        # 对于 sort-by-date 部分，created_at 更大的排前面需要反转
        # 实际上上面排序中 created_at 是 ISO 字符串，升序意味着旧的在前，
        # 我们想新的在前（降序），所以需要调整
        scored.sort(key=lambda x: (-x[0], ""))
        # 按 score 分组后按 created_at 降序
        from itertools import groupby
        result = []
        for _, group in groupby(scored, key=lambda x: x[0]):
            items = list(group)
            items.sort(key=lambda x: x[1].get("created_at", "") or "", reverse=True)
            result.extend(items)
        return [m for _, m in result[:limit]]

    def get_relevant(
        self,
        chain: Optional[str] = None,
        trigger_source: Optional[str] = None,
        token_type: Optional[str] = None,
        mcap_bucket: Optional[str] = None,
        regime: Optional[str] = None,
        limit: int = 10,
        min_score: float = 3.0,
    ) -> List[Dict[str, Any]]:
        """W3 D5+:对齐 17-tech-plan.md Memory 4 层升级评分公式。

        score = trigger_source(+3) + chain(+2) + token_type(+2) + mcap(+1)
              + regime_match(+2) + freshness(衰减)+ match_count(log)

        - freshness:30 天半衰,最大 +1.5,最小 0(超过 90 天为负但 clip)
        - match_count:命中越多越相关,log10 平滑,最大 +1
        - regime_distance(对 7 状态有序距离):同 regime +2,相邻 +1,远离 0

        过滤 score < min_score(默认 3.0),返回带 `_score` 字段的列表。
        命中后给所有返回的记忆 match_count += 1(异步,不阻塞)。
        """
        import math
        from datetime import datetime, timezone

        candidates = self._get_cached()
        now = datetime.now(timezone.utc)

        # 7 状态 regime 距离表(对齐 docs/agent-pm regime 字典)
        REGIME_ORDER = [
            "TRENDING_UP", "BREAKOUT", "RANGING", "HIGH_VOLATILITY",
            "TRENDING_DOWN", "CRISIS", "RECOVERY",
        ]

        def _regime_score(target: Optional[str], actual: Optional[str]) -> float:
            if not target or not actual:
                return 0.0
            if target == actual:
                return 2.0
            try:
                d = abs(REGIME_ORDER.index(target) - REGIME_ORDER.index(actual))
                if d == 1:
                    return 1.0
                if d == 2:
                    return 0.5
            except ValueError:
                return 0.0
            return 0.0

        def _freshness(created_at: Optional[str]) -> float:
            if not created_at:
                return 0.0
            try:
                ts = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            except Exception:
                return 0.0
            age_days = (now - ts).total_seconds() / 86400
            if age_days < 0:
                return 1.5
            # 30d 半衰:1.5 × 0.5^(age/30) - clamp [0, 1.5]
            return max(0.0, 1.5 * (0.5 ** (age_days / 30.0)))

        scored: List = []
        for m in candidates:
            score = 0.0
            if trigger_source and m.get("trigger_source") == trigger_source:
                score += 3.0
            if chain and m.get("chain") == chain:
                score += 2.0
            if token_type and m.get("token_type") == token_type:
                score += 2.0
            if mcap_bucket and m.get("mcap_bucket") == mcap_bucket:
                score += 1.0
            score += _regime_score(regime, m.get("market_regime"))
            score += _freshness(m.get("created_at"))
            mc = int(m.get("match_count", 0) or 0)
            if mc > 0:
                score += min(1.0, math.log10(1 + mc))
            if score < min_score:
                continue
            scored.append({**m, "_score": round(score, 3)})

        scored.sort(key=lambda x: (-x["_score"], x.get("created_at", "") or ""), reverse=False)
        # 上面 created_at 升序;按 score 降序后,同分内 created_at 降序需要再排
        scored.sort(key=lambda x: -x["_score"])
        out = scored[:limit]

        # 异步 bump match_count(失败不阻断返回)
        if out:
            try:
                self._bump_match_count([m["id"] for m in out if m.get("id")])
            except Exception:
                pass
        return out

    def _bump_match_count(self, ids: List[str]) -> None:
        """命中的 episodic 记忆 match_count += 1。
        不在事务里跑(只是命中统计,丢失也无大碍)。
        """
        if not ids:
            return
        try:
            from database import get_db as _db
            for _id in ids:
                try:
                    # Supabase 不直接支持 SQL atomic,先读后写
                    cur = _db().table("agent_memory").select("match_count").eq("id", _id).limit(1).execute()
                    if cur.data:
                        prev = int(cur.data[0].get("match_count", 0) or 0)
                        _db().table("agent_memory").update({"match_count": prev + 1}).eq("id", _id).execute()
                except Exception:
                    continue
        except Exception:
            pass

    def cleanup_expired(self) -> int:
        """清理过期的 episodic 记忆"""
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            res = (
                get_db()
                .table("agent_memory")
                .delete()
                .eq("type", "episodic")
                .lt("expires_at", now_iso)
                .execute()
            )
            count = len(res.data) if res.data else 0
            if count > 0:
                self._cache_ts = 0
                log.info("[EpisodicMemory] Cleaned %d expired memories", count)
            return count
        except Exception as e:
            log.warning("Episodic cleanup failed: %s", e)
            return 0

    def _get_cached(self) -> List[Dict]:
        """带 30s 缓存的 DB 查询"""
        now = time.time()
        if now - self._cache_ts < CACHE_TTL and self._cache:
            return self._cache

        try:
            res = (
                get_db()
                .table("agent_memory")
                .select("*")
                .eq("type", "episodic")
                .eq("is_active", True)
                .order("created_at", desc=True)
                .limit(MAX_EPISODIC)
                .execute()
            )
            self._cache = res.data or []
            self._cache_ts = now
        except Exception as e:
            log.warning("Episodic cache load failed: %s", e)

        return self._cache

    def invalidate_cache(self) -> None:
        """手动使缓存失效"""
        self._cache_ts = 0
