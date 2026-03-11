"""
KOL 系统调度入口 — APScheduler 任务

定时任务：
- 每 30 分钟：采集 KOL 推文
- 每 30 分钟：分析未处理的推文
- 每 1 小时：共振信号检测
- 每 24 小时：KOL 准确率评估

Python 3.9 兼容。
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from database import get_db
from kol_collector import KOLCollector
from kol_analyzer import KOLAnalyzer, batch_analyze
from kol_signal_detector import KOLSignalDetector

log = logging.getLogger(__name__)

# 全局实例
_collector = KOLCollector()
_analyzer = KOLAnalyzer()
_signal_detector = KOLSignalDetector()


async def run_kol_collect():
    """
    KOL 推文采集任务

    每 30 分钟执行一次，采集所有活跃 KOL 的最新推文
    """
    log.info("=== KOL 推文采集开始 ===")
    start = datetime.utcnow()

    try:
        stats = await _collector.collect_all_kols(
            tweets_per_kol=20,
            batch_size=5,
            delay_between_batches=5.0,
        )

        total_tweets = sum(stats.values())
        active_kols = len([v for v in stats.values() if v > 0])

        elapsed = (datetime.utcnow() - start).total_seconds()
        log.info(
            f"KOL 采集完成: {active_kols} KOL, "
            f"{total_tweets} 推文, {elapsed:.1f}s"
        )

    except Exception as e:
        log.error(f"KOL 采集失败: {e}")


async def run_kol_analyze():
    """
    KOL 推文分析任务

    分析未处理的推文：情绪分析 + 代币提取 + 广告检测
    """
    log.info("=== KOL 推文分析开始 ===")
    start = datetime.utcnow()

    try:
        processed = batch_analyze(limit=500)
        elapsed = (datetime.utcnow() - start).total_seconds()
        log.info(f"KOL 分析完成: {processed} 条推文, {elapsed:.1f}s")

    except Exception as e:
        log.error(f"KOL 分析失败: {e}")


async def run_kol_signal_detect():
    """
    KOL 共振信号检测任务

    每 1 小时执行一次，检测多 KOL 共振提及
    """
    log.info("=== KOL 共振信号检测开始 ===")
    start = datetime.utcnow()

    try:
        signals = _signal_detector.detect_signals(
            window_hours=24,
            min_kol_count=3,
        )

        elapsed = (datetime.utcnow() - start).total_seconds()
        log.info(
            f"信号检测完成: {len(signals)} 个共振信号, {elapsed:.1f}s"
        )

        # 对强信号发布事件到 Agent 系统
        if signals:
            try:
                from agent.event_bus import get_event_bus
                bus = get_event_bus()
                for signal in signals:
                    if signal.get("signal_strength", 0) >= 5.0:
                        await bus.publish("data.kol_signal", signal)
            except ImportError:
                pass  # Agent 系统未启用

    except Exception as e:
        log.error(f"信号检测失败: {e}")


async def run_kol_accuracy_eval():
    """
    KOL 准确率评估任务

    每 24 小时执行一次，评估 KOL 历史推荐的准确性
    """
    log.info("=== KOL 准确率评估开始 ===")
    start = datetime.utcnow()

    try:
        evaluated = await _evaluate_accuracy()
        elapsed = (datetime.utcnow() - start).total_seconds()
        log.info(f"准确率评估完成: {evaluated} 条记录, {elapsed:.1f}s")

    except Exception as e:
        log.error(f"准确率评估失败: {e}")


async def _evaluate_accuracy() -> int:
    """
    评估 KOL 提及代币的价格表现

    逻辑：
    1. 获取 24h+ 前的未评估提及
    2. 查询当前价格 vs 提及时价格
    3. 计算涨跌幅，标记是否 hit_2x
    4. 更新 kol_accuracy_log 和 kol_accounts 准确率
    """
    try:
        # 获取 24h+ 且未评估的提及
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()

        result = (
            get_db()
            .table("token_kol_mentions")
            .select("id, twitter_uid, token_address, chain, ticker, "
                    "price_at_mention, mentioned_at")
            .lt("mentioned_at", cutoff)
            .not_.is_("price_at_mention", "null")
            .limit(200)
            .execute()
        )

        mentions = result.data or []
        if not mentions:
            return 0

        # 检查哪些已经评估过
        mention_ids = [m["id"] for m in mentions]
        existing = (
            get_db()
            .table("kol_accuracy_log")
            .select("mention_id")
            .in_("mention_id", mention_ids)
            .execute()
        )
        evaluated_ids = set(r["mention_id"] for r in (existing.data or []))

        count = 0
        for mention in mentions:
            if mention["id"] in evaluated_ids:
                continue

            # TODO: 查询当前价格（通过 DexScreener 或 CoinGecko）
            # 当前版本先跳过实际价格查询，等数据源集成完成
            count += 1

        return count

    except Exception as e:
        log.error(f"Accuracy evaluation error: {e}")
        return 0


async def initialize_kol_accounts():
    """
    从种子列表初始化 KOL 账号

    在首次运行时调用，将 kol_seed.py 中的 KOL 导入数据库
    """
    try:
        from kol_seed import ALL_KOLS as KOL_SEED_LIST

        # 检查是否已经初始化
        result = (
            get_db()
            .table("kol_accounts")
            .select("id", count="exact")
            .execute()
        )
        existing_count = result.count or 0

        if existing_count > 0:
            log.info(f"KOL accounts already initialized ({existing_count} records)")
            return

        # 批量插入种子 KOL
        rows = []
        for kol in KOL_SEED_LIST:
            rows.append({
                "twitter_uid": kol["username"],  # 临时用 username 作为 uid
                "username": kol["username"],
                "display_name": kol.get("display_name", ""),
                "category": kol.get("category", "crypto"),
                "tier": kol.get("tier", "small"),
                "language": kol.get("language", "en"),
                "is_active": True,
            })

        # 分批插入
        for i in range(0, len(rows), 50):
            batch = rows[i:i + 50]
            get_db().table("kol_accounts").upsert(
                batch, on_conflict="twitter_uid"
            ).execute()

        log.info(f"Initialized {len(rows)} KOL accounts from seed list")

    except ImportError:
        log.warning("kol_seed module not found, skip initialization")
    except Exception as e:
        log.error(f"KOL initialization error: {e}")
