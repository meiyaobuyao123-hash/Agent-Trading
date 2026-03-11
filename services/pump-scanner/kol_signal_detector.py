"""
KOL 共振信号检测器

在时间窗口内检测多个 KOL 同时提及某个代币的 "共振" 现象。
共振强度越高，信号越可靠。

检测逻辑：
1. 扫描最近 N 小时内的所有代币提及
2. 按 ticker/token_address 分组
3. 对每组计算 KOL 数量、tier 分布、情绪一致性
4. 超过阈值的生成 kol_signals 记录

Python 3.9 兼容。
"""
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

from database import get_db
from kol_config import (
    SIGNAL_WINDOW_HOURS,
    SIGNAL_MIN_KOL_COUNT,
    SIGNAL_DECAY_HOURS,
)

log = logging.getLogger(__name__)


class KOLSignalDetector:
    """KOL 共振信号检测器"""

    def detect_signals(
        self,
        window_hours: int = SIGNAL_WINDOW_HOURS,
        min_kol_count: int = SIGNAL_MIN_KOL_COUNT,
    ) -> List[Dict[str, Any]]:
        """
        检测共振信号

        Args:
            window_hours: 检测时间窗口（小时）
            min_kol_count: 最少 KOL 提及数

        Returns:
            新检测到的信号列表
        """
        # 1. 获取时间窗口内的所有提及
        mentions = self._get_recent_mentions(window_hours)
        if not mentions:
            return []

        # 2. 按 ticker 分组
        grouped = self._group_mentions(mentions)

        # 3. 对每组计算信号强度
        signals = []  # type: List[Dict[str, Any]]
        for key, group_mentions in grouped.items():
            unique_kols = set(m["twitter_uid"] for m in group_mentions)
            if len(unique_kols) < min_kol_count:
                continue

            signal = self._calculate_signal(key, group_mentions, window_hours)
            if signal:
                signals.append(signal)

        # 4. 保存信号到数据库
        if signals:
            self._save_signals(signals)
            log.info(f"Detected {len(signals)} KOL signals")

        # 5. 过期旧信号
        self._expire_old_signals()

        return signals

    def _get_recent_mentions(
        self,
        window_hours: int,
    ) -> List[Dict[str, Any]]:
        """获取时间窗口内的代币提及"""
        try:
            since = (
                datetime.utcnow() - timedelta(hours=window_hours)
            ).isoformat()

            result = (
                get_db()
                .table("token_kol_mentions")
                .select(
                    "tweet_id, twitter_uid, token_address, chain, "
                    "ticker, sentiment, sentiment_score, "
                    "followers_at_mention, mentioned_at"
                )
                .gte("mentioned_at", since)
                .execute()
            )
            return result.data or []

        except Exception as e:
            log.error(f"Failed to get recent mentions: {e}")
            return []

    def _group_mentions(
        self,
        mentions: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        按 ticker 或 token_address 分组

        优先用 token_address（精确匹配），
        没有地址的用 ticker（可能有同名问题）
        """
        grouped = defaultdict(list)  # type: Dict[str, List[Dict[str, Any]]]

        for mention in mentions:
            addr = mention.get("token_address")
            chain = mention.get("chain", "")
            ticker = mention.get("ticker", "")

            if addr:
                key = f"{chain}:{addr}"
            elif ticker:
                key = f"ticker:{ticker}"
            else:
                continue

            grouped[key].append(mention)

        return dict(grouped)

    def _calculate_signal(
        self,
        key: str,
        mentions: List[Dict[str, Any]],
        window_hours: int,
    ) -> Optional[Dict[str, Any]]:
        """
        计算单个代币的共振信号强度

        信号强度（0-10）由以下因子决定：
        - KOL 数量 (0-3 分)
        - KOL 质量/tier (0-3 分)
        - 情绪一致性 (0-2 分)
        - 总触达粉丝数 (0-2 分)
        """
        # 获取唯一 KOL 及其 tier
        kol_tiers = self._get_kol_tiers(mentions)
        unique_kol_count = len(kol_tiers)

        # 按 tier 统计
        tier_counts = {"mega": 0, "large": 0, "medium": 0, "small": 0}
        for uid, tier in kol_tiers.items():
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

        # 情绪统计
        sentiments = [m.get("sentiment_score", 0) for m in mentions]
        avg_sentiment = sum(sentiments) / max(len(sentiments), 1)
        bullish_count = sum(1 for s in sentiments if s > 0.2)
        bearish_count = sum(1 for s in sentiments if s < -0.2)
        total_sentiment = bullish_count + bearish_count
        bullish_ratio = bullish_count / max(total_sentiment, 1)

        # 总触达粉丝数
        total_reach = sum(
            m.get("followers_at_mention", 0) or 0
            for m in mentions
        )

        # 解析 key
        if key.startswith("ticker:"):
            ticker = key.split(":")[1]
            token_address = None
            chain = None
        else:
            parts = key.split(":", 1)
            chain = parts[0] if parts[0] else None
            token_address = parts[1] if len(parts) > 1 else None
            ticker = mentions[0].get("ticker", "")

        # 计算信号强度
        strength = self._calc_strength(
            unique_kol_count, tier_counts, avg_sentiment, total_reach
        )

        # 收集 KOL usernames
        kol_usernames = self._get_kol_usernames(list(kol_tiers.keys()))

        return {
            "token_address": token_address,
            "chain": chain,
            "ticker": ticker or "UNKNOWN",
            "signal_strength": round(strength, 2),
            "kol_count": unique_kol_count,
            "mega_count": tier_counts.get("mega", 0),
            "large_count": tier_counts.get("large", 0),
            "medium_count": tier_counts.get("medium", 0),
            "small_count": tier_counts.get("small", 0),
            "avg_sentiment": round(avg_sentiment, 3),
            "bullish_ratio": round(bullish_ratio, 3),
            "total_reach": total_reach,
            "window_hours": window_hours,
            "kol_usernames": kol_usernames,
            "is_active": True,
            "expires_at": (
                datetime.utcnow() + timedelta(hours=SIGNAL_DECAY_HOURS)
            ).isoformat(),
        }

    def _calc_strength(
        self,
        kol_count: int,
        tier_counts: Dict[str, int],
        avg_sentiment: float,
        total_reach: int,
    ) -> float:
        """
        计算信号强度 (0-10)

        评分维度：
        - KOL 数量 (0-3): 3→1, 5→2, 10+→3
        - KOL 质量 (0-3): mega*3 + large*2 + medium*1 + small*0.5
        - 情绪一致性 (0-2): 绝对值 * 2
        - 粉丝触达 (0-2): log 尺度
        """
        import math

        # 数量分
        if kol_count >= 10:
            count_score = 3.0
        elif kol_count >= 5:
            count_score = 2.0
        elif kol_count >= 3:
            count_score = 1.0
        else:
            count_score = 0.5

        # 质量分
        quality_raw = (
            tier_counts.get("mega", 0) * 3.0 +
            tier_counts.get("large", 0) * 2.0 +
            tier_counts.get("medium", 0) * 1.0 +
            tier_counts.get("small", 0) * 0.5
        )
        quality_score = min(quality_raw / 3.0, 3.0)

        # 情绪一致性分
        sentiment_score = min(abs(avg_sentiment) * 2.5, 2.0)

        # 粉丝触达分
        if total_reach > 0:
            reach_score = min(math.log10(total_reach + 1) / 3.0, 2.0)
        else:
            reach_score = 0.0

        total = count_score + quality_score + sentiment_score + reach_score
        return min(total, 10.0)

    def _get_kol_tiers(
        self,
        mentions: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        """获取提及中各 KOL 的 tier"""
        uids = list(set(m["twitter_uid"] for m in mentions))
        try:
            result = (
                get_db()
                .table("kol_accounts")
                .select("twitter_uid, tier")
                .in_("twitter_uid", uids)
                .execute()
            )
            return {r["twitter_uid"]: r["tier"] for r in (result.data or [])}
        except Exception as e:
            log.error(f"Failed to get KOL tiers: {e}")
            return {uid: "small" for uid in uids}

    def _get_kol_usernames(
        self,
        uids: List[str],
    ) -> List[str]:
        """获取 KOL usernames"""
        try:
            result = (
                get_db()
                .table("kol_accounts")
                .select("username")
                .in_("twitter_uid", uids)
                .execute()
            )
            return [r["username"] for r in (result.data or [])]
        except Exception:
            return []

    def _save_signals(self, signals: List[Dict[str, Any]]):
        """保存信号到数据库"""
        try:
            for signal in signals:
                get_db().table("kol_signals").insert(signal).execute()
        except Exception as e:
            log.error(f"Failed to save signals: {e}")

    def _expire_old_signals(self):
        """过期旧信号"""
        try:
            now = datetime.utcnow().isoformat()
            get_db().table("kol_signals").update(
                {"is_active": False}
            ).lt("expires_at", now).eq("is_active", True).execute()
        except Exception as e:
            log.error(f"Failed to expire signals: {e}")
