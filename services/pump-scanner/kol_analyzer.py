"""
KOL 推文分析器 — NLP V1 规则引擎

功能：
1. 情绪分析（关键词 + Emoji）
2. 代币提取（$TICKER + SOL/EVM 地址）
3. 广告/推广检测
4. 互动率计算

V1 使用规则引擎（无需 ML 模型），
V2 可升级到 BERT/FinBERT。

Python 3.9 兼容。
"""
import re
import logging
from typing import Any, Dict, List, Optional, Tuple

from kol_config import (
    BULLISH_KEYWORDS,
    BEARISH_KEYWORDS,
    BULLISH_EMOJIS,
    BEARISH_EMOJIS,
    PROMO_KEYWORDS,
    TICKER_PATTERN,
    SOL_ADDRESS_PATTERN,
    EVM_ADDRESS_PATTERN,
    EXCLUDED_TICKERS,
)
from database import get_db

log = logging.getLogger(__name__)


class KOLAnalyzer:
    """KOL 推文分析器"""

    def analyze_tweet(
        self,
        tweet: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        分析单条推文

        Args:
            tweet: 推文数据 {tweet_id, content, ...}

        Returns:
            分析结果 {sentiment, sentiment_score, has_token_mention,
                     is_promotion, engagement_score, mentions: [...]}
        """
        content = tweet.get("content", "")
        content_lower = content.lower()

        # 1. 情绪分析
        sentiment, sentiment_score = self._analyze_sentiment(
            content, content_lower
        )

        # 2. 代币提取
        mentions = self._extract_token_mentions(content)
        has_token_mention = len(mentions) > 0

        # 3. 广告检测
        is_promotion = self._detect_promotion(content_lower)

        # 4. 互动率
        engagement_score = self._calc_engagement(tweet)

        return {
            "sentiment": sentiment,
            "sentiment_score": sentiment_score,
            "has_token_mention": has_token_mention,
            "is_promotion": is_promotion,
            "engagement_score": engagement_score,
            "mentions": mentions,
        }

    def analyze_and_update(
        self,
        tweet: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        分析推文并更新数据库

        Returns:
            分析结果
        """
        result = self.analyze_tweet(tweet)
        tweet_id = tweet.get("tweet_id", "")
        twitter_uid = tweet.get("twitter_uid", "")

        # 更新推文记录
        try:
            get_db().table("kol_tweets").update({
                "sentiment": result["sentiment"],
                "sentiment_score": result["sentiment_score"],
                "has_token_mention": result["has_token_mention"],
                "is_promotion": result["is_promotion"],
                "engagement_score": result["engagement_score"],
            }).eq("tweet_id", tweet_id).execute()
        except Exception as e:
            log.error(f"Failed to update tweet {tweet_id}: {e}")

        # 保存代币提及记录
        if result["has_token_mention"] and not result["is_promotion"]:
            for mention in result["mentions"]:
                self._save_mention(
                    tweet_id=tweet_id,
                    twitter_uid=twitter_uid,
                    mention=mention,
                    sentiment=result["sentiment"],
                    sentiment_score=result["sentiment_score"],
                    tweeted_at=tweet.get("tweeted_at", ""),
                    followers=tweet.get("followers_at_mention"),
                )

        return result

    # ── 情绪分析 ──────────────────────────────────────────────

    def _analyze_sentiment(
        self,
        content: str,
        content_lower: str,
    ) -> Tuple[str, float]:
        """
        基于关键词和 Emoji 的情绪分析

        Returns:
            (sentiment, score) — sentiment: bullish/bearish/neutral
            score: -1.0 到 1.0
        """
        bullish_score = 0.0
        bearish_score = 0.0

        # 关键词匹配
        for kw in BULLISH_KEYWORDS:
            if kw in content_lower:
                bullish_score += 1.0

        for kw in BEARISH_KEYWORDS:
            if kw in content_lower:
                bearish_score += 1.0

        # Emoji 匹配（权重 0.5）
        for emoji in BULLISH_EMOJIS:
            count = content.count(emoji)
            bullish_score += count * 0.5

        for emoji in BEARISH_EMOJIS:
            count = content.count(emoji)
            bearish_score += count * 0.5

        # 否定词检测（翻转情绪）
        negation_words = [
            "not ", "don't ", "dont ", "doesn't ", "doesnt ",
            "won't ", "wont ", "never ", "no ", "isn't ", "isnt ",
            "wasn't ", "wasnt ", "shouldn't ", "shouldnt ",
        ]
        has_negation = any(neg in content_lower for neg in negation_words)
        if has_negation:
            bullish_score, bearish_score = bearish_score * 0.5, bullish_score * 0.5

        # 计算最终分数
        total = bullish_score + bearish_score
        if total == 0:
            return "neutral", 0.0

        score = (bullish_score - bearish_score) / max(total, 1)
        score = max(-1.0, min(1.0, score))

        if score > 0.2:
            sentiment = "bullish"
        elif score < -0.2:
            sentiment = "bearish"
        else:
            sentiment = "neutral"

        return sentiment, round(score, 3)

    # ── 代币提取 ──────────────────────────────────────────────

    def _extract_token_mentions(
        self,
        content: str,
    ) -> List[Dict[str, Any]]:
        """
        从推文中提取代币提及

        支持：
        - $TICKER 格式（如 $BONK, $WIF）
        - SOL 地址（Base58, 32-44 字符）
        - EVM 地址（0x + 40 hex）

        Returns:
            [{ticker, token_address, chain}]
        """
        mentions = []  # type: List[Dict[str, Any]]
        seen_tickers = set()  # type: set

        # 1. $TICKER 提取
        ticker_matches = TICKER_PATTERN.findall(content)
        for ticker in ticker_matches:
            ticker_upper = ticker.upper()
            if ticker_upper not in EXCLUDED_TICKERS and ticker_upper not in seen_tickers:
                seen_tickers.add(ticker_upper)
                mentions.append({
                    "ticker": ticker_upper,
                    "token_address": None,
                    "chain": None,
                })

        # 2. SOL 地址提取
        sol_matches = SOL_ADDRESS_PATTERN.findall(content)
        for addr in sol_matches:
            # 过滤掉太短或看起来像普通单词的匹配
            if len(addr) >= 32 and not addr.isalpha():
                mentions.append({
                    "ticker": None,
                    "token_address": addr,
                    "chain": "solana",
                })

        # 3. EVM 地址提取
        evm_matches = EVM_ADDRESS_PATTERN.findall(content)
        for addr in evm_matches:
            mentions.append({
                "ticker": None,
                "token_address": addr.lower(),
                "chain": None,  # 需要后续判断是 BSC 还是 Base
            })

        return mentions

    # ── 广告检测 ──────────────────────────────────────────────

    def _detect_promotion(self, content_lower: str) -> bool:
        """检测广告/推广内容"""
        promo_count = sum(
            1 for kw in PROMO_KEYWORDS
            if kw in content_lower
        )
        return promo_count >= 2  # 至少匹配 2 个推广关键词才标记

    # ── 互动率计算 ────────────────────────────────────────────

    def _calc_engagement(self, tweet: Dict[str, Any]) -> float:
        """
        计算互动分数

        公式：(likes * 1 + retweets * 2 + replies * 3 + quotes * 2) / max(views, 1) * 10000
        """
        likes = tweet.get("like_count", 0) or 0
        retweets = tweet.get("retweet_count", 0) or 0
        replies = tweet.get("reply_count", 0) or 0
        quotes = tweet.get("quote_count", 0) or 0
        views = tweet.get("view_count", 1) or 1

        raw = (likes * 1 + retweets * 2 + replies * 3 + quotes * 2)
        score = raw / max(views, 1) * 10000

        return round(min(score, 100.0), 2)

    # ── 数据库操作 ────────────────────────────────────────────

    def _save_mention(
        self,
        tweet_id: str,
        twitter_uid: str,
        mention: Dict[str, Any],
        sentiment: str,
        sentiment_score: float,
        tweeted_at: str,
        followers: Optional[int] = None,
    ):
        """保存代币提及记录"""
        try:
            row = {
                "tweet_id": tweet_id,
                "twitter_uid": twitter_uid,
                "token_address": mention.get("token_address"),
                "chain": mention.get("chain"),
                "ticker": mention.get("ticker") or "UNKNOWN",
                "sentiment": sentiment,
                "sentiment_score": sentiment_score,
                "mentioned_at": tweeted_at,
                "followers_at_mention": followers,
            }
            get_db().table("token_kol_mentions").insert(row).execute()
        except Exception as e:
            # 重复插入可能报错，忽略
            if "duplicate" not in str(e).lower():
                log.error(f"Failed to save mention: {e}")


def batch_analyze(limit: int = 500) -> int:
    """
    批量分析未分析的推文

    Returns:
        处理的推文数
    """
    analyzer = KOLAnalyzer()

    try:
        # 获取未分析的推文（sentiment = 'neutral' 且 sentiment_score = 0）
        result = (
            get_db()
            .table("kol_tweets")
            .select("*")
            .eq("sentiment", "neutral")
            .eq("sentiment_score", 0)
            .limit(limit)
            .execute()
        )

        tweets = result.data or []
        if not tweets:
            return 0

        for tweet in tweets:
            analyzer.analyze_and_update(tweet)

        log.info(f"Analyzed {len(tweets)} tweets")
        return len(tweets)

    except Exception as e:
        log.error(f"batch_analyze error: {e}")
        return 0
