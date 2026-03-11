"""
KOL 推文采集器 — twitterapi.io 适配器

使用 twitterapi.io REST API 采集 Twitter KOL 推文。
按量付费 ($0.15/千条推文)，无需 OAuth，仅需 API Key。

API 文档：https://docs.twitterapi.io/

Python 3.9 兼容。
"""
import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from database import get_db
from kol_config import TWITTERAPI_IO_KEY, SCAN_DELAY_BETWEEN_S

log = logging.getLogger(__name__)

# twitterapi.io 基础 URL
BASE_URL = "https://api.twitterapi.io"


class KOLCollector:
    """KOL 推文采集器 — twitterapi.io"""

    def __init__(self):
        self._api_key = TWITTERAPI_IO_KEY
        if not self._api_key:
            log.warning(
                "TWITTERAPI_IO_KEY not set. "
                "Get one at https://twitterapi.io and set env TWITTERAPI_IO_KEY"
            )

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "X-API-Key": self._api_key,
            "Accept": "application/json",
        }

    # ── HTTP 请求层 ─────────────────────────────────────────────

    async def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        retries: int = 3,
    ) -> Optional[Dict[str, Any]]:
        """
        发送 GET 请求到 twitterapi.io

        支持 aiohttp (优先) 或 httpx 作为 HTTP 客户端。
        自动重试 + 指数退避。
        """
        url = f"{BASE_URL}{path}"

        for attempt in range(retries):
            try:
                data = await self._do_get(url, params)
                if data is not None:
                    return data
            except Exception as e:
                wait = 2 ** attempt
                log.warning(
                    f"Request failed (attempt {attempt + 1}/{retries}): "
                    f"{path} — {e}, retry in {wait}s"
                )
                await asyncio.sleep(wait)

        log.error(f"All {retries} attempts failed for {path}")
        return None

    async def _do_get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """实际 HTTP GET（aiohttp 优先，httpx 备选）"""

        if AIOHTTP_AVAILABLE:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=self._headers, params=params, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status == 429:
                        retry_after = int(resp.headers.get("Retry-After", "60"))
                        log.warning(f"Rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                        return None
                    else:
                        text = await resp.text()
                        log.error(f"HTTP {resp.status}: {text[:200]}")
                        return None

        elif HTTPX_AVAILABLE:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, headers=self._headers, params=params)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", "60"))
                    log.warning(f"Rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    return None
                else:
                    log.error(f"HTTP {resp.status_code}: {resp.text[:200]}")
                    return None

        else:
            # 同步 fallback: urllib
            import urllib.request
            import urllib.parse
            import urllib.error

            if params:
                qs = urllib.parse.urlencode(params)
                url = f"{url}?{qs}"

            req = urllib.request.Request(url, headers=self._headers)
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    body = resp.read().decode("utf-8")
                    return json.loads(body)
            except urllib.error.HTTPError as e:
                log.error(f"HTTP {e.code}: {e.read().decode()[:200]}")
                return None

    # ── 用户信息 ────────────────────────────────────────────────

    async def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """
        获取用户基本信息

        API: GET /twitter/user/info?userName=xxx

        Returns:
            用户信息 dict，包含 id, name, followers, following 等
        """
        data = await self._get(
            "/twitter/user/info",
            params={"userName": username},
        )

        if not data or data.get("status") != "success":
            log.warning(f"User info failed for @{username}: {data}")
            return None

        return data.get("data")

    # ── 推文采集 ────────────────────────────────────────────────

    async def collect_user_tweets(
        self,
        username: str,
        twitter_uid: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        采集指定 KOL 的最新推文

        API: GET /twitter/user/last_tweets?userName=xxx

        Args:
            username: Twitter @handle
            twitter_uid: 数据库中的 twitter_uid
            limit: 最多获取推文数

        Returns:
            推文列表 [{tweet_id, content, tweeted_at, ...}]
        """
        if not self._api_key:
            log.error("TWITTERAPI_IO_KEY not configured")
            return []

        results = []  # type: List[Dict[str, Any]]
        cursor = ""
        pages = 0
        max_pages = (limit + 19) // 20  # 每页最多 20 条

        while pages < max_pages:
            params = {"userName": username}  # type: Dict[str, Any]
            if cursor:
                params["cursor"] = cursor

            resp = await self._get("/twitter/user/last_tweets", params=params)
            if not resp:
                break

            # twitterapi.io 返回结构：
            # {status, data: {pin_tweet, tweets: [...]}, has_next_page, next_cursor}
            # 或旧格式：{tweets: [...], has_next_page, next_cursor}
            inner = resp.get("data", resp)
            if isinstance(inner, dict):
                tweets = inner.get("tweets", [])
            else:
                tweets = resp.get("tweets", [])

            if not tweets:
                break

            for tweet in tweets:
                parsed = self._parse_tweet(tweet, twitter_uid)
                if parsed:
                    results.append(parsed)

                if len(results) >= limit:
                    break

            # 分页
            if resp.get("has_next_page") and len(results) < limit:
                cursor = resp.get("next_cursor", "")
                if not cursor:
                    break
                pages += 1
            else:
                break

        log.info(f"Collected {len(results)} tweets from @{username}")
        return results[:limit]

    async def search_token_mentions(
        self,
        query: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        搜索含特定代币提及的推文

        API: GET /twitter/tweet/advanced_search

        支持 Twitter 高级搜索语法：
        - "$BONK" — 搜索 ticker
        - "pump.fun" — 搜索关键词
        - "$PEPE min_faves:100" — 最少 100 赞

        Args:
            query: 搜索查询
            limit: 最多返回数

        Returns:
            推文列表
        """
        if not self._api_key:
            return []

        results = []  # type: List[Dict[str, Any]]
        cursor = ""
        max_pages = (limit + 19) // 20

        for page in range(max_pages):
            params = {
                "query": query,
                "queryType": "Latest",
            }  # type: Dict[str, Any]
            if cursor:
                params["cursor"] = cursor

            resp = await self._get(
                "/twitter/tweet/advanced_search", params=params
            )
            if not resp:
                break

            # 兼容两种返回结构
            inner = resp.get("data", resp)
            if isinstance(inner, dict):
                tweets = inner.get("tweets", resp.get("tweets", []))
            else:
                tweets = resp.get("tweets", [])

            if not tweets:
                break

            for tweet in tweets:
                parsed = self._parse_tweet(tweet, "")
                if parsed:
                    results.append(parsed)

                if len(results) >= limit:
                    break

            if resp.get("has_next_page") and len(results) < limit:
                cursor = resp.get("next_cursor", "")
                if not cursor:
                    break
            else:
                break

        return results[:limit]

    # ── 推文解析 ────────────────────────────────────────────────

    def _parse_tweet(
        self,
        tweet: Dict[str, Any],
        twitter_uid: str,
    ) -> Optional[Dict[str, Any]]:
        """
        解析 twitterapi.io 推文 JSON 为标准 dict

        twitterapi.io 返回字段：
        - id, text, createdAt, url
        - retweetCount, replyCount, likeCount, quoteCount, viewCount
        - author: {userName, id, followers, ...}
        - isReply, retweeted_tweet, quoted_tweet
        """
        try:
            author = tweet.get("author", {})
            author_uid = str(author.get("id", ""))
            uid = twitter_uid or author_uid

            # 解析时间
            created_at = tweet.get("createdAt", "")
            if created_at:
                # twitterapi.io 格式: "Thu Jun 01 12:00:00 +0000 2025"
                try:
                    dt = datetime.strptime(
                        created_at, "%a %b %d %H:%M:%S %z %Y"
                    )
                    tweeted_at = dt.isoformat()
                except ValueError:
                    # 可能已经是 ISO 格式
                    tweeted_at = created_at
            else:
                tweeted_at = datetime.utcnow().isoformat()

            # 判断是否为转推
            is_retweet = tweet.get("retweeted_tweet") is not None
            is_reply = bool(tweet.get("isReply", False))

            return {
                "tweet_id": str(tweet.get("id", "")),
                "twitter_uid": uid,
                "content": tweet.get("text", ""),
                "tweeted_at": tweeted_at,
                "reply_count": int(tweet.get("replyCount", 0) or 0),
                "retweet_count": int(tweet.get("retweetCount", 0) or 0),
                "like_count": int(tweet.get("likeCount", 0) or 0),
                "quote_count": int(tweet.get("quoteCount", 0) or 0),
                "view_count": int(tweet.get("viewCount", 0) or 0),
                "is_retweet": is_retweet,
                "is_reply": is_reply,
                "raw_json": tweet,
            }
        except Exception as e:
            log.debug(f"Failed to parse tweet: {e}")
            return None

    # ── 批量采集 ─────────────────────────────────────────────────

    async def collect_all_kols(
        self,
        tweets_per_kol: int = 20,
        batch_size: int = 5,
        delay_between_batches: float = 3.0,
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
        if not self._api_key:
            log.error("TWITTERAPI_IO_KEY not configured, cannot collect")
            return {}

        # 从数据库加载活跃 KOL 列表
        kols = self._load_active_kols()
        if not kols:
            log.warning("No active KOLs to collect")
            return {}

        stats = {}  # type: Dict[str, int]
        total = len(kols)
        total_batches = (total + batch_size - 1) // batch_size

        log.info(f"Starting collection: {total} KOLs in {total_batches} batches")

        for i in range(0, total, batch_size):
            batch = kols[i:i + batch_size]
            batch_num = i // batch_size + 1
            log.info(f"Collecting batch {batch_num}/{total_batches}")

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

            # 批次间延迟（避免 API 速率限制）
            if i + batch_size < total:
                await asyncio.sleep(delay_between_batches)

        # 汇总统计
        active = len([v for v in stats.values() if v > 0])
        total_tweets = sum(stats.values())
        log.info(
            f"Collection complete: {active}/{total} KOLs active, "
            f"{total_tweets} tweets total"
        )

        return stats

    # ── 同步 KOL 资料 ───────────────────────────────────────────

    async def sync_kol_profiles(self, usernames: Optional[List[str]] = None):
        """
        同步 KOL Twitter 资料（粉丝数、bio 等）

        Args:
            usernames: 指定同步的用户名列表，None 则同步所有活跃 KOL
        """
        if not self._api_key:
            log.error("TWITTERAPI_IO_KEY not configured")
            return

        if usernames is None:
            kols = self._load_active_kols()
            usernames = [k["username"] for k in kols]

        updated = 0
        for username in usernames:
            try:
                info = await self.get_user_info(username)
                if not info:
                    continue

                # 更新数据库
                update_data = {
                    "twitter_uid": str(info.get("id", username)),
                    "display_name": info.get("name", ""),
                    "bio": info.get("description", ""),
                    "followers_count": int(info.get("followers", 0) or 0),
                    "following_count": int(info.get("following", 0) or 0),
                    "tweet_count": int(info.get("statusesCount", 0) or 0),
                }

                # 根据粉丝数更新 tier
                followers = update_data["followers_count"]
                if followers >= 500000:
                    update_data["tier"] = "mega"
                elif followers >= 100000:
                    update_data["tier"] = "large"
                elif followers >= 20000:
                    update_data["tier"] = "medium"
                else:
                    update_data["tier"] = "small"

                get_db().table("kol_accounts").update(
                    update_data
                ).eq("username", username).execute()

                updated += 1
                # 避免频率限制
                await asyncio.sleep(SCAN_DELAY_BETWEEN_S)

            except Exception as e:
                log.error(f"Failed to sync @{username}: {e}")

        log.info(f"Synced {updated}/{len(usernames)} KOL profiles")

    # ── 数据库操作 ────────────────────────────────────────────────

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
        """保存推文到数据库（upsert on tweet_id）"""
        try:
            # 过滤掉空 tweet_id
            valid = [t for t in tweets if t.get("tweet_id")]

            for i in range(0, len(valid), 50):
                batch = valid[i:i + 50]
                # 移除 raw_json 中的大字段以减少存储
                for t in batch:
                    if t.get("raw_json"):
                        # 只保留必要字段
                        raw = t["raw_json"]
                        t["raw_json"] = json.dumps({
                            "entities": raw.get("entities"),
                            "lang": raw.get("lang"),
                            "source": raw.get("source"),
                        }, ensure_ascii=False) if isinstance(raw, dict) else None

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
