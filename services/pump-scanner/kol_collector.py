"""
KOL 推文采集器 — twscrape 适配器

使用 twscrape 免费采集 Twitter KOL 推文。
支持多账号轮换，自动处理速率限制。

降级方案：如果 twscrape 被封，切换到 twitterapi.io ($49/月)

Python 3.9 兼容。
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from database import get_db

log = logging.getLogger(__name__)

# 尝试导入 twscrape
try:
    from twscrape import API as TwscrapeAPI
    from twscrape import gather
    TWSCRAPE_AVAILABLE = True
except ImportError:
    TWSCRAPE_AVAILABLE = False
    log.warning("twscrape not installed. Run: pip install twscrape")


class KOLCollector:
    """KOL 推文采集器"""

    def __init__(self, db_path: str = "twscrape_accounts.db"):
        self.db_path = db_path
        self._api = None  # type: Optional[Any]

    async def _get_api(self) -> Optional[Any]:
        """获取 twscrape API 实例"""
        if not TWSCRAPE_AVAILABLE:
            log.error("twscrape not available")
            return None

        if self._api is None:
            self._api = TwscrapeAPI(self.db_path)
        return self._api

    # ── 账号管理 ──────────────────────────────────────────────

    async def add_account(
        self,
        username: str,
        password: str,
        email: str,
        email_password: str,
    ) -> bool:
        """添加 Twitter 账号（用于采集）"""
        api = await self._get_api()
        if not api:
            return False

        try:
            await api.pool.add_account(
                username, password, email, email_password
            )
            await api.pool.login_all()
            log.info(f"Added account: {username}")
            return True
        except Exception as e:
            log.error(f"Failed to add account {username}: {e}")
            return False

    # ── 推文采集 ──────────────────────────────────────────────

    async def collect_user_tweets(
        self,
        username: str,
        twitter_uid: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        采集指定 KOL 的最新推文

        Args:
            username: Twitter username
            twitter_uid: 数据库中的 twitter_uid
            limit: 获取推文数量

        Returns:
            推文列表 [{tweet_id, content, tweeted_at, ...}]
        """
        api = await self._get_api()
        if not api:
            return []

        try:
            # 获取用户 ID
            user = await api.user_by_login(username)
            if not user:
                log.warning(f"User not found: {username}")
                return []

            # 获取用户时间线
            tweets = await gather(api.user_tweets(user.id, limit=limit))

            results = []  # type: List[Dict[str, Any]]
            for tweet in tweets:
                tweet_data = self._parse_tweet(tweet, twitter_uid)
                if tweet_data:
                    results.append(tweet_data)

            log.info(f"Collected {len(results)} tweets from @{username}")
            return results

        except Exception as e:
            log.error(f"Failed to collect tweets from @{username}: {e}")
            return []

    async def search_token_mentions(
        self,
        query: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        搜索含特定代币提及的推文

        Args:
            query: 搜索查询（如 "$BONK" 或 "pump.fun"）
            limit: 结果数量

        Returns:
            推文列表
        """
        api = await self._get_api()
        if not api:
            return []

        try:
            tweets = await gather(api.search(query, limit=limit))

            results = []  # type: List[Dict[str, Any]]
            for tweet in tweets:
                tweet_data = self._parse_tweet(tweet, "")
                if tweet_data:
                    results.append(tweet_data)

            return results

        except Exception as e:
            log.error(f"Search failed for '{query}': {e}")
            return []

    def _parse_tweet(
        self,
        tweet: Any,
        twitter_uid: str,
    ) -> Optional[Dict[str, Any]]:
        """解析 twscrape Tweet 对象为 dict"""
        try:
            return {
                "tweet_id": str(tweet.id),
                "twitter_uid": twitter_uid or str(tweet.user.id),
                "content": tweet.rawContent or "",
                "tweeted_at": tweet.date.isoformat() if tweet.date else datetime.utcnow().isoformat(),
                "reply_count": tweet.replyCount or 0,
                "retweet_count": tweet.retweetCount or 0,
                "like_count": tweet.likeCount or 0,
                "quote_count": tweet.quoteCount or 0,
                "view_count": tweet.viewCount or 0,
                "is_retweet": tweet.retweetedTweet is not None,
                "is_reply": tweet.inReplyToTweetId is not None,
                "raw_json": None,  # 可选存储原始 JSON
            }
        except Exception as e:
            log.debug(f"Failed to parse tweet: {e}")
            return None

    # ── 批量采集 ──────────────────────────────────────────────

    async def collect_all_kols(
        self,
        tweets_per_kol: int = 20,
        batch_size: int = 5,
        delay_between_batches: float = 5.0,
    ) -> Dict[str, int]:
        """
        批量采集所有活跃 KOL 的推文

        Args:
            tweets_per_kol: 每个 KOL 采集的推文数
            batch_size: 每批并行采集的 KOL 数
            delay_between_batches: 批次间延迟（秒）

        Returns:
            {username: tweet_count} 采集统计
        """
        # 从数据库加载活跃 KOL 列表
        kols = self._load_active_kols()
        if not kols:
            log.warning("No active KOLs to collect")
            return {}

        stats = {}  # type: Dict[str, int]
        total = len(kols)

        for i in range(0, total, batch_size):
            batch = kols[i:i + batch_size]
            log.info(
                f"Collecting batch {i // batch_size + 1}/"
                f"{(total + batch_size - 1) // batch_size}"
            )

            # 并行采集一批
            tasks = []
            for kol in batch:
                tasks.append(
                    self.collect_user_tweets(
                        username=kol["username"],
                        twitter_uid=kol["twitter_uid"],
                        limit=tweets_per_kol,
                    )
                )

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for kol, result in zip(batch, results):
                username = kol["username"]
                if isinstance(result, Exception):
                    log.error(f"Collection failed for @{username}: {result}")
                    stats[username] = 0
                else:
                    tweet_list = result
                    stats[username] = len(tweet_list)

                    # 保存到数据库
                    if tweet_list:
                        self._save_tweets(tweet_list)

                    # 更新 last_scanned_at
                    self._update_scan_time(kol["twitter_uid"])

            # 批次间延迟
            if i + batch_size < total:
                await asyncio.sleep(delay_between_batches)

        return stats

    # ── 数据库操作 ────────────────────────────────────────────

    def _load_active_kols(self) -> List[Dict[str, Any]]:
        """加载活跃 KOL 列表"""
        try:
            result = (
                get_db()
                .table("kol_accounts")
                .select("twitter_uid, username, tier")
                .eq("is_active", True)
                .order("followers_count", desc=True)
                .execute()
            )
            return result.data or []
        except Exception as e:
            log.error(f"Failed to load KOLs: {e}")
            return []

    def _save_tweets(self, tweets: List[Dict[str, Any]]):
        """保存推文到数据库（upsert）"""
        try:
            for i in range(0, len(tweets), 50):
                batch = tweets[i:i + 50]
                get_db().table("kol_tweets").upsert(
                    batch, on_conflict="tweet_id"
                ).execute()
        except Exception as e:
            log.error(f"Failed to save tweets: {e}")

    def _update_scan_time(self, twitter_uid: str):
        """更新 KOL 的最后扫描时间"""
        try:
            get_db().table("kol_accounts").update({
                "last_scanned_at": datetime.utcnow().isoformat(),
            }).eq("twitter_uid", twitter_uid).execute()
        except Exception as e:
            log.error(f"Failed to update scan time: {e}")
