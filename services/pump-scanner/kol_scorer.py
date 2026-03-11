"""
KOL 评分维度 — K 维度（10 分）

将 KOL 信号整合到现有评分体系：
原有：M(50) + Q(30) + P(20) = 100
调整：M(45) + Q(27) + P(18) + K(10) = 100

K 维度分解：
- K1: KOL 提及数量 (4分)
- K2: KOL 质量加权 (3分)
- K3: 情绪一致性 (3分)

Python 3.9 兼容。
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from database import get_db
from kol_config import K_SCORE_WEIGHTS

log = logging.getLogger(__name__)


def calculate_k_score(
    token_address: Optional[str] = None,
    chain: Optional[str] = None,
    ticker: Optional[str] = None,
    window_hours: int = 24,
) -> Dict[str, Any]:
    """
    计算 K 维度评分（0-10 分）

    Args:
        token_address: 代币地址（可选）
        chain: 链（可选）
        ticker: Ticker 符号（可选）
        window_hours: 时间窗口

    Returns:
        {k_score, k1, k2, k3, details}
    """
    # 获取时间窗口内的提及数据
    mentions = _get_token_mentions(
        token_address, chain, ticker, window_hours
    )

    if not mentions:
        return {
            "k_score": 0.0,
            "k1_mention_count": 0.0,
            "k2_quality": 0.0,
            "k3_sentiment": 0.0,
            "mention_count": 0,
            "kol_count": 0,
        }

    # 获取提及的 KOL 信息
    unique_uids = list(set(m["twitter_uid"] for m in mentions))
    kol_info = _get_kol_info(unique_uids)
    kol_count = len(unique_uids)

    # K1: 提及数量 (4分)
    k1 = _calc_k1_mention_count(kol_count)

    # K2: 质量加权 (3分)
    k2 = _calc_k2_quality(kol_info)

    # K3: 情绪一致性 (3分)
    k3 = _calc_k3_sentiment(mentions)

    # 加权总分
    w = K_SCORE_WEIGHTS
    k_score = (
        k1 * w["mention_count"] / 4.0 +
        k2 * w["quality_weighted"] / 3.0 +
        k3 * w["sentiment_consensus"] / 3.0
    )
    k_score = round(min(k_score, 10.0), 2)

    return {
        "k_score": k_score,
        "k1_mention_count": round(k1, 2),
        "k2_quality": round(k2, 2),
        "k3_sentiment": round(k3, 2),
        "mention_count": len(mentions),
        "kol_count": kol_count,
    }


def _calc_k1_mention_count(kol_count: int) -> float:
    """
    K1: KOL 提及数量 (0-4 分)

    1 KOL → 0.5
    2 KOL → 1.0
    3 KOL → 2.0
    5 KOL → 3.0
    10+ KOL → 4.0
    """
    if kol_count >= 10:
        return 4.0
    elif kol_count >= 5:
        return 3.0
    elif kol_count >= 3:
        return 2.0
    elif kol_count >= 2:
        return 1.0
    elif kol_count >= 1:
        return 0.5
    return 0.0


def _calc_k2_quality(
    kol_info: List[Dict[str, Any]],
) -> float:
    """
    K2: KOL 质量加权 (0-3 分)

    tier 权重：mega=3, large=2, medium=1, small=0.3
    accuracy_2x 额外加成
    """
    if not kol_info:
        return 0.0

    tier_weights = {
        "mega": 3.0,
        "large": 2.0,
        "medium": 1.0,
        "small": 0.3,
    }

    total_weight = 0.0
    for kol in kol_info:
        tier = kol.get("tier", "small")
        base = tier_weights.get(tier, 0.3)

        # 准确率加成（如果有历史数据）
        accuracy = kol.get("accuracy_2x", 0)
        if accuracy > 0:
            base *= (1 + accuracy * 0.5)  # 最多 +50% 加成

        total_weight += base

    # 归一化到 0-3
    score = min(total_weight / 3.0, 3.0)
    return score


def _calc_k3_sentiment(
    mentions: List[Dict[str, Any]],
) -> float:
    """
    K3: 情绪一致性 (0-3 分)

    情绪越一致（同方向），分数越高
    混合情绪（有看多有看空）分数降低
    """
    if not mentions:
        return 0.0

    scores = [m.get("sentiment_score", 0) for m in mentions]
    if not scores:
        return 0.0

    avg = sum(scores) / len(scores)
    abs_avg = abs(avg)

    # 一致性：标准差越小越一致
    if len(scores) > 1:
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        std = variance ** 0.5
        consistency = max(0, 1.0 - std)  # std 越小，consistency 越高
    else:
        consistency = 1.0

    # 强度 * 一致性
    score = abs_avg * consistency * 3.0
    return min(score, 3.0)


def _get_token_mentions(
    token_address: Optional[str],
    chain: Optional[str],
    ticker: Optional[str],
    window_hours: int,
) -> List[Dict[str, Any]]:
    """获取代币的 KOL 提及"""
    try:
        since = (
            datetime.utcnow() - timedelta(hours=window_hours)
        ).isoformat()

        query = (
            get_db()
            .table("token_kol_mentions")
            .select("twitter_uid, sentiment, sentiment_score, mentioned_at")
            .gte("mentioned_at", since)
        )

        if token_address:
            query = query.eq("token_address", token_address)
            if chain:
                query = query.eq("chain", chain)
        elif ticker:
            query = query.eq("ticker", ticker)
        else:
            return []

        result = query.execute()
        return result.data or []

    except Exception as e:
        log.error(f"Failed to get mentions: {e}")
        return []


def _get_kol_info(uids: List[str]) -> List[Dict[str, Any]]:
    """获取 KOL 基本信息"""
    if not uids:
        return []

    try:
        result = (
            get_db()
            .table("kol_accounts")
            .select("twitter_uid, username, tier, accuracy_2x, followers_count")
            .in_("twitter_uid", uids)
            .execute()
        )
        return result.data or []
    except Exception as e:
        log.error(f"Failed to get KOL info: {e}")
        return []


def adjust_hot_coin_score(
    original_score: float,
    k_score: float,
    original_max: float = 100.0,
) -> float:
    """
    将 K 维度得分整合到热币总分

    原有 100 分体系调整为：
    M(45) + Q(27) + P(18) + K(10) = 100

    Args:
        original_score: 原有评分 (0-100)
        k_score: K 维度得分 (0-10)
        original_max: 原有满分

    Returns:
        调整后总分 (0-100)
    """
    # 原有部分缩放：100 → 90
    adjusted_original = original_score * 90.0 / original_max

    # 加上 K 维度
    total = adjusted_original + k_score

    return round(min(total, 100.0), 2)
