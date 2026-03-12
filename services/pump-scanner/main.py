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
  每10m  热币增量扫描（hot_coin_job，增量模式 ~30s/轮）
  每5s   OKX 热币市场数据刷新+打分（hot_coin_job）
  每1s   推荐代币表现追踪（performance_tracker 常驻协程）
  每6h   聪明钱钱包更新（smart_wallet_updater）
  每30m  KOL 推文采集
  每30m  KOL 推文分析
  每1h   KOL 共振信号检测
  每24h  KOL 准确率评估
  每30s  Agent 策略监控

FastAPI API Server (port 8000):
  /api/agent/chat        POST  对话创建策略
  /api/agent/strategies  GET   策略列表
  /api/agent/alerts      GET   告警列表
  /docs                  GET   API 文档
"""

import asyncio
import logging
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from collector import PumpScanner
from daily_job import run_daily_job
from outcome_labeler import run_outcome_labeler
from smart_wallet_updater import run_smart_wallet_updater
from smart_wallet_seed import initialize_smart_wallets
from creator_stats_updater import run_creator_stats_updater
from hot_coin_job import run_hot_coin_scan, run_hot_daily_picks, run_hot_price_refresh
from performance_tracker import run_performance_loop

# KOL 系统
from kol_job import (
    run_kol_collect,
    run_kol_analyze,
    run_kol_signal_detect,
    run_kol_accuracy_eval,
    initialize_kol_accounts,
)

# Agent 系统
from agent.monitor_job import run_agent_monitor
from agent.event_bus import get_event_bus

# 聪明钱多链追踪
from smart_money_tracker import run_smart_money_scan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

# 是否启动 FastAPI（通过环境变量控制）
ENABLE_API = os.getenv("ENABLE_API", "true").lower() == "true"
API_PORT = int(os.getenv("API_PORT", "8000"))


async def main():
    scanner = PumpScanner()
    scheduler = AsyncIOScheduler()

    # ══════════════════════════════════════════════════════════
    # 原有定时任务
    # ══════════════════════════════════════════════════════════

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

    # ── 热币增量扫描（每10分钟）─────────────────────────────
    # 增量模式：已入库代币复用安全/社交数据，仅新代币走 GoPlus/Helius/DexScreener
    # 每轮 ~30s（vs 全量 3-5min），发现新代币延迟从 2h → 10min
    scheduler.add_job(
        run_hot_coin_scan,
        trigger="interval",
        minutes=10,
        id="hot_coin_scan",
        name="热币增量扫描",
        misfire_grace_time=120,
    )

    # ── 市场数据刷新（每30秒）─────────────────────────────
    # OKX Market API 优先（毫秒级价格），不可用时 DexScreener fallback
    # 单轮耗时：DexScreener 4链 ≈ 10-20s + 打分 ≈ 0.1s + DB写 ≈ 0.5s
    scheduler.add_job(
        run_hot_price_refresh,
        trigger="interval",
        seconds=30,
        id="hot_price_refresh",
        name="热币市场数据刷新",
        misfire_grace_time=15,
    )

    # ── 热币日榜生成（每天 UTC 02:00）───────────────────────
    scheduler.add_job(
        run_hot_daily_picks,
        trigger=CronTrigger(hour=2, minute=0, timezone="UTC"),
        id="hot_daily_picks",
        name="热币日榜 Top20",
        misfire_grace_time=600,
    )

    # ── 表现追踪（1秒常驻协程，不走 APScheduler）─────────────
    # 由 asyncio.create_task() 在 scheduler.start() 后启动
    # hot 代币: 直调 OKX API（1s循环）  pump 代币: pump.fun API
    # 内存缓存 daily_highs → 每 30s 批量落盘 DB

    # ══════════════════════════════════════════════════════════
    # KOL 系统定时任务
    # ══════════════════════════════════════════════════════════

    # ── KOL 推文采集（每30分钟）────────────────────────────
    scheduler.add_job(
        run_kol_collect,
        trigger="interval",
        minutes=30,
        id="kol_collect",
        name="KOL 推文采集",
        misfire_grace_time=300,
    )

    # ── KOL 推文分析（每30分钟）────────────────────────────
    scheduler.add_job(
        run_kol_analyze,
        trigger="interval",
        minutes=30,
        id="kol_analyze",
        name="KOL 推文分析",
        misfire_grace_time=300,
    )

    # ── KOL 共振信号检测（每1小时）─────────────────────────
    scheduler.add_job(
        run_kol_signal_detect,
        trigger="interval",
        hours=1,
        id="kol_signal_detect",
        name="KOL 共振信号检测",
        misfire_grace_time=300,
    )

    # ── KOL 准确率评估（每天 UTC 03:00）────────────────────
    scheduler.add_job(
        run_kol_accuracy_eval,
        trigger=CronTrigger(hour=3, minute=0, timezone="UTC"),
        id="kol_accuracy_eval",
        name="KOL 准确率评估",
        misfire_grace_time=600,
    )

    # ══════════════════════════════════════════════════════════
    # Agent 系统定时任务
    # ══════════════════════════════════════════════════════════

    # ── Agent 策略监控（每30秒）─────────────────────────────
    scheduler.add_job(
        run_agent_monitor,
        trigger="interval",
        seconds=30,
        id="agent_monitor",
        name="Agent 策略监控",
        misfire_grace_time=10,
    )

    # ── 聪明钱多链扫描（每15分钟）────────────────────────────
    scheduler.add_job(
        run_smart_money_scan,
        trigger="interval",
        minutes=15,
        id="smart_money_scan",
        name="聪明钱多链扫描",
        misfire_grace_time=120,
    )

    scheduler.start()
    log.info(
        "定时任务已启动:\n"
        "  ── 原有任务 ──\n"
        "  每日 UTC 00:05 → daily_picks\n"
        "  每日 UTC 01:00 → creator_stats\n"
        "  每日 UTC 02:00 → hot_daily_picks\n"
        "  每1小时        → outcome_labeler\n"
        "  每10分钟       → hot_coin_scan (增量发现)\n"
        "  每30秒         → hot_price_refresh (OKX+DexScreener 全字段+打分)\n"
        "  每6小时        → smart_wallet_updater\n"
        "  ── KOL 系统 ──\n"
        "  每30分钟       → kol_collect\n"
        "  每30分钟       → kol_analyze\n"
        "  每1小时        → kol_signal_detect\n"
        "  每日 UTC 03:00 → kol_accuracy_eval\n"
        "  ── Agent 系统 ──\n"
        "  每30秒         → agent_monitor\n"
        "  每15分钟       → smart_money_scan (多链聪明钱)\n"
        "  ── 常驻协程 ──\n"
        "  1秒循环        → performance_loop (OKX+pump.fun 秒级追踪)"
    )

    # 初始化种子数据
    await initialize_kol_accounts()
    initialize_smart_wallets()

    # 启动表现追踪常驻协程（1秒循环）
    asyncio.create_task(run_performance_loop())
    log.info("📊 表现追踪协程已启动 (1s loop)")

    # 启动事件总线
    event_bus = get_event_bus()
    asyncio.create_task(event_bus.start())
    log.info("EventBus started")

    # 启动 FastAPI（如果启用）
    if ENABLE_API:
        from api.app import start_api_server
        api_task = asyncio.create_task(start_api_server(port=API_PORT))
        log.info(f"FastAPI server starting on port {API_PORT}")

    # 启动实时采集（阻塞主协程）
    await scanner.run()


if __name__ == "__main__":
    asyncio.run(main())
