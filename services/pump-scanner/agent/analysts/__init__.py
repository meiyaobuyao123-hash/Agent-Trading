"""
PRD-007 M5: 三个分析师 Agent（并行执行）

- TechnicalAnalyst: 技术分析（RSI/MACD/MA/ATR/支撑阻力）
- SentimentAnalyst: 情绪分析（恐慌指数/资金费率/聪明钱/KOL）
- OnchainAnalyst:   链上分析（holder/流动性/成交量/资金流向）

模型：Claude Haiku（$0.25/1M tokens，便宜且快）
并行：asyncio.gather，总耗时 ~1s

Python 3.9 兼容。
"""

from .technical import TechnicalAnalyst
from .sentiment import SentimentAnalyst
from .onchain import OnchainAnalyst

__all__ = ["TechnicalAnalyst", "SentimentAnalyst", "OnchainAnalyst"]
