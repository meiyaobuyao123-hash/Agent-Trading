"""CryptoPanic — 加密新闻 + 情绪标签（每 30 分钟）"""
import logging
from typing import Dict, Any

import aiohttp

from btc_eth.collectors.base_collector import BaseCollector
from btc_eth.config import CRYPTOPANIC_API_KEY, CRYPTOPANIC_URL, INTERVAL_MID_FREQ

log = logging.getLogger(__name__)
_TIMEOUT = aiohttp.ClientTimeout(total=10)


class CryptoPanicCollector(BaseCollector):

    def __init__(self):
        super().__init__("cryptopanic", INTERVAL_MID_FREQ)
        self._session = None

    async def init(self):
        self._session = aiohttp.ClientSession()

    async def close(self):
        if self._session:
            await self._session.close()

    async def collect(self) -> Dict[str, Any]:
        params = {
            "auth_token": CRYPTOPANIC_API_KEY,
            "currencies": "BTC,ETH",
            "filter": "hot",
            "public": "true",
        }
        # 无 API Key 时用公开端点
        if not CRYPTOPANIC_API_KEY:
            params.pop("auth_token", None)

        async with self._session.get(CRYPTOPANIC_URL, params=params, timeout=_TIMEOUT) as resp:
            if resp.status != 200:
                raise Exception(f"HTTP {resp.status}")
            data = await resp.json()

        posts = data.get("results", [])
        if not posts:
            return {"news_sentiment": 0, "news_count": 0, "top_headlines": []}

        # 计算情绪分数 (-1 到 +1)
        sentiments = []
        headlines = []
        for p in posts[:20]:
            votes = p.get("votes", {})
            positive = votes.get("positive", 0) + votes.get("liked", 0)
            negative = votes.get("negative", 0) + votes.get("disliked", 0)
            total = positive + negative
            if total > 0:
                score = (positive - negative) / total
                sentiments.append(score)

            headlines.append({
                "title": p.get("title", "")[:100],
                "source": p.get("source", {}).get("title", ""),
                "sentiment": "bullish" if positive > negative else ("bearish" if negative > positive else "neutral"),
                "url": p.get("url", ""),
            })

        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0

        return {
            "news_sentiment": round(avg_sentiment, 4),
            "news_count": len(posts),
            "top_headlines": headlines[:5],
        }
