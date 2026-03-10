"""
pump-scanner 入口

启动：
  pip install -r requirements.txt
  cp .env.example .env   # 填入 Supabase 密钥
  python main.py

调度任务（所有时间均 UTC）：
  00:05  每日 pump.fun Top10 推荐（daily_job）
  01:00  创建者成功率更新（creator_stats_updater）
  02:00  热币日榜 Top20 生成（hot_coin_job）
  每1h   结果回填（outcome_labeler）
  每2h   热币全链扫描（hot_coin_job）
  每6h   聪明钱钱包更新（smart_wallet_updater）
"""

import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from collector import PumpScanner
from daily_job import run_daily_job
from outcome_labeler import run_outcome_labeler
from smart_wallet_updater import run_smart_wallet_updater
from creator_stats_updater import run_creator_stats_updater
from hot_coin_job import run_hot_coin_scan, run_hot_daily_picks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


async def main():
    scanner = PumpScanner()
    scheduler = AsyncIOScheduler()

    # ── 每日 Top10 推荐（UTC 00:05）────────────────────────
    scheduler.add_job(
        run_daily_job,
        trigger=CronTrigger(hour=0, minute=5, timezone="UTC"),
        id="daily_picks",
        name="每日 Top10 推荐",
        misfire_grace_time=300,
    )

    # ── 创建者成功率更新（UTC 01:00）────────────────────────
    scheduler.add_job(
        run_creator_stats_updater,
        trigger=CronTrigger(hour=1, minute=0, timezone="UTC"),
        id="creator_stats",
        name="创建者成功率更新",
        misfire_grace_time=600,
    )

    # ── 结果回填（每1小时）──────────────────────────────────
    scheduler.add_job(
        run_outcome_labeler,
        trigger="interval",
        hours=1,
        id="outcome_labeler",
        name="结果回填器",
        misfire_grace_time=300,
    )

    # ── 聪明钱钱包更新（每6小时）────────────────────────────
    scheduler.add_job(
        run_smart_wallet_updater,
        trigger="interval",
        hours=6,
        id="smart_wallet",
        name="聪明钱更新",
        misfire_grace_time=600,
    )

    # ── 热币全链扫描（每2小时）──────────────────────────────
    scheduler.add_job(
        run_hot_coin_scan,                  # async 协程，AsyncIOScheduler 直接支持
        trigger="interval",
        hours=2,
        id="hot_coin_scan",
        name="热币全链扫描",
        misfire_grace_time=600,
    )

    # ── 热币日榜生成（每天 UTC 02:00）───────────────────────
    scheduler.add_job(
        run_hot_daily_picks,
        trigger=CronTrigger(hour=2, minute=0, timezone="UTC"),
        id="hot_daily_picks",
        name="热币日榜 Top20",
        misfire_grace_time=600,
    )

    scheduler.start()
    log.info(
        "定时任务已启动:\n"
        "  每日 UTC 00:05 → daily_picks\n"
        "  每日 UTC 01:00 → creator_stats\n"
        "  每日 UTC 02:00 → hot_daily_picks\n"
        "  每1小时        → outcome_labeler\n"
        "  每2小时        → hot_coin_scan\n"
        "  每6小时        → smart_wallet_updater"
    )

    # 启动实时采集（阻塞主协程）
    await scanner.run()


if __name__ == "__main__":
    asyncio.run(main())
